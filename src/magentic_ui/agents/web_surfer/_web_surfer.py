import asyncio
import io
import json
import logging
import os
import re
import time
from datetime import datetime
import tldextract
from typing import (
    Any,
    AsyncGenerator,
    BinaryIO,
    Dict,
    List,
    Optional,
    Sequence,
    cast,
    Mapping,
    Union,
    Tuple,
    Literal,
)
from typing_extensions import Self
from loguru import logger
from urllib.parse import quote_plus
from pydantic import Field
import PIL.Image
import tiktoken
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    BaseChatMessage,
    MultiModalMessage,
    TextMessage,
)
from autogen_agentchat.utils import content_to_str, remove_images
from autogen_agentchat.state import BaseState
from autogen_core import EVENT_LOGGER_NAME, CancellationToken, FunctionCall
from autogen_core import Image as AGImage
from autogen_core.tools import ToolSchema

from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    LLMMessage,
    RequestUsage,
    SystemMessage,
    UserMessage,
)
from autogen_core.model_context import TokenLimitedChatCompletionContext
from pydantic import BaseModel
from autogen_core import Component, ComponentModel

from playwright.async_api import (
    BrowserContext,
    Download,
    Page,
)

from ...tools.playwright.browser import PlaywrightBrowser, VncDockerPlaywrightBrowser

from ...approval_guard import (
    ApprovalGuardContext,
    BaseApprovalGuard,
    MaybeRequiresApproval,
)

from ._events import WebSurferEvent
from ._prompts import (
    WEB_SURFER_OCR_PROMPT,
    WEB_SURFER_QA_PROMPT,
    WEB_SURFER_QA_SYSTEM_MESSAGE,
    WEB_SURFER_TOOL_PROMPT,
    WEB_SURFER_SYSTEM_MESSAGE,
    WEB_SURFER_NO_TOOLS_PROMPT,
)
from ._set_of_mark import add_set_of_mark
from ._tool_definitions import (
    TOOL_CLICK,
    TOOL_HISTORY_BACK,
    TOOL_HOVER,
    # TOOL_PAGE_DOWN,
    # TOOL_PAGE_UP,
    TOOL_READ_PAGE_AND_ANSWER,
    TOOL_SLEEP,
    TOOL_TYPE,
    TOOL_VISIT_URL,
    TOOL_WEB_SEARCH,
    TOOL_STOP_ACTION,
    TOOL_SELECT_OPTION,
    TOOL_CREATE_TAB,
    TOOL_SWITCH_TAB,
    # TOOL_CLOSE_TAB,
    TOOL_KEYPRESS,
    TOOL_REFRESH_PAGE,
    TOOL_SCROLL_DOWN,
    TOOL_SCROLL_UP,
    # TOOL_UPLOAD_FILE,
    # TOOL_CLICK_FULL,
)

from ...tools.tool_metadata import get_tool_metadata, ToolMetadata
from ...tools.playwright.types import InteractiveRegion
from ...tools.playwright.playwright_controller import PlaywrightController
from ...tools.playwright.playwright_state import (
    BrowserState,
    save_browser_state,
    load_browser_state,
)
from ...tools.url_status_manager import (
    UrlStatusManager,
    UrlStatus,
    URL_ALLOWED,
    URL_REJECTED,
)


# New configuration class for WebSurfer
class WebSurferConfig(BaseModel):
    # TODO: Add playwright and context
    name: str
    model_client: ComponentModel | Dict[str, Any]
    browser: ComponentModel | Dict[str, Any]
    model_context_token_limit: int | None = None
    downloads_folder: str | None = None
    description: str | None = None
    debug_dir: str | None = None
    start_page: str | None = "about:blank"
    animate_actions: bool = False
    to_save_screenshots: bool = False
    max_actions_per_step: int = 5
    to_resize_viewport: bool = True
    url_statuses: Dict[str, UrlStatus] | None = None
    url_block_list: List[str] | None = None
    single_tab_mode: bool = False
    json_model_output: bool = False
    multiple_tools_per_call: bool = False
    viewport_height: int = 1440
    viewport_width: int = 1440
    use_action_guard: bool = False
    search_engine: str = "duckduckgo"


class WebSurferState(BaseState):
    """
    State class for saving and loading the WebSurfer's state.

    Attributes:
        chat_history (List[LLMMessage]): List of chat messages exchanged with the model.
        type (str, optional): The type of the state. Default: `WebSurferState`.
        browser_state (BrowserState, optional): The state of the browser, including tabs and active page.
    """

    chat_history: List[LLMMessage]
    type: str = Field(default="WebSurferState")
    browser_state: BrowserState | None = None


