"""FaraWebSurfer — Harness wrapping the core Fara agent with magentic-ui features.

Provides streaming (run_stream), pause/resume, critical point detection,
ask_user_question handling, error retry, and noVNC integration.

Uses composition: contains a core Fara agent instance and a
PlaywrightBrowserEnvironment. The harness drives the action loop,
calling agent methods individually so it can insert yields and
checks between steps.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from ._browser_env import PlaywrightBrowserEnvironment
from ._fara_qwen3 import FaraQwen3Agent
from ._fara_qwen3_next import FaraQwen3NextAgent
from ._state_io import message_from_dict, message_to_dict
from ._types import ImageObj, LLMMessage, StreamUpdate
from ...message_schemas import (
    HandoffInfo,
    HandoffReason,
    HandoffStatus,
    browser_address_props,
    error_props,
    final_answer_props,
    screenshot_props,
    tool_call_props,
)
from ....tools.playwright.playwright_controller_fara import PlaywrightController
from ....types import ContinuationRequest, InputRequest, PauseController

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

    from ....tools.playwright.browser import PlaywrightBrowser


class FaraWebSurfer:
    """Core Fara agent + magentic-ui streaming, pause/resume, critical point.

    This is the harness that wraps the core agent for use in magentic-ui.
    It implements :class:`~magentic_ui.agents.base.SubAgentProtocol`
    (``run_stream``, ``summarize_progress``, ``close``).

    The harness drives the action loop itself (does NOT call agent.run()),
    calling agent._generate_model_call() and agent._execute_action()
    individually so it can insert streaming yields, pause checks, critical
    point detection, and error retry between steps.
    """

    _name = "web_surfer"  # Matches frontend expectations

    def __init__(
        self,
        model_client_config: Any = None,
        browser: PlaywrightBrowser | None = None,
        novnc_port: int = -1,
        playwright_port: int = -1,
        task_id: str | None = None,
        pause_controller: PauseController | None = None,
        downloads_folder: str | None = None,
        output_dir: str | None = None,
        agent_variant: str = "qwen3_next",
        max_rounds: int = 100,
        state_dir: Path | None = None,
    ) -> None:
        self._model_client_config = model_client_config
        self._browser = browser
        self.novnc_port = novnc_port
        self.playwright_port = playwright_port
        # Per-acquire RFB password. Discovered from the browser backend
        # in _lazy_init() once the slot is bound.
        self.vnc_password: str = ""
        self._task_id = task_id
        self.downloads_folder = downloads_folder
        self.output_dir = output_dir
        self._agent_variant = agent_variant
        self._max_rounds = max_rounds
        # Session-scoped state file: last URL + chat history, restored
        # by a follow-up run after the TM is closed (death/stop/idle).
        self._state_path: Path | None = (
            state_dir / "fara_state.json" if state_dir else None
        )

        # Pause/resume state
        self._pause_controller = pause_controller

        # Lazy initialized
        self._agent: FaraQwen3Agent | None = None
        self._env: PlaywrightBrowserEnvironment | None = None
        self._browser_started = False
        self._context: BrowserContext | None = None
        # Snapshot of fara_state.json shared between init and lazy_init.
        self._saved_state: dict[str, Any] = {}

        # Harness-only state
        self._pending_error_message: str | None = None
        self._pending_user_response: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _init_agent_with_state(self) -> None:
        """Build the core agent, restore chat_history from disk, cache the snapshot."""
        if self._agent is not None:
            return

        client_config = self._parse_client_config(self._model_client_config)
        if self._agent_variant == "qwen3_next":
            self._agent = FaraQwen3NextAgent(
                client_config=client_config, max_rounds=self._max_rounds
            )
        elif self._agent_variant == "qwen3":
            self._agent = FaraQwen3Agent(
                client_config=client_config, max_rounds=self._max_rounds
            )
        else:
            raise ValueError(
                f"Unknown web_surfer_variant: {self._agent_variant!r}. "
                f"Expected 'qwen3' or 'qwen3_next'."
            )

        await self._agent.initialize()
        self._saved_state = self._read_state_file()
        self._restore_chat_history(self._saved_state)

    async def _lazy_init(self) -> None:
        """Initialize agent, browser, and environment on first use."""
        if self._browser_started:
            return

        await self._init_agent_with_state()

        # Start browser (required for web surfing)
        if self._browser is None:
            raise ValueError(
                "FaraWebSurfer requires a browser instance. "
                "Pass browser= to the constructor."
            )

        await self._browser.__aenter__()

        # Discover ports from browser (quicksand path). Each attribute is a
        # @property that raises RuntimeError before the slot is bound;
        # AttributeError covers backends that don't expose them at all
        # (e.g., LocalPlaywrightBrowser).
        if self.novnc_port <= 0:
            try:
                self.novnc_port = self._browser.novnc_host_port
            except (AttributeError, RuntimeError):
                logger.warning("Browser started but noVNC port unavailable")
        if self.playwright_port <= 0:
            try:
                self.playwright_port = self._browser.cdp_host_port
            except (AttributeError, RuntimeError):
                logger.warning("Browser started but CDP port unavailable")
        try:
            self.vnc_password = self._browser.vnc_password
        except (AttributeError, RuntimeError):
            logger.warning("Browser started but VNC password unavailable")

        # Create page and controller
        self._context = self._browser.browser_context
        page = await self._context.new_page()

        controller = PlaywrightController(
            animate_actions=False,
            viewport_width=self._agent.config.viewport_width,
            viewport_height=self._agent.config.viewport_height,
            downloads_folder=self.downloads_folder,
        )
        await controller.on_new_page(page)

        # Wrap in BrowserEnvironment
        self._env = PlaywrightBrowserEnvironment(page, controller)

        start_url = self._load_start_url(self._saved_state)
        await self._env.goto(start_url)
        await self._restore_scroll_position(self._saved_state)

        self._browser_started = True

    def _read_state_file(self) -> dict[str, Any]:
        """Read the saved state JSON. Returns {} if absent or unreadable."""
        if not self._state_path or not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text())
        except Exception as e:
            logger.warning(f"Failed to load fara state {self._state_path}: {e}")
            return {}

    def _load_start_url(self, saved_state: dict[str, Any]) -> str:
        url = saved_state.get("last_url")
        if url:
            logger.info(f"Restoring last URL: {url}")
            return url
        return FaraQwen3Agent.DEFAULT_START_PAGE

    async def _restore_scroll_position(self, saved_state: dict[str, Any]) -> None:
        if self._env is None:
            return
        scroll = saved_state.get("scroll")
        if not isinstance(scroll, list) or len(scroll) != 2:
            return
        x, y = int(scroll[0]), int(scroll[1])
        if x == 0 and y == 0:
            return
        await self._env.scroll_to(x, y)
        logger.info(f"Restored scroll position: ({x}, {y})")

    def _restore_chat_history(self, saved_state: dict[str, Any]) -> None:
        if self._agent is None or self._agent._state is None:
            return
        raw = saved_state.get("chat_history")
        if not raw:
            return
        self._agent._state.chat_history = [message_from_dict(m) for m in raw]
        self._agent._state.facts = list(saved_state.get("facts") or [])
        logger.info(
            f"Restored chat history: {len(self._agent._state.chat_history)} messages"
        )

    async def _save_state(self) -> None:
        """Persist last URL, scroll, chat history, facts. Logs and returns on
        any failure — persistence must never break the agent's action loop.
        TODO: writes the full chat history (with retained image base64) on
        every action; if max_n_images grows beyond ~3 this becomes a hot-path
        IO cost worth rethinking."""
        if not self._state_path or self._env is None or self._agent is None:
            return
        if self._agent._state is None:
            return
        try:
            url = await self._env.get_url()
            scroll = list(await self._env.get_scroll())
            trimmed = self._agent.maybe_remove_old_screenshots(
                self._agent._state.chat_history, includes_current=True
            )
            payload = {
                "last_url": url,
                "scroll": scroll,
                "chat_history": [message_to_dict(m) for m in trimmed],
                "facts": list(self._agent._state.facts),
            }
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(payload))
        except Exception as e:
            logger.warning(f"Failed to save fara state {self._state_path}: {e}")

    # TODO: create separate config client, and clean this up
    @staticmethod
    def _parse_client_config(model_client_config: Any) -> dict[str, Any]:
        """Extract client_config dict from various config formats."""
        if model_client_config is None:
            return {}
        config = model_client_config
        # Handle Pydantic model
        if hasattr(config, "model_dump"):
            config = config.model_dump()
        if isinstance(config, dict) and "config" in config:
            return config["config"]
        if isinstance(config, dict):
            return config
        return {}

    async def close(self) -> None:
        """Cleanup browser and agent resources.

        Each step is independently guarded so the browser slot is always
        released even if agent client close fails.
        """
        if self._agent is not None:
            try:
                await self._agent.close()
            except Exception:
                logger.exception("FaraWebSurfer: error closing inner agent")
            self._agent = None
        if self._browser is not None and self._browser_started:
            try:
                await self._browser.__aexit__(None, None, None)
            except Exception:
                logger.exception("FaraWebSurfer: error closing browser")
            self._browser_started = False
            self._context = None
            self._env = None

    def current_browser_address(self) -> dict[str, Any] | None:
        """Return live noVNC connection info, or None if no slot is bound."""
        if self.novnc_port <= 0 or not self.vnc_password:
            return None
        return browser_address_props(
            self._name,
            str(self.novnc_port),
            str(self.playwright_port),
            password=self.vnc_password,
        )

    # ------------------------------------------------------------------
    # run_stream — main streaming interface
    # ------------------------------------------------------------------

    async def run_stream(
        self,
        task: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamUpdate | InputRequest]:
        """Stream web browsing task execution.

        Yields StreamUpdate for each step, or InputRequest when user input is needed.
        """
        if not task:
            yield StreamUpdate(
                text="Error: No task provided",
                additional_properties=error_props(self._name),
            )
            return

        await self._lazy_init()
        assert self._agent is not None
        assert self._env is not None

        # Emit browser address for noVNC thumbnail
        if self.novnc_port > 0:
            yield StreamUpdate(
                text=f"Browser ready at noVNC port {self.novnc_port}",
                additional_properties=browser_address_props(
                    self._name,
                    str(self.novnc_port),
                    str(self.playwright_port),
                    password=self.vnc_password,
                ),
            )

        restored_history = bool(self._agent._state.chat_history)
        scaled_screenshot = None
        if restored_history:
            self._pending_user_response = task
        else:
            # Build initial user message with screenshot + task.
            scaled_screenshot = await self._agent._get_scaled_screenshot(self._env)
            await self._save_screenshot("screenshot_0_pre.png")
            self._agent.add_user_message(
                LLMMessage(
                    role="user",
                    content=[ImageObj.from_pil(scaled_screenshot), task],
                    metadata={"is_original": True},
                ),
                is_original=True,
            )
            await self._save_state()

        # Main action loop (harness drives, not agent.run())
        step = 0
        consecutive_errors = 0
        max_consecutive_errors = 3
        round_idx = 0
        while True:
            if round_idx >= self._agent.config.max_rounds:
                should_continue = False
                async for evt in self._handle_max_rounds_continuation(step):
                    if isinstance(evt, bool):
                        should_continue = evt
                    else:
                        yield evt
                if not should_continue:
                    return
                round_idx = 0
                continue
            if self._pause_controller and self._pause_controller.is_cancelled:
                logger.info("Run cancelled, exiting action loop")
                break

            step += 1
            is_first_round = round_idx == 0 and not restored_history and step == 1
            round_idx += 1
            raw_response = ""

            # Drain mid-run inbox. Fara takes one user_response per step,
            # so messages are joined with newlines and appended after any
            # existing pending response (which is chronologically older).
            if self._pause_controller and self._pause_controller.has_queued_messages:
                queued = self._pause_controller.drain_messages(reader=self._name)
                joined = "\n".join(queued)
                self._pending_user_response = (
                    f"{self._pending_user_response}\n{joined}"
                    if self._pending_user_response
                    else joined
                )

            # Nudge the model to stop if it's been running too long
            if step > 0 and step % 20 == 0 and not self._pending_user_response:
                self._pending_user_response = (
                    "REMINDER: You have been running for many steps. "
                    "If you are done or repeating the same actions without progress, "
                    "use the terminate action now with your best answer. "
                    "Do not continue if you are stuck."
                )

            # Save pre-action screenshot (for eval)
            await self._save_screenshot(f"screenshot_{step}_pre.png")

            # --- Step 1: Generate model call + validate ---
            try:
                # Inject pending error into user_response so the model
                # sees it in the next prompt alongside the screenshot
                if self._pending_error_message:
                    self._pending_user_response = (
                        f"ERROR: {self._pending_error_message}\n\n"
                        + self._pending_user_response
                    )
                    self._pending_error_message = None

                action, raw_response = await self._agent._generate_model_call(
                    self._env,
                    is_first_round,
                    scaled_screenshot,
                    user_response=self._pending_user_response,
                )
                self._pending_user_response = ""
                action_args = action.get("arguments", {})
                action_type = action_args.get("action", "")

                # Validate action structure
                is_valid, error_msg = self._validate_action(action)
                if not is_valid:
                    raise ValueError(error_msg)

            except Exception as e:
                error_str = str(e) or f"{type(e).__name__} (empty message)"
                logger.error(
                    f"Tool call error: {error_str} | Raw: {repr(raw_response)}"
                )
                # Make connection failures explicit so users know the LLM
                # endpoint is unreachable, not the magentic-ui itself.
                user_error = (
                    f"Model API connection error ({error_str})"
                    if "connection error" in error_str.lower()
                    else error_str
                )
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    final_text = (
                        f"Giving up after {consecutive_errors} consecutive errors. "
                        f"Last error: {user_error}"
                    )
                    info = await self._handoff_info(
                        status=HandoffStatus.ERROR,
                        reason=HandoffReason.CONSECUTIVE_ERRORS,
                    )
                    yield StreamUpdate(
                        text=final_text,
                        additional_properties=final_answer_props(
                            self._name, handoff=info
                        ),
                    )
                    return
                if raw_response:
                    self._pending_error_message = error_str
                yield StreamUpdate(
                    text=f"{user_error}. Retrying ({consecutive_errors}/{max_consecutive_errors})...",
                    additional_properties=error_props(self._name),
                )
                continue

            consecutive_errors = 0
            thoughts = action_args.get("thoughts", "")

            # --- Step 2: Check terminate ---
            if action_type in ("terminate", "stop"):
                # Critical point detection
                if "critical point" in thoughts.lower():
                    logger.info("Critical point detected — requesting user input")
                    future: asyncio.Future[str] = (
                        asyncio.get_running_loop().create_future()
                    )
                    yield InputRequest(prompt=thoughts, respond=future.set_result)
                    resp = await future
                    await self._inject_user_input(resp)
                    continue

                # Normal terminate
                final_text = self._agent._get_final_answer(
                    thoughts, action_args.get("answer", thoughts)
                )
                info = await self._handoff_info(
                    status=HandoffStatus.COMPLETED,
                    reason=HandoffReason.TERMINATE,
                )
                yield StreamUpdate(
                    text=final_text,
                    additional_properties=final_answer_props(self._name, handoff=info),
                )
                break

            # --- Step 3: Check ask_user_question ---
            if action_type == "ask_user_question":
                question = action_args.get("question", "")
                future = asyncio.get_running_loop().create_future()
                yield InputRequest(prompt=question, respond=future.set_result)
                resp = await future
                await self._inject_user_input(resp)
                continue

            # --- Step 4: Yield tool call ---
            formatted_content = f"{thoughts} (tool: {action_type})"
            yield StreamUpdate(
                text=formatted_content,
                additional_properties=tool_call_props(
                    self._name, action_type, action_args
                ),
            )

            # --- Step 5: Execute action ---
            try:
                is_stop, description = await self._agent._execute_action(
                    self._env, action_args
                )

                # Take screenshot after action
                screenshot_bytes = await self._env.get_screenshot()
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                yield StreamUpdate(
                    text=description,
                    additional_properties=screenshot_props(
                        self._name,
                        f"data:image/png;base64,{screenshot_b64}",
                    ),
                )

                # Save post-action screenshot (for eval)
                await self._save_screenshot(
                    f"screenshot_{step}_post.png", screenshot_bytes
                )

                await self._save_state()

                if is_stop:
                    break

                # --- Step 6: Pause check ---
                if self._pause_controller and self._pause_controller.is_paused:
                    future = asyncio.get_running_loop().create_future()
                    yield InputRequest(
                        prompt="Task paused. Please type a message to continue.",
                        respond=future.set_result,
                    )
                    resp = await future
                    await self._inject_user_input(resp)
                    continue

            except asyncio.TimeoutError:
                raise  # Re-raise timeout (handled by connection layer)
            except Exception as e:
                error_msg = f"Error executing action: {e}"
                logger.error(f"Action execution failed | {error_msg}")

                # Action-aware guidance
                error_str = str(e).lower()
                is_nav = action_type in (
                    "visit_url",
                    "web_search",
                    "history_back",
                )
                if "timeout" in error_str:
                    guidance = (
                        "Page load timeout - URL may be invalid or unreachable."
                        if is_nav
                        else "Operation timeout - try a different action."
                    )
                elif is_nav:
                    guidance = "Navigation failed - try a different URL."
                else:
                    guidance = "Action failed - try a different approach."

                self._pending_error_message = f"{error_msg}. {guidance}"
                yield StreamUpdate(
                    text=f"{error_msg}. {guidance}",
                    additional_properties=error_props(self._name),
                )
                continue

    # ------------------------------------------------------------------
    # Harness-only methods
    # ------------------------------------------------------------------

    async def _handoff_info(
        self,
        *,
        status: HandoffStatus,
        reason: HandoffReason,
    ) -> HandoffInfo:
        """Gather the last URL and memorized facts into handoff info."""
        last_url: str | None = None
        if self._env is not None:
            try:
                last_url = await self._env.get_url()
            except Exception as e:
                logger.warning(f"Handoff: failed to capture last URL: {e}")
                last_url = None
        if not last_url:
            saved = self._saved_state.get("last_url")
            last_url = saved if isinstance(saved, str) and saved else None
        facts: list[str] = []
        if self._agent is not None and self._agent._state is not None:  # pyright: ignore[reportPrivateUsage]
            facts = list(self._agent._state.facts)  # pyright: ignore[reportPrivateUsage]
        return {
            "status": status.value,
            "reason": reason.value,
            "last_url": last_url,
            "facts": facts,
        }

    async def _recap_and_handoff(
        self,
        *,
        status: HandoffStatus,
        reason: HandoffReason,
    ) -> tuple[str, HandoffInfo]:
        """LLM recap of progress paired with structured handoff info."""
        return (
            await self._summarize_progress(),
            await self._handoff_info(status=status, reason=reason),
        )

    async def summarize_progress(self) -> tuple[str, HandoffInfo]:
        """Return a clean recap plus structured handoff info for resume."""
        await self._init_agent_with_state()
        orphan_info: HandoffInfo = {
            "status": HandoffStatus.INCOMPLETE.value,
            "reason": HandoffReason.ORPHAN_RECOVERY.value,
            "last_url": None,
            "facts": [],
        }
        if self._agent is None or self._agent._state is None:  # pyright: ignore[reportPrivateUsage]
            return (
                "Sub-agent state unavailable — no prior progress to report.",
                orphan_info,
            )
        if not self._agent._state.chat_history:  # pyright: ignore[reportPrivateUsage]
            return (
                "No prior browsing progress is available for this session.",
                orphan_info,
            )
        return await self._recap_and_handoff(
            status=HandoffStatus.INCOMPLETE,
            reason=HandoffReason.ORPHAN_RECOVERY,
        )

    async def _handle_max_rounds_continuation(
        self, actions_so_far: int
    ) -> AsyncIterator[StreamUpdate | ContinuationRequest | bool]:
        """Yield a Continue/Stop card and react to the user's choice."""
        prompt = (
            f"Browser use has taken {actions_so_far} actions without "
            "finishing the task. Continue?"
        )
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        yield ContinuationRequest(prompt=prompt, respond=future.set_result)
        resp = await future
        if resp.strip().lower().rstrip(".!,") == "yes":
            # Don't inject a synthetic user_response: the next
            # _generate_model_call drains _pending_observation only when
            # user_response is empty, and clobbering it here would drop a
            # text observation (e.g. read_page_answer_question) that the
            # last action produced.
            yield True
            return
        logger.info("User chose to stop after max rounds reached")
        final_text, info = await self._recap_and_handoff(
            status=HandoffStatus.INCOMPLETE,
            reason=HandoffReason.MAX_ROUNDS,
        )
        yield StreamUpdate(
            text=final_text,
            additional_properties=final_answer_props(
                self._name, max_rounds_reached=True, handoff=info
            ),
        )
        yield False

    async def _summarize_progress(self) -> str:
        """Best-effort final summary built from ``chat_history``.

        Swaps the leading system message for a one-shot summary prompt and
        clears the default ``stop=["</tool_call>"]`` so prose isn't truncated.
        Any pending text observation (e.g. ``read_page_answer_question``)
        that has not yet been flushed into ``chat_history`` is appended
        as a final user message so the model can see the latest result.
        """
        fallback = "Stopped at the user's request before completion."
        if self._agent is None or self._agent._state is None:  # pyright: ignore[reportPrivateUsage]
            return fallback
        try:
            history = self._agent.maybe_remove_old_screenshots(
                self._agent._state.chat_history,  # pyright: ignore[reportPrivateUsage]
                includes_current=True,
            )
            pending_obs = getattr(self._agent, "_pending_observation", "") or ""
            summary_system = LLMMessage(
                role="system",
                content=(
                    "You are a helpful assistant. The user has stopped the "
                    "browsing task before it was complete. Based on the "
                    "actions and observations in the conversation above, "
                    "write a concise final answer covering: (1) what you "
                    "were trying to do, (2) the most useful information or "
                    "partial result you collected, and (3) what is still "
                    "missing or unverified. Reply in 1-3 short paragraphs "
                    "of plain text. Do not output any tool_call or XML tags."
                ),
            )
            full_history: list[LLMMessage] = [summary_system, *history]
            if pending_obs:
                full_history.append(
                    LLMMessage(
                        role="user",
                        content=f"Latest observation:\n{pending_obs}",
                    )
                )
            raw = await self._agent._make_model_call(  # pyright: ignore[reportPrivateUsage]
                full_history,
                extra_create_args={"temperature": 0, "stop": []},
            )
            text = (raw or "").strip()
            if "<tool_call>" in text:
                text = text.split("<tool_call>", 1)[0].strip()
            return text or fallback
        except Exception as e:
            logger.warning(f"Failed to generate stop summary: {e}")
            return fallback

    async def _inject_user_input(self, user_response: str) -> None:
        """Store user response for next _generate_model_call.

        Shared by pause handler, critical point handler, and ask_user_question.
        The response is passed to _generate_model_call(user_response=...) which
        includes it in the prompt text alongside the URL and screenshot.
        This avoids duplicate user messages on resume.
        """
        logger.info(f"Received user input ({len(user_response)} chars)")
        await self._recover_active_page()
        self._pending_user_response = user_response

    async def _recover_active_page(self) -> None:
        """Ensure the browser environment points to a live page.

        After browser takeover the user may have closed the tab.
        """
        assert self._context is not None
        assert self._env is not None

        page = self._env.page

        # Quick liveness check
        try:
            if page is not None and not page.is_closed():
                await page.evaluate("1", timeout=1000)
                return
        except Exception:
            pass

        logger.warning("Active page is closed — attempting recovery")

        pages = self._context.pages
        if pages:
            self._env.page = pages[-1]
            logger.info(f"Recovered to existing page: {self._env.page.url}")
        else:
            new_page = await self._context.new_page()
            await new_page.goto(FaraQwen3Agent.DEFAULT_START_PAGE, timeout=30000)
            self._env.page = new_page
            logger.info("No open pages — created a new tab")

        # Re-register controller on new page
        await self._env._controller.on_new_page(self._env.page)

    async def _save_screenshot(self, filename: str, data: bytes | None = None) -> None:
        """Save a screenshot to output_dir if configured.

        Args:
            filename: e.g. "screenshot_1_pre.png"
            data: Screenshot bytes. If None, takes a fresh screenshot from env.
        """
        if not self.output_dir or not self._env:
            return
        if data is None:
            data = await self._env.get_screenshot()
        out = Path(self.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / filename).write_bytes(data)

    # ------------------------------------------------------------------
    # Validation (harness concern — not in core agent)
    # ------------------------------------------------------------------

    def _validate_action(self, action: dict[str, Any]) -> tuple[bool, str]:
        """Validate the structure and content of a parsed action.

        Covers all supported Fara agent actions.
        """
        try:
            if not isinstance(action, dict):
                return (
                    False,
                    f"Action must be a dict, got {type(action).__name__}",
                )
            if "arguments" not in action:
                return False, "Action missing 'arguments' field"

            args = action["arguments"]
            if not isinstance(args, dict):
                return (
                    False,
                    f"Arguments must be a dict, got {type(args).__name__}",
                )
            if "action" not in args:
                return False, "Arguments missing 'action' field"

            action_type = args["action"]
            if not isinstance(action_type, str):
                return (
                    False,
                    f"Action type must be string, got {type(action_type).__name__}",
                )

            # Coordinate validation — these actions require coordinate
            coord_required = (
                "click",
                "left_click",
                "hover",
                "mouse_move",
                "double_click",
                "right_click",
                "triple_click",
                "left_click_drag",
            )
            if action_type in coord_required:
                if "coordinate" not in args:
                    return (
                        False,
                        f"{action_type} requires 'coordinate' field",
                    )
                coord = args["coordinate"]
                if not isinstance(coord, (list, tuple)) or len(coord) != 2:
                    return (
                        False,
                        f"Coordinate must be [x, y], got: {coord}",
                    )
                if not all(isinstance(x, (int, float)) for x in coord):
                    return (
                        False,
                        f"Coordinate elements must be numbers: {coord}",
                    )

            # type/input_text with coordinates also need coordinate validation
            if action_type in ("type", "input_text") and "coordinate" in args:
                coord = args["coordinate"]
                if not isinstance(coord, (list, tuple)) or len(coord) != 2:
                    return (
                        False,
                        f"Coordinate must be [x, y], got: {coord}",
                    )

            if action_type == "visit_url":
                if "url" not in args:
                    return False, "visit_url missing 'url' field"
                if not isinstance(args["url"], str):
                    return (
                        False,
                        f"URL must be string, got {type(args['url']).__name__}",
                    )

            if action_type in ("input_text", "type"):
                # FaraQwen3Next type action doesn't require text (no-coord version)
                # But if coordinate is present, text is required
                if "coordinate" in args:
                    if "text" not in args and "text_value" not in args:
                        return (
                            False,
                            "type with coordinate missing 'text' field",
                        )

            if action_type == "web_search" and "query" not in args:
                return False, "web_search missing 'query' field"

            if action_type == "scroll" and "pixels" in args:
                if not isinstance(args["pixels"], (int, float)):
                    return (
                        False,
                        f"Scroll pixels must be number, got {type(args['pixels']).__name__}",
                    )

            if action_type == "hscroll" and "pixels" in args:
                if not isinstance(args["pixels"], (int, float)):
                    return (
                        False,
                        f"Hscroll pixels must be number, got {type(args['pixels']).__name__}",
                    )

            if action_type in ("keypress", "key") and "keys" in args:
                if not isinstance(args["keys"], list):
                    return (
                        False,
                        f"Keys must be a list, got {type(args['keys']).__name__}",
                    )

            if action_type == "read_page_answer_question":
                if "question" not in args:
                    return (
                        False,
                        "read_page_answer_question missing 'question' field",
                    )

            if action_type == "ask_user_question":
                if "question" not in args:
                    return (
                        False,
                        "ask_user_question missing 'question' field",
                    )

            if action_type == "terminate" and "answer" not in args:
                # Backward compat: old models use "thoughts" instead of "answer"
                if "thoughts" not in args:
                    return (
                        False,
                        "terminate missing 'answer' field",
                    )

            return True, ""
        except Exception as e:
            return False, f"Validation exception: {e}"
