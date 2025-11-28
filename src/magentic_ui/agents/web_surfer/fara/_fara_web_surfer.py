from typing import AsyncGenerator, Sequence, List, Tuple, Dict, Any
import asyncio
import logging
import io
import json
import ast
from urllib.parse import quote_plus
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage, TextMessage, MultiModalMessage
from autogen_core.models import (
    AssistantMessage,
    LLMMessage,
    SystemMessage,
    UserMessage,
)
from autogen_core import CancellationToken, Image as AGImage, FunctionCall
import PIL.Image as Image

from .._web_surfer import WebSurfer
from ._prompts import get_computer_use_system_prompt
from ....tools.playwright.browser import VncDockerPlaywrightBrowser
from ....tools.playwright.playwright_controller_fara import PlaywrightController
from ....types import HumanInputFormat


def encode_search_query(query: str) -> str:
    """Encode a search query for URL parameters."""
    return quote_plus(query)


class FaraWebSurfer(WebSurfer):
    DEFAULT_DESCRIPTION = "A helpful assistant with access to a web browser. Ask them to perform web searches, open pages, and interact with content (e.g., clicking links, scrolling the viewport, etc., filling in form fields, etc.) It can also summarize the entire page, or answer questions based on the content of the page. It can also be asked to sleep and wait for pages to load, in cases where the pages seem to be taking a while to load."

    DEFAULT_START_PAGE = "https://www.bing.com/"

    # Viewport dimensions
    # VIEWPORT_HEIGHT = 720
    # VIEWPORT_WIDTH = 1280
    VIEWPORT_HEIGHT = 900
    VIEWPORT_WIDTH = 1440

    # Size of the image we send to the MLM
    # MLM_HEIGHT = 720
    # MLM_WIDTH = 1280
    MLM_HEIGHT = 900
    MLM_WIDTH = 1440

    MLM_PROCESSOR_IM_CFG = {
        "min_pixels": 3136,
        "max_pixels": 12845056,
        "patch_size": 14,
        "merge_size": 2,
    }

    SCREENSHOT_TOKENS = 1105
    MAX_URL_LENGTH = 100
    USER_MESSAGE = "Here is the next screenshot. Think about what to do next."

    def __init__(
        self,
        max_n_images: int = 3,
        fn_call_template: str = "default",
        model_call_timeout: int = 20,
        max_rounds: int = 100,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.max_n_images = max_n_images
        self.fn_call_template = fn_call_template
        self.model_call_timeout = model_call_timeout
        self._facts = []
        self._action_history = []
        self._task_summary = None
        self.max_rounds = max_rounds
        self.logger = logging.getLogger(__name__)
        self._mlm_width = 1440
        self._mlm_height = 900
        self.viewport_height = 900
        self.viewport_width = 1440
        self.original_user_message_indices = set()
        self._playwright_controller = PlaywrightController(
            animate_actions=False,
            downloads_folder=self.downloads_folder,
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
            _download_handler=self._download_handler,
            to_resize_viewport=self.to_resize_viewport,
            single_tab_mode=True,
            logger=self.logger,
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=5.0, min=5.0, max=60),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    async def _make_model_call(self, history, extra_create_args):
        """Make a model call with automatic retry."""
        return await asyncio.wait_for(
            self._model_client.create(history, extra_create_args=extra_create_args),
            timeout=self.model_call_timeout,
        )

    def remove_screenshot_from_message(self, msg: LLMMessage) -> LLMMessage | None:
        """Remove the screenshot from the message content."""
        if isinstance(msg.content, list):
            new_content = []
            for c in msg.content:
                if not isinstance(c, AGImage):
                    new_content.append(c)
            msg.content = new_content
        elif isinstance(msg.content, AGImage):
            msg = None
        return msg

    def maybe_remove_old_screenshots(
        self, history: List[LLMMessage], includes_current=False
    ) -> List[LLMMessage]:
        """Remove old screenshots from the chat history. Assuming we have not yet added the current screenshot message.

        Note: Original user messages (marked with is_original=True) have their TEXT preserved,
        but their images may be removed if we exceed max_n_images. Boilerplate messages can be
        completely removed.
        """
        if self.max_n_images <= 0:
            return history

        max_n_images = self.max_n_images if includes_current else self.max_n_images - 1
        new_history: List[LLMMessage] = []
        n_images = 0
        for i in range(len(history) - 1, -1, -1):
            msg = history[i]
            is_original_user_message = i in self.original_user_message_indices

            if i == 0 and n_images >= max_n_images:
                # First message is always the task so we keep it and remove the screenshot if necessary
                msg = self.remove_screenshot_from_message(msg)
                if msg is None:
                    continue

            if isinstance(msg.content, list):
                # Check if the message contains an image. Assumes 1 image per message.
                has_image = False
                for c in msg.content:
                    if isinstance(c, AGImage):
                        has_image = True
                        break
                if has_image:
                    if n_images < max_n_images:
                        new_history.append(msg)
                    elif is_original_user_message:
                        # Keep original user messages but remove the image
                        msg = self.remove_screenshot_from_message(msg)
                        if msg is not None:
                            new_history.append(msg)
                    n_images += 1
                else:
                    new_history.append(msg)
            elif isinstance(msg.content, AGImage) and n_images < max_n_images:
                new_history.append(msg)
                n_images += 1
            else:
                new_history.append(msg)

        new_history = new_history[::-1]

        return new_history

    def _get_system_message(
        self, screenshot: AGImage | Image.Image
    ) -> Tuple[List[SystemMessage], Image.Image]:
        system_prompt_info = get_computer_use_system_prompt(
            screenshot,
            self.MLM_PROCESSOR_IM_CFG,
            include_input_text_key_args=True,
            fn_call_template=self.fn_call_template,
        )
        self._mlm_width, self._mlm_height = system_prompt_info["im_size"]
        scaled_screenshot = screenshot.resize((self._mlm_width, self._mlm_height))

        system_message = []
        for msg in system_prompt_info["conversation"]:
            tmp_content = ""
            for content in msg["content"]:
                tmp_content += content["text"]

            system_message.append(SystemMessage(content=tmp_content))

        return system_message, scaled_screenshot

    def _parse_thoughts_and_action(self, message: str) -> Tuple[str, Dict[str, Any]]:
        try:
            tmp = message.split("<tool_call>\n")
            thoughts = tmp[0].strip()
            action_text = tmp[1].split("\n</tool_call>")[0]
            try:
                action = json.loads(action_text)
            except json.decoder.JSONDecodeError:
                self.logger.error(f"Invalid action text: {action_text}")
                action = ast.literal_eval(action_text)

            return thoughts, action
        except Exception as e:
            self.logger.error(
                f"Error parsing thoughts and action: {message}", exc_info=True
            )
            raise e

    def convert_resized_coords_to_original(
        self, coords: List[float], rsz_w: int, rsz_h: int, og_w: int, og_h: int
    ) -> List[float]:
        scale_x = og_w / rsz_w
        scale_y = og_h / rsz_h
        return [coords[0] * scale_x, coords[1] * scale_y]

    def proc_coords(
        self,
        coords: List[float],
        im_w: int,
        im_h: int,
        og_im_w: int = None,
        og_im_h: int = None,
    ) -> List[float]:
        if not coords:
            return coords

        if og_im_w is None:
            og_im_w = im_w
        if og_im_h is None:
            og_im_h = im_h

        tgt_x, tgt_y = coords
        return self.convert_resized_coords_to_original(
            [tgt_x, tgt_y], im_w, im_h, og_im_w, og_im_h
        )

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseChatMessage | Response, None]:
        """Dummy implementation that returns a static response."""
        # add the last message to the chat history
        await self.lazy_init()

        # Ensure page is ready after lazy initialization
        assert self._page is not None, "Page should be initialized"

        # Send browser address message if this is the first time the browser is being used
        if (
            self._browser_just_initialized
            and isinstance(self._browser, VncDockerPlaywrightBrowser)
            and self._browser.novnc_port > 0
        ):
            # Send browser address message after browser is initialized
            yield TextMessage(
                source="system",
                content=f"Browser noVNC address can be found at http://localhost:{self._browser.novnc_port}/vnc.html",
                metadata={
                    "internal": "no",
                    "type": "browser_address",
                    "novnc_port": str(self._browser.novnc_port),
                    "playwright_port": str(self._browser.playwright_port),
                },
            )
            # Reset the flag so we don't send the message again
            self._browser_just_initialized = False

        assert messages and isinstance(messages[-1], TextMessage)
        # add the message sent to the websurfer, excluding our own messages
        screenshot = await self._playwright_controller.get_screenshot(self._page)
        screenshot = Image.open(io.BytesIO(screenshot))
        _, scaled_screenshot = self._get_system_message(screenshot)
        if messages[-1].source != self.name:
            if messages[-1].source == "user_proxy" or messages[-1].source == "user":
                human_input = HumanInputFormat.from_str(messages[-1].content)
                content_human = f"{human_input.content}"
                self._chat_history.append(
                    UserMessage(
                        content=[content_human, AGImage.from_pil(scaled_screenshot)],
                        source=messages[-1].source,
                    )
                )
                self.original_user_message_indices.add((len(self._chat_history) - 1))
            else:
                assert isinstance(
                    messages[-1].content,
                    str,
                    "Fara web surfer only supports text messages from non-user sources.",
                )
                self._chat_history.append(
                    UserMessage(
                        content=[
                            messages[-1].content,
                            AGImage.from_pil(scaled_screenshot),
                        ],
                        source=messages[-1].source,
                    )
                )
                self.original_user_message_indices.add((len(self._chat_history) - 1))
        assert len(self._chat_history) > 0, "Chat history should not be empty"
        for i in range(self.max_rounds):
            is_stop_action = False
            is_first_round = i == 0
            function_call, raw_response = await self.generate_model_call(
                is_first_round, scaled_screenshot if is_first_round else None
            )
            assert isinstance(raw_response, str)
            # Extract thoughts and action for formatted display
            thoughts, action = self._parse_thoughts_and_action(raw_response)
            action_args = action.get("arguments", {})
            action_type = action_args.get("action", "")

            # Check if this is a terminate action
            if action_type in ["terminate", "stop"]:
                # For terminate, only emit the thoughts without executing
                yield Response(
                    chat_message=TextMessage(
                        content=thoughts,
                        source=self.name,
                    ),
                )
                break

            # For pause_and_memorize_fact, show thoughts but continue to execute
            # The action description will be shown after execution
            if action_type == "pause_and_memorize_fact":
                yield Response(
                    chat_message=TextMessage(
                        content=thoughts,
                        source=self.name,
                    ),
                )
            else:
                formatted_content = f"{thoughts} (tool: {action_type})"
                yield Response(
                    chat_message=TextMessage(
                        content=formatted_content,
                        source=self.name,
                    ),
                )
            if self.is_paused:
                yield TextMessage(
                    content="Web surfer is paused. Please type a message to continue.",
                    source="system",
                    metadata={
                        "internal": "no",
                        "type": "paused",
                    },
                )
                break
            try:
                (
                    is_stop_action,
                    new_screenshot,
                    action_description,
                ) = await self.execute_action(
                    function_call,
                    {},
                    tool_names=None,
                    cancellation_token=cancellation_token,
                )

                yield Response(
                    chat_message=MultiModalMessage(
                        content=[
                            AGImage.from_pil(Image.open(io.BytesIO(new_screenshot))),
                            action_description,
                        ],
                        source=self.name,
                        metadata={
                            "internal": "no",
                            "type": "browser_screenshot",
                        },
                    ),
                )
            except Exception as e:
                error_msg = f"Error executing action: {e}"

                yield Response(
                    chat_message=TextMessage(
                        content=error_msg,
                        source=self.name,
                    ),
                )

            if self.is_paused:
                yield TextMessage(
                    content="Web surfer is paused. Please type a message to continue.",
                    source="system",
                    metadata={
                        "internal": "no",
                        "type": "paused",
                    },
                )
                break
            if is_stop_action:
                break

    async def generate_model_call(
        self, is_first_round: bool, scaled_screenshot: Image.Image = None
    ):
        history = self.maybe_remove_old_screenshots(self._chat_history)
        screenshot_for_system = scaled_screenshot if is_first_round else None
        if not is_first_round:
            screenshot = await self._playwright_controller.get_screenshot(self._page)
            screenshot = Image.open(io.BytesIO(screenshot))
            system_message, scaled_screenshot = self._get_system_message(screenshot)
            screenshot_for_system = scaled_screenshot
            text_prompt = self.USER_MESSAGE
            curr_url = await self._playwright_controller.get_page_url(self._page)
            # Trim URL to 100 characters
            trimmed_url = curr_url.split("?", 1)[0]  # Strip query parameters
            if len(trimmed_url) > 100:
                trimmed_url = trimmed_url[:100] + " ..."
            text_prompt = f"Current URL: {trimmed_url}\n" + text_prompt

            curr_message = UserMessage(
                content=[AGImage.from_pil(scaled_screenshot), text_prompt],
                source=self.name,
            )
            self._chat_history.append(curr_message)
            history.append(curr_message)
        else:
            system_message, _ = self._get_system_message(screenshot_for_system)
        history = system_message + history
        response = await self._make_model_call(
            history, extra_create_args={"temperature": 0}
        )
        message = response.content

        self._chat_history.append(AssistantMessage(content=message, source=self.name))
        thoughts, action = self._parse_thoughts_and_action(message)
        action["arguments"]["thoughts"] = thoughts

        function_call = [FunctionCall(id="dummy", **action)]
        return function_call, message

    async def execute_action(
        self,
        function_call,
        rects,
        tool_names=None,
        cancellation_token: CancellationToken = None,
    ):
        # name = function_call[0].name
        args = function_call[0].arguments
        action_description = ""
        assert self._page is not None

        if "coordinate" in args:
            args["coordinate"] = self.proc_coords(
                args["coordinate"],
                self._mlm_width,
                self._mlm_height,
                self.viewport_width,
                self.viewport_height,
            )

        is_stop_action = False

        if args["action"] == "visit_url":
            url = str(args["url"])
            action_description = f"I typed '{url}' into the browser address bar."
            # Check if the argument starts with a known protocol
            if url.startswith(("https://", "http://", "file://", "about:")):
                (
                    reset_prior_metadata,
                    reset_last_download,
                ) = await self._playwright_controller.visit_page(self._page, url)
            # If the argument contains a space, treat it as a search query
            elif " " in url:
                (
                    reset_prior_metadata,
                    reset_last_download,
                ) = await self._playwright_controller.visit_page(
                    self._page,
                    f"https://www.bing.com/search?q={quote_plus(url)}&FORM=QBLH",
                )
            # Otherwise, prefix with https://
            else:
                (
                    reset_prior_metadata,
                    reset_last_download,
                ) = await self._playwright_controller.visit_page(
                    self._page, "https://" + url
                )
            if reset_last_download and self._last_download is not None:
                self._last_download = None
            if reset_prior_metadata and self._prior_metadata_hash is not None:
                self._prior_metadata_hash = None
        elif args["action"] == "history_back":
            action_description = "I clicked the browser back button."
            await self._playwright_controller.back(self._page)
        elif args["action"] == "web_search":
            query = args.get("query")
            action_description = f"I typed '{query}' into the browser search bar."
            encoded_query = encode_search_query(query)
            (
                reset_prior_metadata,
                reset_last_download,
            ) = await self._playwright_controller.visit_page(
                self._page, f"https://www.bing.com/search?q={encoded_query}&FORM=QBLH"
            )
            if reset_last_download and self._last_download is not None:
                self._last_download = None
            if reset_prior_metadata and self._prior_metadata_hash is not None:
                self._prior_metadata_hash = None
        elif args["action"] == "scroll":
            pixels = int(args.get("pixels", 0))
            if pixels > 0:
                action_description = "I scrolled up one page in the browser."
                await self._playwright_controller.page_up(self._page)
            elif pixels < 0:
                action_description = "I scrolled down one page in the browser."
                await self._playwright_controller.page_down(self._page)
        elif args["action"] == "keypress" or args["action"] == "key":
            keys = args.get("keys", [])
            action_description = f"I pressed the following keys: {keys}"
            await self._playwright_controller.keypress(self._page, keys)
        elif args["action"] == "hover" or args["action"] == "mouse_move":
            if "coordinate" in args:
                tgt_x, tgt_y = args["coordinate"]
                await self._playwright_controller.hover_coords(self._page, tgt_x, tgt_y)
            else:
                target_id = str(args.get("target_id", args.get("id")))
                target_name = self._target_name(target_id, rects)
                if target_name:
                    action_description = f"I moved the mouse over '{target_name}'."
                else:
                    action_description = "I moved the mouse over the control."
                await self._playwright_controller.hover_id(self._page, target_id)
        elif args["action"] == "sleep" or args["action"] == "wait":
            duration = args.get("duration", 3.0)
            duration = args.get("time", duration)
            action_description = (
                "I am waiting a short period of time before taking further action."
            )
            await self._playwright_controller.sleep(self._page, duration)
        elif args["action"] == "click" or args["action"] == "left_click":
            if "coordinate" in args:
                tgt_x, tgt_y = args["coordinate"]
                action_description = (
                    f"I clicked at coordinates ({int(tgt_x)}, {int(tgt_y)})."
                )
                new_page_tentative = await self._playwright_controller.click_coords(
                    self._page, tgt_x, tgt_y
                )
            else:
                target_id = str(args.get("target_id", args.get("id")))
                target_name = self._target_name(target_id, rects)
                if target_name:
                    action_description = f"I clicked '{target_name}'."
                else:
                    action_description = "I clicked the control."
                new_page_tentative = await self._playwright_controller.click_id(
                    self._page, target_id
                )

            if new_page_tentative is not None:
                self._page = new_page_tentative
                self._prior_metadata_hash = None

        elif args["action"] == "input_text" or args["action"] == "type":
            text_value = str(args.get("text", args.get("text_value")))
            action_description = f"I typed '{text_value}'."
            press_enter = args.get("press_enter", True)
            delete_existing_text = args.get("delete_existing_text", False)

            if "coordinate" in args:
                tgt_x, tgt_y = args["coordinate"]
                new_page_tentative = await self._playwright_controller.fill_coords(
                    self._page,
                    tgt_x,
                    tgt_y,
                    text_value,
                    press_enter=press_enter,
                    delete_existing_text=delete_existing_text,
                )
                if new_page_tentative is not None:
                    self._page = new_page_tentative
                    self._prior_metadata_hash = None
        elif args["action"] == "pause_and_memorize_fact":
            fact = str(args.get("fact"))
            self._facts.append(fact)
            action_description = f"I memorized the following fact: {fact}"
        elif args["action"] == "stop" or args["action"] == "terminate":
            action_description = args.get("thoughts")
            is_stop_action = True

        else:
            raise ValueError(f"Unknown tool: {args['action']}")

        await self._playwright_controller.wait_for_load_state(self._page)
        await self._playwright_controller.sleep(
            self._page, 1
        )  # There's a 2s sleep below too

        new_screenshot = await self._playwright_controller.get_screenshot(self._page)

        return is_stop_action, new_screenshot, action_description
