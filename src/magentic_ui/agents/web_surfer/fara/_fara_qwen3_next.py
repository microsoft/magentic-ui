"""FaraQwen3NextAgent — Extends FaraQwen3Agent with expanded tool sets."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger
from PIL import Image

from ._fara_qwen3 import FaraQwen3Agent, FaraQwen3AgentConfig
from ._prompts import get_computer_use_system_prompt
from ._types import BrowserEnvironment, LLMMessage


class FaraQwen3NextAgentConfig(FaraQwen3AgentConfig):
    """Configuration for FaraQwen3NextAgent."""

    name: str = "fara_next"
    tools: list[str] = ["BROWSER_TOOLS_CORE"]
    max_observation_chars: int = 1000


class FaraQwen3NextAgent(FaraQwen3Agent):
    """Web/desktop automation agent with expanded tool sets (FaraNext).

    Extends FaraQwen3Agent with:
    - Dynamic tool mode selection (browser vs windows) via config.tools
    - New GUI actions: double_click, right_click, triple_click, left_click_drag, hscroll
    - New non-GUI actions: read_page_answer_question, ask_user_question, run_command
    - Cursor position tracking for left_click_drag
    """

    # Tool set to mode mapping
    TOOL_SET_TO_MODE = {
        "BROWSER_TOOLS_CORE": "fara_next_browser",
        "BROWSER_TOOLS_WITH_READ_PAGE": "fara_next_browser",
    }

    # New action types not in parent
    _NEW_ACTIONS = frozenset(
        {
            "type",
            "input_text",
            "scroll",
            "double_click",
            "right_click",
            "triple_click",
            "left_click_drag",
            "hscroll",
            "read_page_answer_question",
            "ask_user_question",
            "run_command",
            "terminate",
        }
    )

    # Actions whose observation is text (not a screenshot state change).
    # Their output gets stashed in _pending_observation and prepended to the
    # next user message.
    _TEXT_OBSERVATION_ACTIONS = frozenset({"read_page_answer_question"})

    def __init__(
        self,
        config: FaraQwen3NextAgentConfig | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self.config: FaraQwen3NextAgentConfig
        self._computer_use_mode: str = "fara_next_browser"
        self._cursor_x: float = 0.0
        self._cursor_y: float = 0.0

    @classmethod
    def _get_config_class(cls) -> type[FaraQwen3NextAgentConfig]:
        return FaraQwen3NextAgentConfig

    async def initialize(self) -> None:
        await super().initialize()
        tool_set = self.config.tools[0] if self.config.tools else "BROWSER_TOOLS_CORE"
        self._computer_use_mode = self.TOOL_SET_TO_MODE.get(
            tool_set, "fara_next_browser"
        )

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def _get_system_message(self, screenshot):
        """Use dynamic mode instead of hardcoded 'fara_browser'."""
        assert self._state is not None
        system_prompt_info = get_computer_use_system_prompt(
            screenshot,
            self.mlm_processor_im_cfg,
            mode=self._computer_use_mode,
            include_input_text_key_args=self.config.include_input_text_key_args,
            fn_call_template=self.config.fn_call_template,
            display_size=self.DISPLAY_SIZE,
        )
        self._state.mlm_width, self._state.mlm_height = system_prompt_info["im_size"]
        # LANCZOS, not PIL default (BICUBIC): on certain pages the BICUBIC
        # anti-aliasing pattern produces PNG bytes that crash vLLM/Qwen-VL.
        scaled_screenshot = screenshot.resize(
            (self._state.mlm_width, self._state.mlm_height),
            Image.Resampling.LANCZOS,
        )

        system_messages = []
        for msg in system_prompt_info["conversation"]:
            text = "".join(content["text"] for content in msg["content"])
            system_messages.append(LLMMessage(role="system", content=text))

        return system_messages, scaled_screenshot

    def _get_final_answer(self, thoughts: str, action_description: str) -> str:
        return action_description

    # ------------------------------------------------------------------
    # Action execution — new dispatch + parent delegation
    # ------------------------------------------------------------------

    async def _execute_action(
        self, env: BrowserEnvironment, args: dict[str, Any]
    ) -> tuple[bool, str]:
        """Execute an action — handles new actions, delegates shared ones to parent."""
        action_type = args.get("action", "")

        if action_type in self._NEW_ACTIONS:
            logger.debug(f"FaraQwen3NextAgent: {action_type}({json.dumps(args)})")

            if "coordinate" in args:
                args["coordinate"] = self._proc(args["coordinate"])

            is_stop, description = await self._dispatch_new_action(
                env, action_type, args
            )

            if action_type in self._TEXT_OBSERVATION_ACTIONS:
                self._pending_observation = self._truncate_observation(
                    description, self.config.max_observation_chars
                )

            if not is_stop:
                # Mirror the parent FaraQwen3Agent post-action wait policy:
                # wait for `domcontentloaded` (not `load`, which may never
                # fire on ad-heavy SPAs) with a 20s cap, then a 3s settle.
                # See FaraQwen3Agent._execute_action for full rationale.
                try:
                    await env.wait_for_load(state="domcontentloaded", timeout=20000)
                except asyncio.TimeoutError:
                    pass
                await asyncio.sleep(3)

            self._state.num_actions += 1
            return is_stop, description

        # Delegate to parent for shared actions
        is_stop, desc = await super()._execute_action(env, args)

        # Track cursor on parent's coordinate actions
        if "coordinate" in args and args["coordinate"] and not is_stop:
            self._cursor_x, self._cursor_y = args["coordinate"]

        return is_stop, desc

    async def _dispatch_new_action(
        self, env: BrowserEnvironment, action_type: str, args: dict[str, Any]
    ) -> tuple[bool, str]:
        """Dispatch new actions not present in FaraQwen3Agent."""

        if action_type in ("type", "input_text"):
            text = str(args.get("text", args.get("text_value", "")))
            await env.type_direct(text)
            return False, f"I typed '{text}'."

        elif action_type == "scroll":
            pixels = int(args.get("pixels", 0))
            pixels = int(pixels * self.config.viewport_height / self.DISPLAY_SIZE)
            amount = abs(pixels)
            if pixels > 0:
                await env.scroll_up(amount)
                return False, "I scrolled up one page in the browser."
            elif pixels < 0:
                await env.scroll_down(amount)
                return False, "I scrolled down one page in the browser."
            return False, ""

        elif action_type == "double_click":
            tgt_x, tgt_y = args["coordinate"]
            await env.double_click(tgt_x, tgt_y)
            self._cursor_x, self._cursor_y = tgt_x, tgt_y
            return False, f"I double-clicked at coordinates ({tgt_x}, {tgt_y})."

        elif action_type == "right_click":
            tgt_x, tgt_y = args["coordinate"]
            await env.right_click(tgt_x, tgt_y)
            self._cursor_x, self._cursor_y = tgt_x, tgt_y
            return False, f"I right-clicked at coordinates ({tgt_x}, {tgt_y})."

        elif action_type == "triple_click":
            tgt_x, tgt_y = args["coordinate"]
            await env.triple_click(tgt_x, tgt_y)
            self._cursor_x, self._cursor_y = tgt_x, tgt_y
            return (
                False,
                f"I triple-clicked at coordinates ({tgt_x}, {tgt_y}).",
            )

        elif action_type == "left_click_drag":
            tgt_x, tgt_y = args["coordinate"]
            await env.left_click_drag(tgt_x, tgt_y)
            self._cursor_x, self._cursor_y = tgt_x, tgt_y
            return False, f"I dragged to ({tgt_x}, {tgt_y})."

        elif action_type == "hscroll":
            pixels = int(args.get("pixels", 0))
            pixels = int(pixels * self.config.viewport_width / self.DISPLAY_SIZE)
            await env.hscroll(pixels)
            return False, f"I scrolled horizontally by {pixels} pixels."

        elif action_type == "read_page_answer_question":
            question = str(args.get("question", ""))
            markdown = await env.get_page_markdown()
            answer = await self._extract_from_page(markdown, question)
            return (
                False,
                f"I read the page to answer: {question}\nAnswer: {answer}",
            )

        elif action_type == "ask_user_question":
            question = str(args.get("question", ""))
            return True, f"I asked the user: {question}"

        elif action_type == "run_command":
            command = str(args.get("command", ""))
            result = await env.execute(command)
            if len(result) > 1000:
                result = result[:500] + f"\n... [truncated {len(result) - 500} chars]"
            return (
                False,
                f"I executed command: {command}\nOutput: {result}",
            )

        elif action_type == "terminate":
            answer = args.get("answer")
            if answer is None:
                raise ValueError("terminate action requires 'answer' argument")
            return True, answer

        raise ValueError(f"Unknown new action: {action_type}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _proc(self, coordinate: list[float]) -> list[float]:
        """Shorthand for proc_coords with standard display/viewport args."""
        return self.proc_coords(
            coordinate,
            self.DISPLAY_SIZE,
            self.DISPLAY_SIZE,
            self.config.viewport_width,
            self.config.viewport_height,
        )

    @staticmethod
    def _truncate_observation(text: str, max_chars: int = 1000) -> str:
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        return (
            text[:half]
            + f"\n... [truncated {len(text) - max_chars} chars] ...\n"
            + text[-half:]
        )

    async def _extract_from_page(
        self, markdown: str, question: str, max_chars: int = 20000
    ) -> str:
        """Send page markdown to the model with a question, return concise answer."""
        assert self._client is not None
        if len(markdown) > max_chars:
            markdown = markdown[:max_chars] + "\n... [truncated]"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are given the markdown content of a web page. "
                    "Answer the user's question based solely on this content. "
                    "Be concise and extract only the relevant information."
                ),
            },
            {
                "role": "user",
                "content": f"Page content:\n{markdown}\n\nQuestion: {question}",
            },
        ]

        assert self._model is not None, "Call initialize() first"
        # Bounded by the client's httpx read timeout.
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        return response.choices[0].message.content or "Error: Extraction failed."
