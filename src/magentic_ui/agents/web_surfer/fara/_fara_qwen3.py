"""FaraQwen3Agent — Core web automation agent using Qwen3 vision-language model.

Uses the OpenAI SDK directly. Operates on the BrowserEnvironment ABC.

This is the base agent with 11 actions. FaraQwen3NextAgent extends it with
18 actions, cursor tracking, and dynamic mode selection.
"""

from __future__ import annotations

import ast
import asyncio
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Tuple
from urllib.parse import quote_plus

import openai
from loguru import logger
from PIL import Image
from pydantic import BaseModel
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ...._ai_client import create_openai_client, is_retryable_model_error
from ._prompts import get_computer_use_system_prompt
from ._types import BrowserEnvironment, ImageObj, LLMMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_url_query(url: str) -> str:
    return url.split("?", 1)[0]


def _get_trimmed_url(url: str, max_len: int) -> str:
    trimmed = _strip_url_query(url)
    if len(trimmed) > max_len:
        trimmed = trimmed[:max_len] + " ..."
    return trimmed


def _merge_chat_template_kwargs(
    extra_body: dict[str, Any] | None,
    chat_template_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Return a new ``extra_body`` with ``chat_template_kwargs`` overlaid.

    Preserves any other keys the caller already set on ``extra_body`` and
    any unrelated entries inside ``chat_template_kwargs``. Caller-provided
    values for the same chat-template key win over ``chat_template_kwargs``
    so callers can opt out per-call.
    """
    merged_extra_body: dict[str, Any] = dict(extra_body or {})
    existing_ctk: dict[str, Any] = dict(
        merged_extra_body.get("chat_template_kwargs") or {}
    )
    for key, value in chat_template_kwargs.items():
        existing_ctk.setdefault(key, value)
    merged_extra_body["chat_template_kwargs"] = existing_ctk
    return merged_extra_body


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class FaraQwen3AgentConfig(BaseModel):
    """Configuration for FaraQwen3Agent."""

    name: str = "fara"
    client_config: dict[str, Any] | None = None
    start_page: str = "about:blank"
    max_rounds: int = 10
    max_n_images: int = 3
    fn_call_template: str = "fara-qwen35vl"
    # Qwen3.5 hybrid-thinking models reason in prose by default and stop
    # emitting <tool_call>. We override via vLLM `chat_template_kwargs`
    # to force the non-thinking generation prefix. Set False if running
    # on a backbone whose chat template does not honor `enable_thinking`
    # (e.g. legacy Qwen3-VL).
    disable_thinking: bool = True
    include_input_text_key_args: bool = True
    viewport_width: int = 1440
    viewport_height: int = 900
    min_pixels: int = 3136
    max_pixels: int = 12845056


# ---------------------------------------------------------------------------
# Mutable state
# ---------------------------------------------------------------------------


@dataclass
class FaraQwen3AgentState:
    """Mutable state that persists across rounds."""

    chat_history: list[LLMMessage] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    num_actions: int = 0
    current_step: int = 0
    mlm_width: int = 0
    mlm_height: int = 0
    original_user_message_indices: set[int] = field(default_factory=set)


# ---------------------------------------------------------------------------
# FaraQwen3Agent
# ---------------------------------------------------------------------------


class FaraQwen3Agent:
    """Web automation agent with 11 actions, DISPLAY_SIZE=1000 coordinate space.

    Uses :class:`BrowserEnvironment` so the agent never touches Playwright
    directly.
    """

    # Class constants
    DEFAULT_START_PAGE = "https://www.bing.com/"
    DISPLAY_SIZE = 1000
    PATCH_SIZE = 16
    MERGE_SIZE = 2
    USER_MESSAGE = "Here is the next screenshot. Think about what to do next."
    MAX_URL_LENGTH = 100

    def __init__(
        self,
        config: FaraQwen3AgentConfig | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if config is None:
            config = self._get_config_class()(**kwargs)
        elif isinstance(config, dict):
            config = self._get_config_class()(**config)
        self.config: FaraQwen3AgentConfig = config
        self._client: openai.AsyncOpenAI | None = None
        self._model: str | None = None
        self._state: FaraQwen3AgentState | None = None
        self._pending_observation: str = ""

    @classmethod
    def _get_config_class(cls) -> type[FaraQwen3AgentConfig]:
        return FaraQwen3AgentConfig

    @property
    def mlm_processor_im_cfg(self) -> dict[str, int]:
        return {
            "min_pixels": self.config.min_pixels,
            "max_pixels": self.config.max_pixels,
            "patch_size": self.PATCH_SIZE,
            "merge_size": self.MERGE_SIZE,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize client and state. Call before run()."""
        self._state = FaraQwen3AgentState(
            mlm_width=self.config.viewport_width,
            mlm_height=self.config.viewport_height,
        )
        if self.config.client_config is None:
            raise ValueError("client_config must be provided")
        cfg = self.config.client_config
        self._client, _ = create_openai_client(cfg)
        self._model = cfg.get("model") or "microsoft/Fara-7B"

    async def close(self) -> None:
        """Cleanup.

        Closes the underlying ``AsyncOpenAI`` HTTP client before
        dropping the reference so the httpx connection pool / file
        descriptors are released deterministically. Without this,
        long-running processes (server mode) leak FDs across sessions.
        """
        if self._client is not None:
            await self._client.close()
        self._state = None
        self._client = None
        self._model = None

    # ------------------------------------------------------------------
    # run() — supports fresh start and resume
    # ------------------------------------------------------------------

    async def run(
        self,
        env: BrowserEnvironment,
        task: str,
        user_response: str = "",
        output_dir: str | Path | None = None,
    ) -> Tuple[str, List[str], List[str]]:
        """Run the agent loop.

        Supports resuming: if ``_state.chat_history`` is already populated,
        skips fresh-start init and uses ``user_response`` as the pending
        user reply (WAITING_FOR_USER pattern).

        Args:
            env: Browser environment to operate on.
            task: Task instruction string.
            user_response: User reply when resuming after ask_user_question.
            output_dir: Optional directory to save pre/post screenshots.

        Returns:
            (final_answer, all_raw_responses, all_action_descriptions)
        """
        assert self._state is not None, "Call initialize() before run()"

        pending_user_response = ""
        scaled_screenshot: Image.Image | None = None
        if self._state.chat_history:
            # Continuation after WAITING_FOR_USER
            pending_user_response = user_response
            start_step = self._state.current_step
        else:
            # Fresh start
            scaled_screenshot = await self._get_scaled_screenshot(env)
            await self._save_screenshot(env, output_dir, "screenshot_0_pre.png")
            self._state.chat_history.append(
                LLMMessage(
                    role="user",
                    content=[ImageObj.from_pil(scaled_screenshot), task],
                    metadata={"is_original": True},
                )
            )
            self._state.original_user_message_indices.add(
                len(self._state.chat_history) - 1
            )
            start_step = 0

        all_actions: List[str] = []
        all_observations: List[str] = []
        final_answer = "<no_answer>"

        for i in range(self.config.max_rounds):
            step = start_step + i + 1
            is_first_round = step == 1

            pre_screenshot_name = f"screenshot_{step}_pre.png"
            await self._save_screenshot(env, output_dir, pre_screenshot_name)

            action_dict, raw_response = await self._generate_model_call(
                env,
                is_first_round,
                scaled_screenshot if is_first_round else None,
                user_response=pending_user_response,
            )
            pending_user_response = ""
            all_actions.append(raw_response)

            action_args = action_dict.get("arguments", {})
            action_name = action_args.get("action", "")
            thoughts = action_args.get("thoughts", "")

            logger.debug(
                f"\nThought #{step}: {thoughts}\n"
                f"Action #{step}: executing tool '{action_name}' "
                f"with arguments {json.dumps(action_args)}"
            )

            is_stop, description = await self._execute_action(env, action_args)
            all_observations.append(description)

            logger.debug(f"Observation#{step}: {description}")

            # Save post-action screenshot
            post_screenshot_name = f"screenshot_{step}_post.png"
            if is_stop:
                # Copy pre as post for stop actions (no state change)
                if output_dir:
                    import shutil

                    src = Path(output_dir) / pre_screenshot_name
                    dst = Path(output_dir) / post_screenshot_name
                    if src.exists():
                        shutil.copyfile(src, dst)
            else:
                await self._save_screenshot(env, output_dir, post_screenshot_name)

            self._state.current_step = step

            # ask_user_question: return to caller for user interaction
            if action_name == "ask_user_question":
                return description, all_actions, all_observations

            if is_stop:
                final_answer = self._get_final_answer(thoughts, description)
                break

        return final_answer, all_actions, all_observations

    # ------------------------------------------------------------------
    # Overridable by subclass
    # ------------------------------------------------------------------

    def _get_final_answer(self, thoughts: str, action_description: str) -> str:
        return thoughts

    def _get_observation_prefix(self) -> str:
        """Return text to prepend to the next user message. Override in subclasses."""
        obs = self._pending_observation
        self._pending_observation = ""
        return obs

    # ------------------------------------------------------------------
    # Screenshot saving (for eval)
    # ------------------------------------------------------------------

    async def _save_screenshot(
        self,
        env: BrowserEnvironment,
        output_dir: str | Path | None,
        filename: str,
    ) -> None:
        """Save a screenshot to disk if output_dir is set."""
        if output_dir:
            screenshot_bytes = await env.get_screenshot()
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / filename).write_bytes(screenshot_bytes)

    # ------------------------------------------------------------------
    # System message / prompt construction
    # ------------------------------------------------------------------

    def _get_system_message(
        self, screenshot: Image.Image
    ) -> Tuple[List[LLMMessage], Image.Image]:
        """Build system messages with tool definitions."""
        assert self._state is not None
        system_prompt_info = get_computer_use_system_prompt(
            screenshot,
            self.mlm_processor_im_cfg,
            mode="fara_browser",
            include_input_text_key_args=self.config.include_input_text_key_args,
            fn_call_template=self.config.fn_call_template,
            display_size=self.DISPLAY_SIZE,
        )
        self._state.mlm_width, self._state.mlm_height = system_prompt_info["im_size"]
        # LANCZOS, not the PIL default (BICUBIC): on certain pages the BICUBIC
        # anti-aliasing pattern produces PNG bytes that crash vLLM/Qwen-VL with 500.
        scaled_screenshot = screenshot.resize(
            (self._state.mlm_width, self._state.mlm_height),
            Image.Resampling.LANCZOS,
        )

        system_messages: List[LLMMessage] = []
        for msg in system_prompt_info["conversation"]:
            text = "".join(content["text"] for content in msg["content"])
            system_messages.append(LLMMessage(role="system", content=text))

        return system_messages, scaled_screenshot

    async def _get_scaled_screenshot(self, env: BrowserEnvironment) -> Image.Image:
        """Take a screenshot and scale it for the model."""
        screenshot_bytes = await env.get_screenshot()
        screenshot = Image.open(io.BytesIO(screenshot_bytes))
        _, scaled = self._get_system_message(screenshot)
        return scaled

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(is_retryable_model_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=5.0, min=5.0, max=60),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    async def _make_model_call(
        self,
        history: List[LLMMessage],
        extra_create_args: dict[str, Any] | None = None,
    ) -> str:
        """Call the LLM and return the response text.

        The caller's ``extra_create_args`` dict is never mutated; we copy
        before injecting our defaults (``stop`` and, for Qwen3.5 backbones,
        ``extra_body.chat_template_kwargs.enable_thinking``).
        """
        assert self._client is not None, "Call initialize() first"
        openai_messages = [m.to_openai_dict() for m in history]
        create_args: dict[str, Any] = dict(extra_create_args or {})
        # Stop at the first complete tool_call: the parser only consumes the
        # first <tool_call>...</tool_call> block, and without this the Qwen3.5
        # backbones sometimes spew redundant blocks past the wall-clock timeout.
        create_args.setdefault("stop", ["</tool_call>"])
        if self.config.disable_thinking:
            create_args["extra_body"] = _merge_chat_template_kwargs(
                create_args.get("extra_body"),
                {"enable_thinking": False},
            )
        assert self._model is not None, "Call initialize() first"
        # The httpx read timeout on the client bounds this call; a slow model
        # surfaces as openai.APITimeoutError, which the retry predicate treats
        # as transient.
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=openai_messages,
            **create_args,
        )
        return response.choices[0].message.content or ""

    # ------------------------------------------------------------------
    # Generate model call
    # ------------------------------------------------------------------

    async def _generate_model_call(
        self,
        env: BrowserEnvironment,
        is_first_round: bool,
        first_screenshot: Image.Image | None = None,
        user_response: str = "",
    ) -> Tuple[dict[str, Any], str]:
        """Build messages, call LLM, parse response.

        Returns (action_dict, raw_response).
        """
        assert self._state is not None
        history = self.maybe_remove_old_screenshots(self._state.chat_history)
        curr_message: LLMMessage | None = None

        screenshot_for_system = first_screenshot
        if not is_first_round:
            scaled_screenshot = await self._get_scaled_screenshot(env)
            screenshot_for_system = scaled_screenshot

            curr_url = await env.get_url()
            if curr_url:
                trimmed_url = _get_trimmed_url(curr_url, self.MAX_URL_LENGTH)
                url_prefix = f"Current URL: {trimmed_url}\n"
            else:
                url_prefix = ""
            observation_prefix = self._get_observation_prefix()
            if user_response:
                text_prompt = f"{url_prefix}{user_response}"
            elif observation_prefix:
                text_prompt = f"{url_prefix}{observation_prefix}\n{self.USER_MESSAGE}"
            else:
                text_prompt = f"{url_prefix}{self.USER_MESSAGE}"

            metadata = (
                {"is_user_response": True, "user_response": user_response}
                if user_response
                else None
            )
            curr_message = LLMMessage(
                role="user",
                content=[ImageObj.from_pil(scaled_screenshot), text_prompt],
                metadata=metadata,
            )
            history.append(curr_message)

        system_messages, _ = self._get_system_message(screenshot_for_system)
        full_history = system_messages + history

        raw_response = await self._make_model_call(
            full_history, extra_create_args={"temperature": 0}
        )

        if curr_message is not None:
            self._state.chat_history.append(curr_message)
        self._state.chat_history.append(
            LLMMessage(role="assistant", content=raw_response)
        )
        thoughts, action = self._parse_thoughts_and_action(raw_response)
        action["arguments"]["thoughts"] = thoughts

        return action, raw_response

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_thoughts_and_action(self, message: str) -> Tuple[str, dict[str, Any]]:
        """Parse ``thoughts\\n<tool_call>\\n{json}\\n</tool_call>``."""
        try:
            parts = message.split("<tool_call>\n")
            thoughts = parts[0].strip()
            action_text = parts[1].split("\n</tool_call>")[0]
            try:
                action = json.loads(action_text)
            except json.JSONDecodeError:
                logger.warning(
                    f"JSON parse failed, trying ast.literal_eval: {action_text}"
                )
                action = ast.literal_eval(action_text)
            return thoughts, action
        except Exception:
            logger.error(
                f"Error parsing thoughts and action: {message}",
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------
    # Coordinate scaling
    # ------------------------------------------------------------------

    def convert_resized_coords_to_original(
        self,
        coords: List[float],
        rsz_w: int,
        rsz_h: int,
        og_w: int,
        og_h: int,
    ) -> List[float]:
        scale_x = og_w / rsz_w
        scale_y = og_h / rsz_h
        return [coords[0] * scale_x, coords[1] * scale_y]

    def proc_coords(
        self,
        coords: List[float] | None,
        im_w: int,
        im_h: int,
        og_im_w: int | None = None,
        og_im_h: int | None = None,
    ) -> List[float] | None:
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

    # ------------------------------------------------------------------
    # Screenshot management
    # ------------------------------------------------------------------

    def remove_screenshot_from_message(self, msg: LLMMessage) -> LLMMessage | None:
        """Remove the screenshot from the message content."""
        if isinstance(msg.content, list):
            new_content = [c for c in msg.content if not isinstance(c, ImageObj)]
            if not new_content:
                return None
            return LLMMessage(
                role=msg.role,
                content=new_content,
                metadata=msg.metadata,
            )
        elif isinstance(msg.content, ImageObj):
            return None
        return msg

    def maybe_remove_old_screenshots(
        self,
        history: List[LLMMessage],
        includes_current: bool = False,
    ) -> List[LLMMessage]:
        """Remove old screenshots from the chat history."""
        if self.config.max_n_images <= 0:
            return history

        max_n_images = (
            self.config.max_n_images
            if includes_current
            else self.config.max_n_images - 1
        )
        new_history: List[LLMMessage] = []
        n_images = 0

        for i in range(len(history) - 1, -1, -1):
            msg = history[i]
            meta = (msg.metadata or {}) if msg.role == "user" else {}
            preserve_text = meta.get("is_original", False) or meta.get(
                "is_user_response", False
            )

            if i == 0 and n_images >= max_n_images:
                msg = self.remove_screenshot_from_message(msg)
                if msg is None:
                    continue

            if isinstance(msg.content, list):
                has_image = any(isinstance(c, ImageObj) for c in msg.content)
                if has_image:
                    if n_images < max_n_images:
                        new_history.append(msg)
                    elif preserve_text:
                        msg = self.remove_screenshot_from_message(msg)
                        if msg is not None:
                            raw = meta.get("user_response")
                            if raw is not None:
                                msg.content = [raw]
                            new_history.append(msg)
                    n_images += 1
                else:
                    new_history.append(msg)
            elif isinstance(msg.content, ImageObj):
                if n_images < max_n_images:
                    new_history.append(msg)
                n_images += 1
            else:
                new_history.append(msg)

        return new_history[::-1]

    # ------------------------------------------------------------------
    # Action execution (11 actions)
    # ------------------------------------------------------------------

    async def _execute_action(
        self, env: BrowserEnvironment, args: dict[str, Any]
    ) -> Tuple[bool, str]:
        """Execute an action. Returns (is_stop, description)."""
        # Scale coordinates from DISPLAY_SIZE to viewport
        if "coordinate" in args:
            args["coordinate"] = self.proc_coords(
                args["coordinate"],
                self.DISPLAY_SIZE,
                self.DISPLAY_SIZE,
                self.config.viewport_width,
                self.config.viewport_height,
            )

        is_stop = False
        action_type = args["action"]
        description = ""

        if action_type == "visit_url":
            url = str(args["url"])
            description = f"I typed '{url}' into the browser address bar."
            if url.startswith(("https://", "http://", "file://", "about:")):
                await env.goto(url)
            elif " " in url:
                await env.goto(
                    f"https://www.bing.com/search?q={quote_plus(url)}&FORM=QBLH"
                )
            else:
                await env.goto("https://" + url)

        elif action_type == "history_back":
            description = "I clicked the browser back button."
            await env.back()

        elif action_type == "web_search":
            query = str(args.get("query", ""))
            description = f"I typed '{query}' into the browser search bar."
            encoded_query = quote_plus(query)
            await env.goto(f"https://www.bing.com/search?q={encoded_query}&FORM=QBLH")

        elif action_type == "scroll":
            pixels = int(args.get("pixels", 0))
            if pixels > 0:
                description = "I scrolled up one page in the browser."
                await env.scroll_up()
            elif pixels < 0:
                description = "I scrolled down one page in the browser."
                await env.scroll_down()

        elif action_type in ("keypress", "key"):
            keys = args.get("keys", [])
            description = f"I pressed the following keys: {keys}"
            await env.key(keys)

        elif action_type in ("hover", "mouse_move"):
            if "coordinate" in args:
                tgt_x, tgt_y = args["coordinate"]
                await env.hover(tgt_x, tgt_y)

        elif action_type in ("sleep", "wait"):
            duration = float(args.get("duration", args.get("time", 3.0)))
            description = (
                "I am waiting a short period of time before taking further action."
            )
            await env.wait(duration)

        elif action_type in ("click", "left_click"):
            if "coordinate" in args:
                tgt_x, tgt_y = args["coordinate"]
                description = f"I clicked at coordinates ({tgt_x}, {tgt_y})."
                await env.left_click(tgt_x, tgt_y)

        elif action_type in ("input_text", "type"):
            text_value = args.get("text", args.get("text_value"))
            if text_value is None:
                raise ValueError(
                    "input_text/type action requires 'text' or 'text_value' argument"
                )
            text_value = str(text_value)
            description = f"I typed '{text_value}'."
            press_enter = args.get("press_enter", True)
            delete_existing = args.get("delete_existing_text", False)
            if "coordinate" in args:
                tgt_x, tgt_y = args["coordinate"]
                await env.type_text(
                    tgt_x,
                    tgt_y,
                    text_value,
                    press_enter=press_enter,
                    clear_first=delete_existing,
                )

        elif action_type == "pause_and_memorize_fact":
            fact = str(args.get("fact", ""))
            self._state.facts.append(fact)
            description = f"I memorized the following fact: {fact}"

        elif action_type in ("stop", "terminate"):
            description = args.get("thoughts", "Task terminated")
            is_stop = True

        else:
            raise ValueError(f"Unknown action: {action_type}")

        if not is_stop:
            # Post-action wait policy:
            #   - pause_and_memorize_fact is purely local (no DOM change),
            #     so neither a load wait nor a settle delay is required.
            #   - For all other actions, wait for `domcontentloaded`
            #     (not `load`) with a 20s cap. The default `load` state
            #     may never fire on ad-heavy SPAs (Zumper, etc.), causing
            #     a 30s Playwright default timeout per action.
            #     Suppress the timeout: many actions don't trigger any
            #     navigation, in which case the wait is a no-op anyway.
            #     Real failures (target closed, protocol errors) still
            #     propagate — only TimeoutError is swallowed.
            if action_type != "pause_and_memorize_fact":
                try:
                    await env.wait_for_load(state="domcontentloaded", timeout=20000)
                except asyncio.TimeoutError:
                    pass
                await asyncio.sleep(3)

        self._state.num_actions += 1
        return is_stop, description

    # ------------------------------------------------------------------
    # Helper for harness
    # ------------------------------------------------------------------

    def add_user_message(self, msg: LLMMessage, is_original: bool = False) -> None:
        """Append a user message to chat history."""
        assert self._state is not None
        self._state.chat_history.append(msg)
        if is_original:
            self._state.original_user_message_indices.add(
                len(self._state.chat_history) - 1
            )