class WebSurfer(BaseChatAgent, Component[WebSurferConfig]):
    """An agent that can browse the web and interact with web pages using a browser.

    Works with any model that supports tool calling or JSON outputs. Works best with multimodal models.

    The WebSurfer uses Playwright to control a browser and navigate web pages. It can:
    - Visit URLs and perform web searches
    - Click links and buttons
    - Fill in forms and type text
    - Scroll and hover over elements
    - Read and extract content from pages
    - Take screenshots and handle downloads
    - Manage multiple browser tabs

    The agent uses an LLM to decide what actions to take based on the current page state
    and user instructions.

    The browser interactions are controlled through a set of tools that the LLM can invoke.
    The agent captures screenshots and page content to give the LLM context about the
    current state of the page.

    Args:
        name (str): The name of the agent.
        model_client (ChatCompletionClient): The model client used by the agent.
        browser (PlaywrightBrowser): The browser resource to use.
        downloads_folder (str, optional): The folder where downloads are saved. Default: None.
        description (str, optional): The description of the agent. Default: WebSurfer.DEFAULT_DESCRIPTION.
        debug_dir (str, optional): The directory where debug information is saved. Default: None.
        start_page (str, optional): The start page for the browser. Defaults: WebSurfer.DEFAULT_START_PAGE.
        animate_actions (bool, optional): Whether to animate actions. Default: False.
        to_save_screenshots (bool, optional): Whether to save screenshots. Default: False.
        max_actions_per_step (int, optional): The maximum number of actions per step. Default: 5.
        to_resize_viewport (bool, optional): Whether to resize the viewport. Default: True.
        url_statuses (Dict[str, Literal["allowed", "rejected"]], optional): The set of allowed and rejected websites. Default: None.
        single_tab_mode (bool, optional): Whether to use single tab mode. Default: False.
        url_block_list (List[str], optional): A list of URLs to block. Default: None.
        json_model_output (bool, optional): Whether to use JSON output for model_client instead of tool calls. Default: False.
        multiple_tools_per_call (bool, optional): Whether to allow execution of multiple tool calls sequentially per model call. Default: False.
        viewport_height (int, optional): The height of the viewport. Default: 1440.
        viewport_width (int, optional): The width of the viewport. Default: 1440.
        search_engine (str, optional): The search engine to use for web searches. Supported engines: "duckduckgo", "google", "bing", "yahoo". Any other value will be treated as a direct website URL to visit. Default: "duckduckgo".
    """

    component_type = "agent"
    component_config_schema = WebSurferConfig
    component_provider_override = "magentic_ui.agents.web_surfer.WebSurfer"

    DEFAULT_DESCRIPTION = """
    The websurfer has access to a web browser that it can control.
    It understands images and can use them to help it complete the task.

    In a single step when you ask the agent to do something, it will perform multiple actions sequentially until it decides to stop.
    The actions it can perform are:
    - visiting a web page url
    - performing a web search using a configurable search engine
    - Interact with a web page: clicking a button, hovering over a button, typing in a field, scrolling the page, select an option in a dropdown
    - Downloading a file from the web page and upload file from the local file system
    - Pressing a key on the keyboard to interact with the web page
    - answer a question based on the content of the entire page beyond just the vieport
    - wait on a page to load
    - interact with tabs on the page: closing a tab, switching to a tab, creating a new tab
    - refresh the page

    It can do multiple actions in a single step, but it will stop after it has performed the maximum number of actions or once it decides to stop.
    As mentioned, it can perform multiple actions per command given to it, for instance if asked to fill a form, it can input the first name, then the last name, then the email, and then submit, and then stop.
    """
    DEFAULT_START_PAGE = "about:blank"

    # Size of the image we send to the MLM
    # Current values represent a 0.85 scaling to fit within the GPT-4v short-edge constraints (768px)
    MLM_HEIGHT = 765
    MLM_WIDTH = 1224

    SCREENSHOT_TOKENS = 1105

    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        browser: PlaywrightBrowser,
        model_context_token_limit: int | None = None,
        downloads_folder: str | None = None,
        description: str = DEFAULT_DESCRIPTION,
        debug_dir: str | None = None,
        start_page: str = DEFAULT_START_PAGE,
        animate_actions: bool = False,
        to_save_screenshots: bool = False,
        max_actions_per_step: int = 5,
        to_resize_viewport: bool = True,
        url_statuses: Optional[Dict[str, UrlStatus]] = None,
        url_block_list: Optional[List[str]] = None,
        single_tab_mode: bool = False,
        json_model_output: bool = False,
        multiple_tools_per_call: bool = False,
        viewport_height: int = 1440,
        viewport_width: int = 1440,
        use_action_guard: bool = False,
        search_engine: str = "duckduckgo",
    ) -> None:
        """
        Initialize the WebSurfer.
        """
        super().__init__(name, description)
        if debug_dir is None and to_save_screenshots:
            raise ValueError(
                "Cannot save screenshots without a debug directory. Set it using the 'debug_dir' parameter. The debug directory is created if it does not exist."
            )
        self._model_client = model_client
        self._model_context = TokenLimitedChatCompletionContext(
            model_client=self._model_client, token_limit=model_context_token_limit
        )
        self.start_page = start_page
        self.downloads_folder = downloads_folder
        self.debug_dir = debug_dir
        self.to_save_screenshots = to_save_screenshots
        self.to_resize_viewport = to_resize_viewport
        self.animate_actions = animate_actions
        self.max_actions_per_step = max_actions_per_step
        self.single_tab_mode = single_tab_mode
        self.json_model_output = json_model_output
        # If the model does not support function calling, we will use JSON output
        # override the json_model_output flag
        if not self._model_client.model_info["function_calling"]:
            self.json_model_output = True
        self.multiple_tools_per_call = multiple_tools_per_call
        self.viewport_height = viewport_height
        self.viewport_width = viewport_width
        self.use_action_guard = use_action_guard
        self.search_engine = search_engine
        self._browser = browser
        # Call init to set these in case not set
        self._context: BrowserContext | None = None
        self._url_status_manager: UrlStatusManager = UrlStatusManager(
            url_statuses=url_statuses, url_block_list=url_block_list
        )
        self._page: Page | None = None
        self._last_download: Download | None = None
        self._prior_metadata_hash: str | None = None
        self.logger = logging.getLogger(EVENT_LOGGER_NAME + f".{self.name}.WebSurfer")
        self._chat_history: List[LLMMessage] = []
        self._last_outside_message: str = ""
        self._last_rejected_url: str | None = None

        # TODO: These are a little bit of a hack so we can get the ports out of the browser object
        self.novnc_port = -1
        self.playwright_port = -1
        if isinstance(self._browser, VncDockerPlaywrightBrowser):
            self.novnc_port = self._browser.novnc_port
            self.playwright_port = self._browser.playwright_port

        # explicitly allow about:blank
        if not self._url_status_manager.is_url_allowed("about:blank"):
            self._url_status_manager.set_url_status("about:blank", URL_ALLOWED)
        # explicitly allow chrome-error://chromewebdata
        if not self._url_status_manager.is_url_allowed("chrome-error://chromewebdata"):
            self._url_status_manager.set_url_status(
                "chrome-error://chromewebdata", URL_ALLOWED
            )

        if not self._url_status_manager.is_url_allowed(self.start_page):
            self.start_page = "about:blank"
            self.logger.warning(
                f"Default start page '{self.DEFAULT_START_PAGE}' is not in the allow list. Setting start page to blank."
            )

        # Define the download handler
        def _download_handler(download: Download) -> None:
            self._last_download = download

        self._download_handler = _download_handler

        # Define the Playwright controller that handles the browser interactions
        self._playwright_controller = PlaywrightController(
            animate_actions=self.animate_actions,
            downloads_folder=self.downloads_folder,
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
            _download_handler=self._download_handler,
            to_resize_viewport=self.to_resize_viewport,
            single_tab_mode=self.single_tab_mode,
            url_status_manager=self._url_status_manager,
            url_validation_callback=self._check_url_and_generate_msg,
        )
        self.default_tools = [
            TOOL_STOP_ACTION,
            TOOL_VISIT_URL,
            TOOL_WEB_SEARCH,
            TOOL_CLICK,
            TOOL_TYPE,
            TOOL_READ_PAGE_AND_ANSWER,
            TOOL_SLEEP,
            TOOL_HOVER,
            TOOL_HISTORY_BACK,
            TOOL_KEYPRESS,
            TOOL_REFRESH_PAGE,
            TOOL_SCROLL_DOWN,
            TOOL_SCROLL_UP,
            # TOOL_CLICK_FULL,
        ]
        self.did_lazy_init = False  # flag to check if we have initialized the browser
        self._browser_just_initialized = False
        self.is_paused = False
        self._pause_event = asyncio.Event()
        self.action_guard: BaseApprovalGuard | None = (
            ApprovalGuardContext.approval_guard() if self.use_action_guard else None
        )
        if self._model_client.model_info["vision"]:
            self.is_multimodal = True
        else:
            self.is_multimodal = False

    def _get_search_url(self, query: str) -> tuple[str, str]:
        """Get search URL and domain based on configured search engine.

        Args:
            query (str): The search query

        Returns:
            tuple[str, str]: (search_url, domain) - For known search engines, returns search URL.
                            For unknown engines, treats the engine name as a direct website URL.
        """
        if self.search_engine.lower() == "google":
            domain = "google.com"
            url = f"https://www.google.com/search?q={quote_plus(query)}"
        elif self.search_engine.lower() == "bing":
            domain = "bing.com"
            url = f"https://www.bing.com/search?q={quote_plus(query)}"
        elif self.search_engine.lower() == "yahoo":
            domain = "yahoo.com"
            url = f"https://search.yahoo.com/search?p={quote_plus(query)}"
        elif self.search_engine.lower() == "duckduckgo":
            domain = "duckduckgo.com"
            url = f"https://duckduckgo.com/?q={quote_plus(query)}"
        else:  # treat as direct website URL
            domain = self.search_engine
            url = (
                f"https://{self.search_engine}"
                if not self.search_engine.startswith(("http://", "https://"))
                else self.search_engine
            )
        return url, domain

    async def lazy_init(
        self,
    ) -> None:
        """Initialize the browser and page on first use.

        This method is called automatically on first interaction. It:
        - Starts Playwright and launches a browser
        - Creates a new browser context and page
        - Configures viewport size and downloads
        - Navigates to the start page
        - Sets up the debug directory if specified
        """
        if self.did_lazy_init:
            return

        self._last_download = None
        self._prior_metadata_hash = None

        await self._browser.__aenter__()

        if isinstance(self._browser, VncDockerPlaywrightBrowser):
            self.novnc_port = self._browser.novnc_port
            self.playwright_port = self._browser.playwright_port

        self._context = self._browser.browser_context

        # Create the page
        assert self._context is not None
        self._context.set_default_timeout(20000)  # 20 sec

        self._page = None
        self._page = await self._context.new_page()
        await self._playwright_controller.on_new_page(self._page)

        async def handle_new_page(new_pg: Page) -> None:
            # last resort on new tabs
            assert new_pg is not None
            assert self._page is not None
            await new_pg.wait_for_load_state("domcontentloaded")
            new_url = new_pg.url
            await new_pg.close()
            await self._playwright_controller.visit_page(self._page, new_url)

        if self.single_tab_mode:
            # this will make sure any new tabs will be closed and redirected to the main page
            # it is a last resort, the playwright controller handles most cases
            self._context.on("page", lambda new_pg: handle_new_page(new_pg))

        try:
            await self._playwright_controller.visit_page(self._page, self.start_page)
        except Exception:
            pass

        # Prepare the debug directory -- which stores the screenshots generated throughout the process
        await self._set_debug_dir()
        self.did_lazy_init = True
        self._browser_just_initialized = True

    async def pause(self) -> None:
        """Pause the WebSurfer agent."""
        self.is_paused = True
        self._pause_event.set()

    async def monitor_pause(self, cancellation_token: CancellationToken) -> None:
        """Set up background task to monitor the pause event and cancel the code execution if paused."""
        await self._pause_event.wait()
        cancellation_token.cancel()

    async def resume(self) -> None:
        """Resume the WebSurfer agent."""
        self.is_paused = False
        self._pause_event.clear()

    async def close(self) -> None:
        """
        Close the browser and the page.
        Should be called when the agent is no longer needed.
        """
        logger.info("Closing WebSurfer...")
        if self._page is not None:
            # If we're already exiting, we don't need to close the page again
            self._page = None
        await self._browser.__aexit__(None, None, None)
        if hasattr(self._model_client, "close"):
            await self._model_client.close()

    async def _set_debug_dir(self) -> None:
        assert self._page is not None
        if self.debug_dir is None:
            return
        if not os.path.isdir(self.debug_dir):
            os.mkdir(self.debug_dir)

    @property
    def produced_message_types(self) -> List[type[BaseChatMessage]]:
        """Get the types of messages produced by the agent."""
        return [MultiModalMessage]

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """Reset the WebSurfer agent's state."""
        if not self.did_lazy_init:
            return
        assert self._page is not None

        self._chat_history.clear()
        (
            reset_prior_metadata,
            reset_last_download,
        ) = await self._playwright_controller.visit_page(self._page, self.start_page)
        if reset_last_download and self._last_download is not None:
            self._last_download = None
        if reset_prior_metadata and self._prior_metadata_hash is not None:
            self._prior_metadata_hash = None

    async def on_messages(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        """
        Handle incoming messages and return a single response.

        Args:
            messages (Sequence[BaseChatMessage]): A sequence of incoming chat messages.
            cancellation_token (CancellationToken): Token to cancel the operation.

        Returns:
            Response: A single `Response` object generated from the incoming messages.
        """
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                return message
        raise AssertionError("The stream should have returned the final result.")

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseChatMessage | Response, None]:
        """
        Handle incoming messages and yield responses as a stream.

        Args:
            messages (Sequence[BaseChatMessage]): A sequence of incoming chat messages.
            cancellation_token (CancellationToken): Token to cancel the operation.

        Yields:
            AsyncGenerator: A stream of `BaseChatMessage` or `Response` objects.
        """
        # only keep last message and any MultiModalMessages
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
        for i, chat_message in enumerate(messages):
            if isinstance(chat_message, MultiModalMessage):
                self._chat_history.append(
                    UserMessage(
                        content=chat_message.content, source=chat_message.source
                    )
                )
            elif isinstance(chat_message, TextMessage) and i == len(messages) - 1:
                # Only append the last TextMessage
                self._chat_history.append(
                    UserMessage(
                        content=chat_message.content, source=chat_message.source
                    )
                )
        self._last_outside_message = content_to_str(self._chat_history[-1].content)
        self.inner_messages: List[BaseChatMessage] = []
        self.model_usage: List[RequestUsage] = []
        actions_proposed: List[str] = []
        observations: List[str] = []
        action_results: List[str] = []
        emited_responses: List[str] = []
        all_screenshots: List[bytes] = []
        if self.is_paused:
            yield Response(
                chat_message=TextMessage(
                    content="The WebSurfer is paused. Please resume to continue surfing the web.",
                    source=self.name,
                    metadata={"internal": "yes"},
                )
            )
        non_action_tools = ["stop_action", "answer_question"]

        # Set up the cancellation token for the code execution.
        llm_cancellation_token = CancellationToken()

        # Cancel the code execution if the handler's cancellation token is set.
        cancellation_token.add_callback(lambda: llm_cancellation_token.cancel())
        monitor_pause_task = asyncio.create_task(
            self.monitor_pause(llm_cancellation_token)
        )

        try:
            for _ in range(self.max_actions_per_step):
                # 1) Generate the next action to take
                if self.is_paused:
                    break
                response: str | List[FunctionCall] = ""
                need_execute_tool = False
                (
                    response,
                    rects,
                    tools,
                    element_id_mapping,
                    need_execute_tool,
                ) = await self._get_llm_response(
                    cancellation_token=llm_cancellation_token
                )

                final_usage = RequestUsage(
                    prompt_tokens=sum([u.prompt_tokens for u in self.model_usage]),
                    completion_tokens=sum(
                        [u.completion_tokens for u in self.model_usage]
                    ),
                )

                found_stop_action = False
                if not need_execute_tool:
                    summary_of_response = f"On the webpage '{str(self._page.title)}', we propose the following action: {response}"
                    self._chat_history.append(
                        AssistantMessage(
                            content=summary_of_response,
                            source=self.name,
                        )
                    )
                    assert isinstance(response, str)
                    emited_responses.append(response)
                    actions_proposed.append(summary_of_response)
                    observations.append("")
                    action_results.append("")
                    # 2 ) Emit the action proposed
                    yield Response(
                        chat_message=TextMessage(
                            content=emited_responses[-1],
                            source=self.name,
                            models_usage=final_usage,
                        ),
                        inner_messages=self.inner_messages,
                    )
                    break
                else:
                    # need to execute the tool(s)
                    assert isinstance(response, list)
                    for action in response:
                        assert isinstance(action, FunctionCall)
                        tool_call_name = action.name
                        tool_call_msg = f"{action.name}( {json.dumps(json.loads(action.arguments))} )"
                        tool_call_explanation = json.loads(action.arguments).get(
                            "explanation"
                        )
                        if tool_call_name == "answer_question":
                            tool_call_explanation = (
                                "Reading the entire page... " + tool_call_explanation
                            )
                        actions_proposed.append(tool_call_msg)
                        action_context = f'"{str(await self._page.title())}" (at {str(self._page.url)})'

                        self._chat_history.append(
                            AssistantMessage(
                                content=f"On the webpage {action_context}, we propose the following action: {tool_call_msg}",
                                source=self.name,
                            )
                        )

                        require_approval: bool = False
                        tool_args = json.loads(action.arguments)
                        assert isinstance(tool_args, dict)
                        if self.use_action_guard and self.action_guard is not None:
                            # find the tool schema given the name
                            tool_schema: ToolSchema | None = next(
                                (
                                    tool
                                    for tool in tools
                                    if tool["name"] == tool_call_name
                                ),
                                None,
                            )

                            baseline_needs_approval: MaybeRequiresApproval | None = None
                            if tool_schema is not None:
                                tool_metadata: ToolMetadata = get_tool_metadata(
                                    tool_call_name
                                )
                                baseline_needs_approval = tool_metadata.get(
                                    "requires_approval", "always"
                                )
                            else:
                                # If the tool schema is not found, default to a reasonable value
                                # In principle, this should be based on the action_guard policy
                                # e.g.: Always => Always, Never => Never, Permissive/Conservative => Maybe?
                                # Technically, Maybe always works here
                                baseline_needs_approval = "maybe"

                            assert baseline_needs_approval is not None
                            llm_guess = baseline_needs_approval  # only takes values "always" or "never"
                            # First check if require_approval is explicitly set in the tool arguments
                            # This is only for "maybe needs approval" actions
                            if "require_approval" in tool_args:
                                if tool_args["require_approval"]:
                                    llm_guess = "always"
                                else:
                                    llm_guess = "never"
                            require_approval = (
                                await self.action_guard.requires_approval(
                                    baseline_needs_approval,
                                    llm_guess,
                                    self._chat_history,
                                )
                            )

                        if tool_call_name == "stop_action":
                            tool_call_answer = json.loads(action.arguments).get(
                                "answer"
                            )
                            observations.append(tool_call_answer)
                            action_results.append(tool_call_answer)
                            emited_responses.append(tool_call_answer)
                            found_stop_action = True
                            yield Response(
                                chat_message=TextMessage(
                                    content=emited_responses[-1],
                                    source=self.name,
                                    models_usage=final_usage,
                                ),
                            )
                            break
                        if self.is_paused:
                            break
                        emited_responses.append(tool_call_explanation)
                        yield Response(
                            chat_message=TextMessage(
                                content=emited_responses[-1],
                                source=self.name,
                                models_usage=final_usage,
                            ),
                        )

                        if require_approval:
                            assert self.action_guard is not None
                            # tool_call_msg with (if exist) explanation
                            action_proposal = (
                                f"{tool_call_name}( {json.dumps(json.loads(action.arguments))} )"
                                if tool_call_explanation is None
                                else f"{tool_call_explanation}"
                            )

                            request_message = TextMessage(
                                source=self.name,
                                content=f"On the webpage {action_context}, we propose the following action: {action_proposal}",
                            )
                            # Preview action for tools that have target_id
                            if tool_call_name in [
                                "click",
                                "hover",
                                "select_option",
                                "upload_file",
                            ]:
                                if "target_id" in tool_args:
                                    target_id = str(tool_args["target_id"])  # type: ignore
                                    assert isinstance(target_id, str)
                                    if target_id in element_id_mapping:
                                        await (
                                            self._playwright_controller.preview_action(
                                                self._page,
                                                element_id_mapping[target_id],
                                            )
                                        )
                            elif (
                                tool_call_name == "input_text"
                                and "input_field_id" in tool_args
                            ):
                                input_field_id = str(tool_args["input_field_id"])  # type: ignore
                                assert isinstance(input_field_id, str)
                                if input_field_id in element_id_mapping:
                                    await self._playwright_controller.preview_action(
                                        self._page, element_id_mapping[input_field_id]
                                    )

                            approval = await self.action_guard.get_approval(
                                request_message,
                            )

                            if not approval:
                                # cleanup animations
                                await self._playwright_controller.cleanup_animations(
                                    self._page
                                )
                                # User did not approve the action
                                self._chat_history.append(
                                    AssistantMessage(
                                        content="The action was not approved.",
                                        source=self.name,
                                    )
                                )
                                yield Response(
                                    chat_message=TextMessage(
                                        content="The action was not approved.",
                                        source=self.name,
                                        models_usage=final_usage,
                                    ),
                                )
                                break

                        # execute the tool call
                        action_result = ""
                        try:
                            action_result = await self._execute_tool(
                                message=[action],
                                rects=rects,
                                tools=tools,
                                element_id_mapping=element_id_mapping,
                                cancellation_token=llm_cancellation_token,
                            )
                        except RuntimeError as e:
                            if "WebSurfer was paused" in str(e):
                                self.logger.info(f"Tool execution paused: {e}")
                                action_result = "Action was interrupted because WebSurfer was paused."
                            else:
                                self.logger.error(f"Runtime error executing tool: {e}")
                                action_result = f"Error occurred while executing action {tool_call_msg}: {e}"
                        except Exception as e:
                            self.logger.error(f"Error executing tool: {e}")
                            action_result = f"Error occurred while executing action {tool_call_msg}: {e}"
                        new_screenshot = (
                            await self._playwright_controller.get_screenshot(self._page)
                        )
                        if self.to_save_screenshots and self.debug_dir is not None:
                            current_timestamp = "_" + int(time.time()).__str__()
                            screenshot_png_name = (
                                "screenshot_raw" + current_timestamp + ".png"
                            )
                            PIL.Image.open(io.BytesIO(new_screenshot)).save(
                                os.path.join(self.debug_dir, screenshot_png_name)
                            )
                        all_screenshots.append(new_screenshot)
                        content: list[str | AGImage] = [
                            action_result,
                            AGImage.from_pil(
                                PIL.Image.open(io.BytesIO(new_screenshot))
                            ),
                        ]
                        emited_responses.append(action_result)
                        # 4) Emit the observation
                        yield Response(
                            chat_message=MultiModalMessage(
                                content=content,
                                source=self.name,
                                models_usage=final_usage,
                                metadata={
                                    "internal": "no",
                                    "type": "browser_screenshot",
                                },
                            ),
                            inner_messages=self.inner_messages,
                        )
                        (
                            message_content,
                            _,
                            metadata_hash,
                        ) = await self._playwright_controller.describe_page(
                            self._page,
                            get_screenshot=False,
                        )
                        observations.append(f"{action_result}\n\n{message_content}")
                        action_results.append(action_result)

                        self._chat_history.append(
                            UserMessage(
                                content=[
                                    f"Observation: {action_result}\n\n{message_content}",
                                    AGImage.from_pil(
                                        PIL.Image.open(io.BytesIO(new_screenshot))
                                    ),
                                ],
                                source=self.name,
                            )
                        )
                        if tool_call_name in non_action_tools:
                            found_stop_action = True
                            break
                    if found_stop_action:
                        break
        except asyncio.CancelledError:
            # If the task is cancelled, we respond with a message.
            yield Response(
                chat_message=TextMessage(
                    content="The task was cancelled by the user.",
                    source=self.name,
                    metadata={"internal": "yes"},
                ),
                inner_messages=self.inner_messages,
            )
        except Exception as e:
            yield Response(
                chat_message=TextMessage(
                    content=f"The WebSurfer encountered an error: {e}",
                    source=self.name,
                    metadata={"internal": "no"},
                ),
            )
            self.logger.error(f"Error in on_messages: {e}")
            pass
        finally:
            # Cancel the monitor task.
            monitor_pause_task.cancel()
            try:
                await monitor_pause_task
            except asyncio.CancelledError:
                pass

        # Prepare Final Response to other agents

        all_responses = (
            "The actions the websurfer performed are the following.\n"
            + "\n".join(
                [
                    f"\n Action: {action}\nObservation: {action_result}\n\n"
                    for action, action_result in zip(actions_proposed, action_results)
                ]
            )
        )
        try:
            # Ensure page is ready for final response
            assert self._page is not None, "Page should be initialized"
            (
                message_content,
                maybe_new_screenshot,
                metadata_hash,
            ) = await self._playwright_controller.describe_page(self._page)
            self._prior_metadata_hash = metadata_hash

            message_content = f"\n\n{all_responses}\n\n" + message_content
            assert maybe_new_screenshot is not None
            new_screenshot = maybe_new_screenshot

            content = [
                message_content,
                AGImage.from_pil(PIL.Image.open(io.BytesIO(new_screenshot))),
            ]

            final_usage = RequestUsage(
                prompt_tokens=sum([u.prompt_tokens for u in self.model_usage]),
                completion_tokens=sum([u.completion_tokens for u in self.model_usage]),
            )
            # Send the final response to other agents
            yield Response(
                chat_message=MultiModalMessage(
                    content=content,
                    source=self.name,
                    models_usage=final_usage,
                    metadata={"internal": "yes"},
                ),
                inner_messages=self.inner_messages,
            )
        except Exception as e:
            self.logger.error(f"Error in on_messages: {e}")
            final_message = f"{all_responses}\n\n Encountered an error while getting screenshot: {e}"
            yield Response(
                chat_message=TextMessage(
                    content=final_message,
                    source=self.name,
                    metadata={"internal": "no"},
                )
            )

    @staticmethod
    def _tools_to_names(tools: List[ToolSchema]) -> str:
        """Convert the list of tools to a string of names.

        Returns:
            str: A string of tool names separated by commas.
        """
        return "\n".join([t["name"] for t in tools])

    async def _get_llm_response(
        self, cancellation_token: Optional[CancellationToken] = None
    ) -> tuple[
        Union[str, List[FunctionCall]],
        Dict[str, InteractiveRegion],
        List[ToolSchema],
        Dict[str, str],
        bool,
    ]:
        """Generate the next action to take based on the current page state.

        Args:
            cancellation_token (CancellationToken, optional): Token to cancel the operation. Default: None

        Returns:
            Tuple containing:
                - str | List[FunctionCall]: The model's response (text or function calls)
                - Dict[str, InteractiveRegion]: Dictionary of interactive page elements
                - List[ToolSchema]: String of available tool names
                - Dict[str, str]: Mapping of element IDs
                - bool: Boolean indicating if tool execution is needed
        """
        try:
            assert self._page is not None
            await self._playwright_controller._ensure_page_ready(self._page)  # type: ignore
            assert (
                await self._playwright_controller.get_interactive_rects(self._page)
                is not None
            )
        except Exception as e:
            # open a new tab and point it to about:blank
            self.logger.error(f"Page is not accessible, creating a new one: {e}")
            assert self._context is not None
            self._page = await self._playwright_controller.create_new_tab(
                self._context, "about:blank"
            )

        # Clone the messages to give context, removing old screenshots
        history: List[LLMMessage] = []
        date_today = datetime.now().strftime("%Y-%m-%d")
        history.append(
            SystemMessage(
                content=WEB_SURFER_SYSTEM_MESSAGE.format(date_today=date_today)
            )
        )
        # Keep images only for user messages, remove from others
        filtered_history: List[LLMMessage] = []
        for msg in self._chat_history:
            if isinstance(msg, UserMessage) and msg.source in ["user", "user_proxy"]:
                filtered_history.append(msg)
            else:
                filtered_history.extend(remove_images([msg]))
        history.extend(filtered_history)

        # Ask the page for interactive elements, then prepare the state-of-mark screenshot
        rects = await self._playwright_controller.get_interactive_rects(self._page)
        # viewport = await self._playwright_controller.get_visual_viewport(self._page)
        screenshot = await self._playwright_controller.get_screenshot(self._page)
        som_screenshot, visible_rects, rects_above, rects_below, element_id_mapping = (
            add_set_of_mark(screenshot, rects, use_sequential_ids=True)
        )
        # element_id_mapping is a mapping of new ids to original ids in the page
        # we need to reverse it to get the original ids from the new ids
        # for each element we click, we need to use the original id
        reverse_element_id_mapping = {v: k for k, v in element_id_mapping.items()}
        rects = {reverse_element_id_mapping.get(k, k): v for k, v in rects.items()}

        if self.to_save_screenshots and self.debug_dir is not None:
            current_timestamp = "_" + int(time.time()).__str__()
            screenshot_png_name = "screenshot_som" + current_timestamp + ".png"
            som_screenshot.save(os.path.join(self.debug_dir, screenshot_png_name))
            self.logger.debug(
                WebSurferEvent(
                    source=self.name,
                    url=self._page.url,
                    message="Screenshot: " + screenshot_png_name,
                )
            )

        # Get the tabs information
        tabs_information_str = ""
        num_tabs = 1
        if not self.single_tab_mode and self._context is not None:
            num_tabs, tabs_information_str = await self.get_tabs_info()
            tabs_information_str = f"There are {num_tabs} tabs open. The tabs are as follows:\n{tabs_information_str}"

        # What tools are available?
        tools = self.default_tools.copy()

        # If not in single tab mode, always allow creating new tabs
        if not self.single_tab_mode:
            if TOOL_CREATE_TAB not in tools:
                tools.append(TOOL_CREATE_TAB)

        # If there are multiple tabs, we can switch between them and close them
        if not self.single_tab_mode and num_tabs > 1:
            tools.append(TOOL_SWITCH_TAB)
            # tools.append(TOOL_CLOSE_TAB)

        # We can scroll up
        # if viewport["pageTop"] > 5:
        #    tools.append(TOOL_PAGE_UP)

        # Can scroll down
        # if (viewport["pageTop"] + viewport["height"] + 5) < viewport["scrollHeight"]:
        #    tools.append(TOOL_PAGE_DOWN)

        # Add select_option tool only if there are option elements
        if any(rect.get("role") == "option" for rect in rects.values()):
            tools.append(TOOL_SELECT_OPTION)

        # Add upload_file tool only if there are file input elements
        # if any(rect.get("tag_name") == "input, type=file" for rect in rects.values()):
        #    tools.append(TOOL_UPLOAD_FILE)

        # Focus hint
        focused = await self._playwright_controller.get_focused_rect_id(self._page)
        focused = reverse_element_id_mapping.get(focused, focused)

        focused_hint = ""
        if focused:
            name = self._target_name(focused, rects)
            if name:
                name = f"(and name '{name}') "

            role = "control"
            try:
                role = rects[focused]["role"]
            except KeyError:
                pass

            focused_hint = f"\nThe {role} with ID {focused} {name}currently has the input focus.\n\n"

        # Everything visible
        visible_targets = (
            "\n".join(self._format_target_list(visible_rects, rects)) + "\n\n"
        )

        # Everything else
        other_targets: List[str] = []
        other_targets.extend(self._format_target_list(rects_above, rects))
        other_targets.extend(self._format_target_list(rects_below, rects))

        if len(other_targets) > 0:
            # Extract just the names from the JSON strings
            other_target_names: List[str] = []
            for target in other_targets:
                try:
                    target_dict = json.loads(target)
                    name = target_dict.get("name", "")
                    role = target_dict.get("role", "")
                    other_target_names.append(name if name else f"{role} control")
                except json.JSONDecodeError:
                    continue

            other_targets_str = (
                "Some additional valid interaction targets (not shown, you need to scroll to interact with them) include:\n"
                + ", ".join(other_target_names[:30])
                + "\n\n"
            )
        else:
            other_targets_str = ""

        tool_names = WebSurfer._tools_to_names(tools)

        webpage_text = await self._playwright_controller.get_visible_text(self._page)

        if not self.json_model_output:
            text_prompt = WEB_SURFER_TOOL_PROMPT.format(
                tabs_information=tabs_information_str,
                last_outside_message=self._last_outside_message,
                webpage_text=webpage_text,
                url=self._page.url,
                visible_targets=visible_targets,
                consider_screenshot="Consider the following screenshot of a web browser,"
                if self.is_multimodal
                else "Consider the following webpage",
                other_targets_str=other_targets_str,
                focused_hint=focused_hint,
                tool_names=tool_names,
            ).strip()
        else:
            text_prompt = WEB_SURFER_NO_TOOLS_PROMPT.format(
                tabs_information=tabs_information_str,
                last_outside_message=self._last_outside_message,
                webpage_text=webpage_text,
                url=self._page.url,
                visible_targets=visible_targets,
                consider_screenshot="Consider the following screenshot of a web browser,"
                if self.is_multimodal
                else "Consider the following webpage",
                other_targets_str=other_targets_str,
                focused_hint=focused_hint,
            ).strip()

        if self.is_multimodal:
            # Scale the screenshot for the MLM, and close the original
            scaled_som_screenshot = som_screenshot.resize(
                (self.MLM_WIDTH, self.MLM_HEIGHT)
            )
            screenshot_file = PIL.Image.open(io.BytesIO(screenshot))
            scaled_screenshot = screenshot_file.resize(
                (self.MLM_WIDTH, self.MLM_HEIGHT)
            )
            som_screenshot.close()
            screenshot_file.close()

            # Add the multimodal message and make the request
            history.append(
                UserMessage(
                    content=[
                        text_prompt,
                        AGImage.from_pil(scaled_som_screenshot),
                        AGImage.from_pil(scaled_screenshot),
                    ],
                    source=self.name,
                )
            )
        else:
            history.append(
                UserMessage(
                    content=text_prompt,
                    source=self.name,
                )
            )

        # Re-initialize model context to meet token limit quota
        try:
            await self._model_context.clear()
            for msg in history:
                await self._model_context.add_message(msg)
            token_limited_history = await self._model_context.get_messages()
        except Exception:
            token_limited_history = history

        if not self.json_model_output:
            create_args: Dict[str, Any] | None = None
            if self._model_client.model_info["family"] in [
                "gpt-4o",
                "gpt-41",
                "gpt-45",
                "o3",
                "o4",
            ]:
                create_args = {
                    "tool_choice": "required",
                }
                if self.multiple_tools_per_call:
                    create_args["parallel_tool_calls"] = True
            if create_args is not None:
                response = await self._model_client.create(
                    token_limited_history,
                    tools=tools,
                    cancellation_token=cancellation_token,
                    extra_create_args=create_args,
                )
            else:
                response = await self._model_client.create(
                    token_limited_history,
                    tools=tools,
                    cancellation_token=cancellation_token,
                )
        else:
            response = await self._model_client.create(
                token_limited_history,
                cancellation_token=cancellation_token,
            )
        self.model_usage.append(response.usage)
        self._last_download = None
        if not self.json_model_output:
            to_execute_tool = isinstance(response.content, list)
            return (
                response.content,
                rects,
                tools,
                element_id_mapping,
                to_execute_tool,
            )
        else:
            try:
                # check if first line is `json
                response_content = response.content
                assert isinstance(response_content, str)
                if response_content.startswith("```json"):
                    # remove first and last line
                    response_lines = response_content.split("\n")
                    response_lines = response_lines[1:-1]
                    response_content = "\n".join(response_lines)

                json_response = json.loads(response_content)
                tool_name = json_response["tool_name"]
                tool_args = json_response["tool_args"]
                tool_args["explanation"] = json_response["explanation"]
                function_call = FunctionCall(
                    id="json_response", name=tool_name, arguments=json.dumps(tool_args)
                )
                return [function_call], rects, tools, element_id_mapping, True
            except Exception as e:
                error_msg = f"Failed to parse JSON response: {str(e)}. Response was: {response.content}"
                return error_msg, rects, tools, element_id_mapping, False

    async def _check_url_and_generate_msg(self, url: str) -> Tuple[str, bool]:
        """Returns a message to caller if the URL is not allowed and a boolean indicating if the user has approved the URL."""
        # TODO: Hacky check to see if the URL was aborted. Find a better way to do this
        if url == "chrome-error://chromewebdata/":
            if self._last_rejected_url is not None:
                last_rejected_url = self._last_rejected_url
                self._last_rejected_url = None
                return (
                    f"I am not allowed to access the website {last_rejected_url} because it is not in the list of websites I can access and the user has declined to approve it.",
                    False,
                )

        if self._url_status_manager.is_url_blocked(url):
            return (
                f"I am not allowed to access the website {url} because has been blocked.",
                False,
            )

        if not self._url_status_manager.is_url_allowed(url):
            if not self._url_status_manager.is_url_rejected(url):
                # tldextract will only recombine entries with valid, registered hostnames. We'll just use the straight url for anything else.
                domain = tldextract.extract(url).fqdn
                if not domain:
                    domain = url
                response = False
                if self.action_guard is not None:
                    # The content string here is important because the UI is checking for specific wording to detect the URL approval request
                    request_message = TextMessage(
                        source=self.name,
                        content=f"The website {url} is not allowed. Would you like to allow the domain {domain} for this session?",
                    )
                    response = await self.action_guard.get_approval(request_message)
                if response:
                    self._url_status_manager.set_url_status(domain, URL_ALLOWED)
                    return (
                        "",
                        True,
                    )
                else:
                    self._url_status_manager.set_url_status(domain, URL_REJECTED)

            self._last_rejected_url = url
            return (
                f"I am not allowed to access the website {url} because it is not in the list of websites I can access and the user has declined to allow it.",
                False,
            )
        return "", True

    async def _execute_tool_stop_action(self, args: Dict[str, Any]) -> str:
        answer = cast(str, args.get("answer"))
        return answer

    async def _execute_tool_visit_url(self, args: Dict[str, Any]) -> str:
        url = cast(str, args.get("url"))
        ret, approved = await self._check_url_and_generate_msg(url)
        if not approved:
            return ret

        action_description = f"I typed '{url}' into the browser address bar."
        assert self._page is not None
        if url.startswith(("https://", "http://", "file://", "about:")):
            (
                reset_prior_metadata,
                reset_last_download,
            ) = await self._playwright_controller.visit_page(self._page, url)
        # If the argument contains a space, treat it as a search query
        elif " " in url:
            search_url, domain = self._get_search_url(url)
            ret, approved = await self._check_url_and_generate_msg(domain)
            if not approved:
                return ret
            (
                reset_prior_metadata,
                reset_last_download,
            ) = await self._playwright_controller.visit_page(
                self._page,
                search_url,
            )
        # Otherwise, prefix with https://
        else:
            (
                reset_prior_metadata,
                reset_last_download,
            ) = await self._playwright_controller.visit_page(
                self._page, "https://" + url
            )

        if reset_last_download:
            self._last_download = None
        if reset_prior_metadata:
            self._prior_metadata_hash = None

        return action_description

    async def _execute_tool_history_back(self, args: Dict[str, Any]) -> str:
        assert self._page is not None
        response = await self._playwright_controller.go_back(self._page)
        if response:
            return "I clicked the browser back button."
        return "No previous page in the browser history or couldn't navigate back."

    async def _execute_tool_refresh_page(self, args: Dict[str, Any]) -> str:
        assert self._page is not None
        await self._playwright_controller.refresh_page(self._page)
        return "I refreshed the current page."

    async def _execute_tool_web_search(self, args: Dict[str, Any]) -> str:
        assert self._page is not None
        query = cast(str, args.get("query"))
        search_url, domain = self._get_search_url(query)
        ret, approved = await self._check_url_and_generate_msg(domain)
        if not approved:
            return ret
        action_description = f"I typed '{query}' into the browser search bar."
        (
            reset_prior_metadata,
            reset_last_download,
        ) = await self._playwright_controller.visit_page(
            self._page,
            search_url,
        )
        if reset_last_download:
            self._last_download = None
        if reset_prior_metadata:
            self._prior_metadata_hash = None
        return action_description

    async def _execute_tool_page_up(self, args: Dict[str, Any]) -> str:
        assert self._page is not None
        await self._playwright_controller.page_up(self._page)
        return "I scrolled up one page in the browser."

    async def _execute_tool_page_down(self, args: Dict[str, Any]) -> str:
        assert self._page is not None
        await self._playwright_controller.page_down(self._page)
        return "I scrolled down one page in the browser."

    async def _execute_tool_scroll_down(self, args: Dict[str, Any]) -> str:
        assert self._page is not None
        pixels = int(args.get("pixels", 400))
        await self._playwright_controller.scroll_mousewheel(self._page, "down", pixels)
        return f"I scrolled down {pixels} pixels in the browser."

    async def _execute_tool_scroll_up(self, args: Dict[str, Any]) -> str:
        assert self._page is not None
        pixels = int(args.get("pixels", 400))
        await self._playwright_controller.scroll_mousewheel(self._page, "up", pixels)
        return f"I scrolled up {pixels} pixels in the browser."

    async def _execute_tool_click(
        self,
        args: Dict[str, Any],
        rects: Dict[str, InteractiveRegion],
        element_id_mapping: Dict[str, str],
    ) -> str:
        assert "target_id" in args
        target_id: str = str(args["target_id"])
        target_name = self._target_name(target_id, rects)
        target_id = element_id_mapping[target_id]

        action_description = (
            f"I clicked '{target_name}'." if target_name else "I clicked the control."
        )
        assert self._context is not None
        assert self._page is not None
        new_page_tentative = await self._playwright_controller.click_id(
            self._context, self._page, target_id
        )
        if new_page_tentative is not None:
            new_url = new_page_tentative.url
            self._page = new_page_tentative
            # Ensure the new page is visible and active
            await self._page.bring_to_front()
            self._prior_metadata_hash = None
            ret, approved = await self._check_url_and_generate_msg(new_url)
            if not approved:
                return ret

        return action_description

    async def _execute_tool_click_full(
        self,
        args: Dict[str, Any],
        rects: Dict[str, InteractiveRegion],
        element_id_mapping: Dict[str, str],
    ) -> str:
        assert "target_id" in args
        target_id: str = str(args["target_id"])
        target_name = self._target_name(target_id, rects)
        target_id = element_id_mapping[target_id]

        hold = float(args.get("hold", 0.0))
        button = str(args.get("button", "left"))
        button = cast(Literal["left", "right"], button)
        action_description = (
            f"I clicked '{target_name}' with button '{button}' and hold {hold} seconds."
            if target_name
            else f"I clicked the control with button '{button}' and hold {hold} seconds."
        )
        assert self._context is not None
        assert self._page is not None
        new_page_tentative = await self._playwright_controller.click_id(
            self._context, self._page, target_id, hold=hold, button=button
        )
        if new_page_tentative is not None:
            new_url = new_page_tentative.url
            self._page = new_page_tentative
            # Ensure the new page is visible and active
            await self._page.bring_to_front()
            self._prior_metadata_hash = None
            ret, approved = await self._check_url_and_generate_msg(new_url)
            if not approved:
                return ret

        return action_description

    async def _execute_tool_input_text(
        self,
        args: Dict[str, Any],
        rects: Dict[str, InteractiveRegion],
        element_id_mapping: Dict[str, str],
    ) -> str:
        assert "input_field_id" in args
        assert "text_value" in args
        assert "delete_existing_text" in args
        input_field_id: str = str(args["input_field_id"])
        input_field_name = self._target_name(input_field_id, rects)
        input_field_id = element_id_mapping[input_field_id]

        text_value = str(args.get("text_value"))
        press_enter = bool(args.get("press_enter", True))
        delete_existing_text = bool(args.get("delete_existing_text"))

        action_description = (
            f"I typed '{text_value}' into '{input_field_name}'."
            if input_field_name
            else f"I typed '{text_value}'."
        )
        assert self._page is not None
        await self._playwright_controller.fill_id(
            self._page,
            input_field_id,
            text_value,
            press_enter,
            delete_existing_text,
        )
        return action_description

    async def _execute_tool_answer_question(
        self,
        args: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:
        assert "question" in args
        question: str = args["question"]
        return await self._summarize_page(
            question=question, cancellation_token=cancellation_token
        )

    async def _execute_tool_summarize_page(
        self,
        args: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:
        return await self._summarize_page(cancellation_token=cancellation_token)

    async def _execute_tool_hover(
        self,
        args: Dict[str, Any],
        rects: Dict[str, InteractiveRegion],
        element_id_mapping: Dict[str, str],
    ) -> str:
        target_id = str(args.get("target_id"))
        target_name = self._target_name(target_id, rects)
        target_id = element_id_mapping.get(target_id, target_id)

        action_description = (
            f"I hovered over '{target_name}'."
            if target_name
            else "I hovered over the control."
        )
        assert self._page is not None
        await self._playwright_controller.hover_id(self._page, target_id)
        return action_description

    async def _execute_tool_sleep(self, args: Dict[str, Any]) -> str:
        assert self._page is not None
        duration = cast(int, args.get("duration", 3))
        await self._playwright_controller.sleep(self._page, duration)
        return f"I waited {duration} seconds."

    async def _execute_tool_select_option(
        self,
        args: Dict[str, Any],
        rects: Dict[str, InteractiveRegion],
        element_id_mapping: Dict[str, str],
    ) -> str:
        target_id = str(args.get("target_id"))
        target_name = self._target_name(target_id, rects)
        target_id = element_id_mapping.get(target_id, target_id)

        action_description = (
            f"I selected the option '{target_name}'."
            if target_name
            else "I selected the option."
        )
        assert self._context is not None
        assert self._page is not None
        new_page_tentative = await self._playwright_controller.select_option(
            self._context, self._page, target_id
        )
        if new_page_tentative is not None:
            new_url = new_page_tentative.url
            ret, approved = await self._check_url_and_generate_msg(new_url)
            if not approved:
                return ret
            self._page = new_page_tentative
            # Ensure the new page is visible and active
            await self._page.bring_to_front()
            self._prior_metadata_hash = None

        return action_description

    async def _execute_tool_create_tab(self, args: Dict[str, Any]) -> str:
        url: str = cast(str, args.get("url"))
        ret, approved = await self._check_url_and_generate_msg(url)
        if not approved:
            return ret
        assert self._context is not None
        action_description = f"I created a new tab and navigated to '{url}'."
        new_page = await self._playwright_controller.create_new_tab(self._context, url)
        self._page = new_page
        # Ensure the new page is visible and active
        await self._page.bring_to_front()
        self._prior_metadata_hash = None
        return action_description

    async def _execute_tool_switch_tab(self, args: Dict[str, Any]) -> str:
        assert self._context is not None
        try:
            assert "tab_index" in args
            tab_index = int(cast(str, args["tab_index"]))
            new_page = await self._playwright_controller.switch_tab(
                self._context, tab_index
            )
            self._page = new_page
            # Ensure the switched tab is visible and active
            await self._page.bring_to_front()
            self._prior_metadata_hash = None
            return f"I switched to tab {tab_index}."
        except (ValueError, TypeError) as e:
            return f"Invalid tab index: {e}"

    async def _execute_tool_close_tab(self, args: Dict[str, Any]) -> str:
        try:
            assert self._context is not None
            assert "tab_index" in args
            tab_index = int(cast(str, args["tab_index"]))
            new_page = await self._playwright_controller.close_tab(
                self._context, tab_index
            )
            self._page = new_page
            # Ensure the new active tab is visible and active
            await self._page.bring_to_front()
            self._prior_metadata_hash = None
            return f"I closed tab {tab_index} and switched to an adjacent tab."
        except (ValueError, TypeError) as e:
            return f"Invalid tab index: {e}"

    async def _execute_tool_upload_file(
        self,
        args: Dict[str, Any],
        rects: Dict[str, InteractiveRegion],
        element_id_mapping: Dict[str, str],
    ) -> str:
        target_id = str(args.get("target_id"))
        assert self.downloads_folder is not None
        file_path = self.downloads_folder + "/" + str(args.get("file_path"))
        target_name = self._target_name(target_id, rects)

        target_id = element_id_mapping.get(target_id, target_id)
        if target_name:
            action_description = (
                f"I uploaded the file '{file_path}' to '{target_name}'."
            )
        else:
            action_description = f"I uploaded the file '{file_path}'."
        assert self._page is not None
        await self._playwright_controller.upload_file(self._page, target_id, file_path)

        return action_description

    async def _execute_tool_keypress(self, args: Dict[str, Any]) -> str:
        """Execute the keypress tool to press one or more keyboard keys in sequence.

        Args:
            args (Dict[str, Any]): The arguments for the keypress tool.
                keys (List[str]): List of keys to press in sequence.

        Returns:
            str: A message describing what was done.
        """
        assert self._page is not None, "Browser page is not initialized"
        keys = args["keys"]
        await self._playwright_controller.keypress(self._page, keys)
        keys_str = ", ".join(f"'{k}'" for k in keys)
        return f"Pressed the following keys in sequence: {keys_str}"

    async def _execute_tool(
        self,
        message: List[FunctionCall],
        rects: Dict[str, InteractiveRegion],
        tools: List[ToolSchema],
        element_id_mapping: Dict[str, str],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:
        """Execute a tool action in the browser.

        Args:
            message (List[FunctionCall]): List of function calls from the model, should be a single function call
            rects (Dict[str, InteractiveRegion]): Dictionary of interactive page elements
            tools (List[ToolSchema]): List of available tool schemas
            element_id_mapping (Dict[str, str]): Mapping of element IDs
            cancellation_token (CancellationToken, optional): Token to cancel the operation. Default: None

        Returns:
            str: Description of the action taken

        Raises:
            ValueError: If an unknown tool is specified
            RuntimeError: If the WebSurfer was paused during tool execution
        """
        assert self._context is not None, "Browser context is not initialized"
        assert len(message) == 1, "Expected exactly one function call"
        assert self._page is not None

        name = message[0].name
        args = json.loads(message[0].arguments)

        self.logger.debug(
            WebSurferEvent(
                source=self.name,
                url=self._page.url,
                action=name,
                arguments=args,
                message=f"{name}( {json.dumps(args)} )",
            )
        )
        self.inner_messages.append(
            TextMessage(content=f"{name}( {json.dumps(args)} )", source=self.name)
        )

        # Convert tool name to function name (e.g. "visit_url" -> "_execute_tool_visit_url")
        tool_func_name = f"_execute_tool_{name}"
        tool_func = getattr(self, tool_func_name, None)

        if tool_func is None:
            tool_names = WebSurfer._tools_to_names(tools)

            raise ValueError(
                f"Unknown tool '{name}'. Please choose from:\n\n{tool_names}"
            )

        # Create the appropriate arguments based on the tool's requirements
        tool_kwargs = {"args": args}
        if name in [
            "click",
            "input_text",
            "hover",
            "select_option",
            "upload_file",
            "click_full",
        ]:
            tool_kwargs.update(
                {"rects": rects, "element_id_mapping": element_id_mapping}
            )
        if name in ["answer_question", "summarize_page"]:
            tool_kwargs["cancellation_token"] = cancellation_token

        # Start a new task to execute the tool.
        execute_tool_task = asyncio.create_task(tool_func(**tool_kwargs))

        # Start a new task to wait for the pause event and cancel the tool execution if paused.
        async def wait_for_pause_event() -> None:
            await self._pause_event.wait()
            if self._pause_event.is_set():
                execute_tool_task.cancel()

        wait_for_pause_task = asyncio.create_task(wait_for_pause_event())

        # Wait for the tool execution to complete or be cancelled.
        try:
            action_description = await execute_tool_task
            assert isinstance(action_description, str)
            # Handle downloads
            if self._last_download is not None and self.downloads_folder is not None:
                action_description += f"\n\nSuccessfully downloaded '{self._last_download.suggested_filename}' to local path: {self.downloads_folder}"
        except asyncio.CancelledError:
            # If the task was cancelled, we can handle it here if needed
            # Clean up any cursor animations or highlights that were added by animate_actions.
            assert self._page is not None
            await self._playwright_controller.cleanup_animations(self._page)
            return f"WebSurfer was paused, action '{name}' was cancelled."
        finally:
            # Cancel the wait_for_pause_task if it is still running
            if not wait_for_pause_task.done():
                wait_for_pause_task.cancel()
        # cleanup animations
        await self._playwright_controller.cleanup_animations(self._page)
        return action_description

    def _target_name(
        self, target: str, rects: Dict[str, InteractiveRegion]
    ) -> str | None:
        """Get the accessible name of a target element.

        Args:
            target (str): ID of the target element
            rects (Dict[str, InteractiveRegion]): Dictionary of interactive page elements

        Returns:
            str | None: The aria name of the element if available, None otherwise
        """
        try:
            return rects[target]["aria_name"].strip()
        except KeyError:
            return None

    def _format_target_list(
        self, ids: List[str], rects: Dict[str, InteractiveRegion]
    ) -> List[str]:
        """
        Format the list of targets in the webpage as a string to be used in the agent's prompt.
        """
        targets: List[str] = []
        for r in list(set(ids)):
            if r in rects:
                # Get the role
                aria_role = rects[r].get("role", "").strip()
                if len(aria_role) == 0:
                    aria_role = rects[r].get("tag_name", "").strip()

                # Get the name
                aria_name = re.sub(
                    r"[\n\r]+", " ", rects[r].get("aria_name", "")
                ).strip()

                # What are the actions?
                actions = ['"click", "hover"']
                if (
                    rects[r]["role"] in ["textbox", "searchbox", "combobox"]
                    or rects[r].get("tag_name") in ["input", "textarea", "search"]
                    or rects[r].get("contenteditable") == "true"
                ):
                    actions.append('"input_text"')
                # if the role is option, add "select" to the actions
                if rects[r]["role"] == "option":
                    actions = ['"select_option"']
                # check if the role is file input
                if aria_role == "input, type=file":
                    actions = ['"upload_file"']
                actions_str = "[" + ",".join(actions) + "]"
                # limit  name to maximum 100 characters
                aria_name = aria_name[:100]
                targets.append(
                    f'{{"id": {r}, "name": "{aria_name}", "role": "{aria_role}", "tools": {actions_str} }}'
                )
        sorted_targets = sorted(
            targets, key=lambda x: int(x.split(",")[0].split(":")[1])
        )

        return sorted_targets

    async def _get_ocr_text(
        self,
        image: Union[bytes, io.BufferedIOBase, PIL.Image.Image],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:
        """Extract text from an image using OCR via the LLM.

        Args:
            image (bytes | io.BufferedIOBase | PIL.Image.Image): Image data as bytes, file or PIL Image
            cancellation_token (CancellationToken, optional): Token to cancel the operation. Default: None

        Returns:
            str: Extracted text from the image
        """
        scaled_screenshot = None
        if isinstance(image, PIL.Image.Image):
            scaled_screenshot = image.resize((self.MLM_WIDTH, self.MLM_HEIGHT))
        else:
            pil_image = None
            if not isinstance(image, io.BufferedIOBase):
                pil_image = PIL.Image.open(io.BytesIO(image))
            else:
                pil_image = PIL.Image.open(cast(BinaryIO, image))
            scaled_screenshot = pil_image.resize((self.MLM_WIDTH, self.MLM_HEIGHT))
            pil_image.close()

        # Add the multimodal message and make the request
        messages: List[LLMMessage] = []
        messages.append(
            UserMessage(
                content=[
                    WEB_SURFER_OCR_PROMPT,
                    AGImage.from_pil(scaled_screenshot),
                ],
                source=self.name,
            )
        )
        response = await self._model_client.create(
            messages, cancellation_token=cancellation_token
        )
        self.model_usage.append(response.usage)
        scaled_screenshot.close()
        assert isinstance(response.content, str)
        return response.content

    async def _summarize_page(
        self,
        question: Optional[str] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:
        """Generate a summary of the current page content.

        Args:
            question (str, optional): Optional specific question to answer about the page. Default: None
            cancellation_token (CancellationToken, optional): Token to cancel the operation. Default: None

        Returns:
            str: Summary text or answer to the question
        """
        assert self._page is not None

        # Get page content and title
        page_markdown: str = await self._playwright_controller.get_page_markdown(
            self._page
        )
        title: str = await self._page.title() or self._page.url

        # Take a screenshot and scale it
        screenshot = await self._playwright_controller.get_screenshot(self._page)
        pil_image = PIL.Image.open(io.BytesIO(screenshot))
        scaled_screenshot = pil_image.resize((self.MLM_WIDTH, self.MLM_HEIGHT))
        pil_image.close()
        ag_image = AGImage.from_pil(scaled_screenshot)

        # Prepare the system prompt and user prompt
        messages: List[LLMMessage] = []
        messages.append(SystemMessage(content=WEB_SURFER_QA_SYSTEM_MESSAGE))

        # Create the prompt with the question
        prompt = WEB_SURFER_QA_PROMPT(title, question)

        # Truncate the page content if needed to fit within token limits
        tokenizer = tiktoken.encoding_for_model("gpt-4o")
        prompt_tokens = len(tokenizer.encode(prompt))
        # Reserve tokens for the image (SCREENSHOT_TOKENS) and some buffer for the response
        max_content_tokens = 128000 - self.SCREENSHOT_TOKENS - prompt_tokens - 1000

        if max_content_tokens <= 0:
            # If we don't have enough tokens, just use a minimal prompt
            content = prompt
        else:
            # Truncate the page content to fit within the token limit
            content_tokens = tokenizer.encode(page_markdown)
            if len(content_tokens) > max_content_tokens:
                truncated_content = tokenizer.decode(
                    content_tokens[:max_content_tokens]
                )
                content = f"Page content (truncated):\n{truncated_content}\n\n{prompt}"
            else:
                content = f"Page content:\n{page_markdown}\n\n{prompt}"

        # Create the message with the content and image
        messages.append(
            UserMessage(
                content=[content, ag_image],
                source=self.name,
            )
        )

        # Generate the response
        response = await self._model_client.create(
            messages, cancellation_token=cancellation_token
        )
        self.model_usage.append(response.usage)
        scaled_screenshot.close()

        assert isinstance(response.content, str)
        return response.content

    async def describe_current_page(self) -> tuple[str, Union[bytes, None], str]:
        """Get a description of the current page including content, screenshot and metadata hash.

        Returns:
            Tuple containing:
            - str: String description of the page content
            - bytes | None: Screenshot of the page as bytes
            - str: Hash of the page metadata
        """
        assert self._page is not None
        return await self._playwright_controller.describe_page(self._page)

    async def get_page_title_url(self) -> tuple[str, str]:
        """Get the title and URL of the current page.

        Returns:
            Tuple containing:
            - str: String title of the page
            - str: String URL of the page
        """
        assert self._page is not None
        return await self._page.title(), self._page.url

    async def get_tabs_info(self) -> Tuple[int, str]:
        """Returns the number of tabs and a newline delineated string describing each of them. An example of the string is:

        Tab 0: <Tab_Title> (<URL>) [CURRENTLY SHOWN] [CONTROLLED]
        Tab 1: <Tab_Title> (<URL>)
        Tab 2: <Tab_Title> (<URL>)

        Returns:
            Tuple containing:
            - int: The number of tabs
            - str: String describing each tab.
        """
        num_tabs = 1
        assert self._context is not None
        assert self._page is not None
        tabs_information = await self._playwright_controller.get_tabs_information(
            self._context,
            self._page,  # Pass the current page
        )
        num_tabs = len(tabs_information)
        tabs_information_str = "\n".join(
            [
                f"Tab {tab['index']}: {tab['title']} ({tab['url']})"
                f"{' [CURRENTLY SHOWN]' if tab['is_active'] else ''}"
                f"{' [CONTROLLED]' if tab['is_controlled'] else ''}"
                for tab in tabs_information
            ]
        )
        return num_tabs, tabs_information_str

    def _to_config(self) -> WebSurferConfig:
        return WebSurferConfig(
            name=self.name,
            model_client=self._model_client.dump_component(),
            browser=self._browser.dump_component(),
            downloads_folder=self.downloads_folder,
            description=self.description,
            debug_dir=self.debug_dir,
            start_page=self.start_page,
            animate_actions=self.animate_actions,
            to_save_screenshots=self.to_save_screenshots,
            max_actions_per_step=self.max_actions_per_step,
            to_resize_viewport=self.to_resize_viewport,
            url_statuses=self._url_status_manager.url_statuses,
            single_tab_mode=self.single_tab_mode,
            json_model_output=self.json_model_output,
            multiple_tools_per_call=self.multiple_tools_per_call,
            viewport_height=self.viewport_height,
            viewport_width=self.viewport_width,
            use_action_guard=self.use_action_guard,
            search_engine=self.search_engine,
        )

    @classmethod
    def _from_config(cls, config: WebSurferConfig) -> Self:
        return cls(
            name=config.name,
            model_client=ChatCompletionClient.load_component(config.model_client),
            browser=PlaywrightBrowser.load_component(config.browser),
            model_context_token_limit=config.model_context_token_limit,
            downloads_folder=config.downloads_folder,
            description=config.description or cls.DEFAULT_DESCRIPTION,
            debug_dir=config.debug_dir,
            start_page=config.start_page or cls.DEFAULT_START_PAGE,
            animate_actions=config.animate_actions,
            to_save_screenshots=config.to_save_screenshots,
            to_resize_viewport=config.to_resize_viewport,
            url_statuses=config.url_statuses,
            url_block_list=config.url_block_list,
            single_tab_mode=config.single_tab_mode,
            json_model_output=config.json_model_output,
            multiple_tools_per_call=config.multiple_tools_per_call,
            viewport_height=config.viewport_height,
            viewport_width=config.viewport_width,
            use_action_guard=config.use_action_guard,
            search_engine=config.search_engine,
        )

    @classmethod
    def from_config(cls, config: WebSurferConfig) -> Self:
        return cls._from_config(config)

    async def save_state(self, save_browser: bool = True) -> Mapping[str, Any]:
        """Save the current state of the WebSurfer.
        Args:
            save_browser (bool): Whether to save the browser state. Defaults to True.

        Returns:
            A dictionary containing the chat history and browser state
        """

        if not self.did_lazy_init:
            state = WebSurferState(
                chat_history=self._chat_history,
                browser_state=None,  # No browser state when not initialized
            )
            return state.model_dump()

        assert self._context is not None

        browser_state = None
        if save_browser:
            # Get the browser state and convert it to a dict
            browser_state = await save_browser_state(self._context, self._page)

        # Create and return the WebSurfer state
        state = WebSurferState(
            chat_history=self._chat_history,
            browser_state=browser_state,
        )
        return state.model_dump()

    async def load_state(
        self, state: Mapping[str, Any], load_browser: bool = True
    ) -> None:
        """
        Load a previously saved state.

        Args:
            state: Dictionary containing the state to load
        """
        # Validate and convert the state to a WebSurferState
        web_surfer_state = WebSurferState.model_validate(state)

        # Update the chat history
        self._chat_history = web_surfer_state.chat_history

        # Load the browser state if it exists and load_browser is True
        if load_browser and web_surfer_state.browser_state is not None:
            await self.lazy_init()
            assert self._context is not None
            await load_browser_state(self._context, web_surfer_state.browser_state)

            # Update the controlled page to the active tab
            if self._context and self._context.pages:
                active_index = min(
                    web_surfer_state.browser_state.activeTabIndex,
                    len(self._context.pages) - 1,
                )
                self._page = self._context.pages[active_index]
