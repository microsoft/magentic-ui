"""OmniAgent orchestrator — agent loop and tool dispatch.

Runs the main round-based loop that drives a conversation with the
model: send a message, parse the response, execute tools, feed results
back, repeat. Terminates on ``<answer>`` from the model or when the
max-round cap is reached.

LLM I/O, history bookkeeping, and trajectory logging live in
:class:`OmniResponses` so this file can stay focused on control flow,
tool dispatch, pause/resume, and stream event emission.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from openai import AsyncOpenAI

from ...agents.message_schemas import (
    HandoffInfo,
    final_answer_props,
    reasoning_props,
    system_props,
    tool_call_props,
    tool_result_props,
)
from ...agents.registry import AgentRegistry
from ...agents.web_surfer.fara._types import StreamUpdate
from ...magentic_ui_config import AgentMode, ApprovalPolicy
from ...tools.playwright.browser import BrowserSlotPoolFullError
from ...types import (
    ApprovalRequest,
    InputRequest,
    LIVE_BROWSER_POOL_FULL_PROMPT,
    PauseController,
)
from ._continuation import handle_max_rounds_continuation, is_subagent_user_stop
from ...approval import (
    AGENT_INPUT_SESSION_AUTO_APPROVE,
    ApprovalStatus,
)
from ._command_policy import ClassificationResult, CommandVerdict
from ._errors import ToolCallError
from ._handoff import build_handoff_from_info
from ._harness import format_tool_output
from ._messages import Message, user_msg
from ._parse import ParseError, extract_answer, parse_response
from ._registry import TOOLS, Tool, build_delegate_cua_task
from ._responses import DEFAULT_COMPACTION_THRESHOLD, OmniResponses
from ._sandbox_utils import is_isolated_sandbox
from ._state_io import read_state, write_state
from ._system_prompt import build_system_prompt
from ._user_interjection import (
    format_subagent_interjection,
    format_user_interjection,
)
from .tools.host import ViewportState

if TYPE_CHECKING:
    from ...sandbox import Sandbox

logger = logging.getLogger(__name__)

DEFAULT_FINAL_ANSWER_PROMPT = (
    "Based on the work you've done above, provide a clear and concise "
    "final answer to the original task. Summarize what you found or "
    "accomplished. Wrap your answer in <answer></answer> tags."
)


# Prepended once to the first user message of every session. Bash word-
# splitting on unquoted whitespace silently breaks commands; the model has
# been observed to ignore the same advice when placed only in the system
# prompt, so we surface it in a user-role message where attention is higher.
_PATH_QUOTING_NUDGE = (
    "When calling bash, quote any path containing whitespace or shell "
    "metacharacters. Bash word-splits unquoted paths — an unquoted path "
    "with whitespace silently breaks the command. Example:\n"
    "  ls -la 'My Folder/file (1).pdf'   ← quoted, works\n"
    "  ls -la My Folder/file (1).pdf     ← unquoted, fails\n"
)


class OmniAgent:
    """Round-based agent orchestrator.

    Drives a single conversation: builds a system prompt, calls the LLM
    through :class:`OmniResponses`, parses the response, executes the
    requested tool, feeds the result back, and repeats until the model
    produces an ``<answer>`` or the round budget is exhausted.
    """

    name = "OmniAgent"

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        host_workspace: Path,
        sandbox: Sandbox | None = None,
        agent_registry: AgentRegistry | None = None,
        agent_mode: AgentMode = AgentMode.ALL,
        approval_policy: ApprovalPolicy = ApprovalPolicy.REQUIRE_APPROVAL_UNTRUSTED,
        pause_controller: PauseController | None = None,
        final_answer_prompt: str | None = None,
        compaction_threshold: int | None = DEFAULT_COMPACTION_THRESHOLD,
        temperature: float = 0.6,
        max_rounds: int = 100,
        observability_dir: Path | None = None,
        state_dir: Path | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._sandbox = sandbox
        self._is_sandbox = is_isolated_sandbox(sandbox)
        self._agent_registry = agent_registry or AgentRegistry()
        self._agent_mode = agent_mode
        self._approval_policy = approval_policy
        self._pause_controller = pause_controller
        self._final_answer_prompt = final_answer_prompt or DEFAULT_FINAL_ANSWER_PROMPT
        self._compaction_threshold = compaction_threshold
        self._temperature = temperature

        # Host workspace: for host-side Python I/O (writing files to disk)
        self._host_workspace = host_workspace
        # Guest workspace: what the agent sees inside the sandbox
        if sandbox is not None:
            self._guest_workspace = sandbox.to_guest_path(host_workspace)
        else:
            self._guest_workspace = host_workspace

        # Build tool list: core tools + registered agent tools.
        # Callers decide what to register (e.g. OMNIAGENT_ONLY mode passes
        # an empty registry); OmniAgent just rejects name collisions.
        self._tools: list[Tool] = list(TOOLS)
        core_names = {t.name for t in TOOLS}
        for entry in self._agent_registry:
            if entry.name in core_names:
                raise ValueError(
                    f"Registered agent tool '{entry.name}' conflicts with a "
                    f"core tool of the same name"
                )
            self._tools.append(Tool(name=entry.name, definition=entry.tool_definition))
        self._tool_map: dict[str, Tool] = {t.name: t for t in self._tools}
        logger.info(
            "OmniAgent tools: %s | registered_agents=%s | agent_mode=%s",
            [t.name for t in self._tools],
            [e.name for e in self._agent_registry],
            agent_mode,
        )

        # Viewport state (replaces MarkdownFileBrowser)
        self._viewport = ViewportState()

        # Conversation state. Lazily constructed on the first run_stream
        # call and reused across follow-up turns within the same agent
        # lifetime, so prior history is available when the user submits
        # additional input after a final answer.
        self._chat: OmniResponses | None = None

        # Cursor into PauseController._drain_log; reset at each
        # run_stream so prior tasks' sub-agent drains don't re-surface.
        self._sub_agent_drain_cursor: int = 0

        # Constants
        self._max_rounds = max_rounds
        self._max_tool_response_bytes = 12_000  # ~3K tokens for 32K context
        self._outputs_dir = host_workspace / ".agent" / "tool_outputs"
        self._transcripts_dir = host_workspace / ".agent" / "transcripts"
        # Observability dir is host-only — never mounted into the sandbox.
        # Caller decides where it lives. Defaults to a sibling of the
        # workspace mount when not supplied.
        self._observability_dir = (
            observability_dir
            if observability_dir is not None
            else host_workspace.parent / "observability" / host_workspace.name
        )

        # Per-session resume state; ``None`` disables persistence.
        # The file is read on the first ``run_stream`` call (off the event
        # loop via ``asyncio.to_thread``) so construction stays cheap.
        self._state_path: Path | None = (
            state_dir / "omni_state.json" if state_dir is not None else None
        )
        self._loaded_state: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public properties for tool execute functions
    # ------------------------------------------------------------------

    @property
    def sandbox(self) -> Sandbox | None:
        return self._sandbox

    @property
    def host_workspace(self) -> Path:
        """Host-side workspace path — for Python file I/O."""
        return self._host_workspace

    @property
    def guest_workspace(self) -> Path:
        """Guest-side workspace path — what the agent sees inside the sandbox."""
        return self._guest_workspace

    @property
    def viewport(self) -> ViewportState:
        """Viewport state for the file editor."""
        return self._viewport

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _drain_user_interjections(self, pending: list[Message]) -> None:
        """Append wrapped user interjections (own + sub-agent) to ``pending``."""
        pc = self._pause_controller
        if pc is None:
            return
        for queued in pc.drain_messages(reader=self.name):
            pending.append(user_msg(format_user_interjection(queued)))
        sub_msgs, self._sub_agent_drain_cursor = pc.messages_drained_by_others(
            my_reader=self.name,
            since_index=self._sub_agent_drain_cursor,
        )
        if sub_msgs:
            pending.append(user_msg(format_subagent_interjection(sub_msgs)))

    async def run_stream(self, task: str) -> AsyncIterator[StreamUpdate | InputRequest]:
        """Stream agent execution. Yields StreamUpdate, InputRequest, or ApprovalRequest."""
        if self._chat is None:
            if self._state_path is not None:
                self._loaded_state = await asyncio.to_thread(
                    read_state, self._state_path
                )
            system_prompt = build_system_prompt(
                self._tools,
                str(self._guest_workspace),
                capabilities=self._agent_registry.capabilities(),
                sandbox=self._sandbox,
            )
            self._chat = OmniResponses(
                client=self._client,
                model=self._model,
                system_prompt=system_prompt,
                transcripts_dir=self._transcripts_dir,
                observability_dir=self._observability_dir,
                guest_transcripts_dir=self._to_guest_path(self._transcripts_dir),
                compaction_threshold=self._compaction_threshold,
                source_name=self.name,
                temperature=self._temperature,
            )
            resumed = self._apply_loaded_state(self._chat)
            if not resumed:
                # Fresh session: prepend a path-quoting nudge to the task
                # so the model sees the pattern in a user-role message
                # (higher attention than the same advice buried in the
                # system prompt). On resume, the nudge is already in the
                # first user message of the restored history.
                task = f"{_PATH_QUOTING_NUDGE}\n{task}"
        chat = self._chat
        # Outbox of user-role messages waiting to be sent on the next
        # generate call. Starts with the task, accumulates tool responses,
        # pause replies, and error nudges between rounds. Consumed and
        # cleared each time chat.generate() runs.
        pending: list[Message] = []
        orphan_response = await self._close_orphan_tool_call(chat)
        if orphan_response is not None:
            pending.append(orphan_response)
        pending.append(user_msg(task))

        consecutive_parse_errors = 0
        max_parse_retries = 3
        bare_text_retries = 0

        self._sub_agent_drain_cursor = (
            self._pause_controller.drain_log_cursor
            if self._pause_controller is not None
            else 0
        )

        round_num = 0
        total_rounds = 0
        while True:
            if round_num >= self._max_rounds:
                should_continue = False
                final_answer_text = ""
                async for evt in handle_max_rounds_continuation(
                    source_name=self.name,
                    total_rounds=total_rounds,
                    generate_final_answer=lambda: self._generate_final_answer(
                        chat, pending
                    ),
                ):
                    if isinstance(evt, bool):
                        should_continue = evt
                    else:
                        if (
                            isinstance(evt, StreamUpdate)
                            and evt.additional_properties.get("type") == "final_answer"
                            and isinstance(evt.text, str)
                        ):
                            final_answer_text = evt.text
                        yield evt
                if not should_continue:
                    # ``_generate_final_answer`` runs with persist=False
                    # so the synthetic wrap-up prompt stays out of
                    # history. Inject just the answer text here, wrapped
                    # in ``<answer>`` tags so the persisted shape
                    # matches the normal final-answer round.
                    if final_answer_text:
                        chat.append_assistant_message(
                            f"<answer>{final_answer_text}</answer>"
                        )
                    await self._save_state()
                    return
                round_num = 0
                continue
            round_num += 1
            total_rounds += 1
            logger.info("Round %d/%d", round_num, self._max_rounds)

            self._drain_user_interjections(pending)

            # --- Pause check (before LLM call) ---
            pause_request = self._make_pause_request()
            if pause_request is not None:
                request, future = pause_request
                yield request
                user_response = await future
                pending.append(user_msg(user_response))

            # --- LLM call ---
            response_text = await chat.generate(pending)
            pending = []

            # --- Drain any compaction events triggered by this round ---
            async for evt in chat.maybe_compact():
                yield evt
            # Persist after compaction so the on-disk snapshot matches
            # the final post-compaction history and compaction_count.
            await self._save_state()

            # --- Parse response ---
            try:
                parsed = parse_response(response_text)
                consecutive_parse_errors = 0
            except Exception as e:
                consecutive_parse_errors += 1
                if consecutive_parse_errors >= max_parse_retries:
                    logger.error("Parse failed %d times, skipping", max_parse_retries)
                    yield StreamUpdate(
                        additional_properties=dict(
                            system_props(self.name, "error", str(e))
                        ),
                    )
                    consecutive_parse_errors = 0
                    continue

                logger.warning("Parse error, feeding back: %s", e)
                pending.append(
                    user_msg(
                        f"<tool_response>Error: Could not parse your response. "
                        f"Please use <tool_call> or <answer> tags. Details: {e}</tool_response>"
                    )
                )
                continue

            # --- Yield reasoning ---
            if parsed.thoughts:
                yield StreamUpdate(
                    text=parsed.thoughts,
                    additional_properties=dict(reasoning_props(source=self.name)),
                )

            # --- Check answer ---
            if parsed.answer is not None:
                yield StreamUpdate(
                    text=parsed.answer,
                    additional_properties=dict(final_answer_props(source=self.name)),
                )
                return

            # --- No tool call blocks → bare text; nudge once then treat as done ---
            if not parsed.tool_call_blocks:
                bare_text_retries += 1
                if bare_text_retries <= 1:
                    pending.append(
                        user_msg(
                            "<tool_response>Your response did not contain a "
                            "<tool_call> or <answer> tag. If you are done, wrap "
                            "your final answer in <answer>...</answer> tags. "
                            "If not, use <tool_call> to take action.</tool_response>"
                        )
                    )
                    continue

                final_text = parsed.thoughts or "Task complete."
                yield StreamUpdate(
                    text=final_text,
                    additional_properties=dict(final_answer_props(source=self.name)),
                )
                return

            # --- Execute tool call blocks sequentially ---
            # Per-block results (success or parse error) are accumulated in
            # original order and concatenated as one user message at the end
            # of the batch. Mid-batch user_input or decline-with-alt aborts
            # the remaining calls (state changed). Hard verdicts (DENY, user
            # "no") still terminate the run.
            results: list[str] = []
            user_stopped_any_subagent = False

            for block in parsed.tool_call_blocks:
                if isinstance(block, ParseError):
                    results.append(f"Error parsing {block.message}")
                    continue

                tool_call = block.call
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("arguments", {})
                # Lenient fallback: some models emit args at the top level
                # instead of nested under `arguments`, e.g.
                # {"name":"bash","command":"ls"} rather than
                # {"name":"bash","arguments":{"command":"ls"}}. Without this
                # the bash tool receives an empty command and the model can
                # loop indefinitely on the same broken format. Use the
                # tool's declared parameter names as a whitelist so we
                # don't forward unrelated top-level keys.
                if not tool_args and tool_name in self._tool_map:
                    valid_params = (
                        self._tool_map[tool_name]
                        .definition.get("function", {})
                        .get("parameters", {})
                        .get("properties", {})
                    )
                    tool_args = {
                        k: tool_call[k] for k in valid_params if k in tool_call
                    }
                tool_call_id = str(uuid4())

                if not tool_name:
                    error_output = ToolCallError(
                        "tool call missing 'name' field"
                    ).to_output()
                    # Emit tool_call + tool_result events so the frontend /
                    # trajectory log keeps the one-pair-per-block invariant.
                    yield StreamUpdate(
                        additional_properties=dict(
                            tool_call_props(
                                source=self.name,
                                tool="<missing>",
                                tool_args=tool_args,
                                tool_call_id=tool_call_id,
                            )
                        ),
                    )
                    yield StreamUpdate(
                        text=error_output,
                        additional_properties=dict(
                            tool_result_props(
                                source=self.name,
                                tool_call_id=tool_call_id,
                                tool="<missing>",
                            )
                        ),
                    )
                    results.append(error_output)
                    continue

                # --- Approval check (harness handles yes/no directly) ---
                tool_entry = self._tool_map.get(tool_name)
                approval_status: str | None = None
                approval_result = _check_tool_approval(
                    tool_entry,
                    tool_name,
                    tool_args,
                    self._approval_policy,
                    self._is_sandbox,
                    current_file=self._viewport.current_file,
                )

                if approval_result.verdict == CommandVerdict.DENY:
                    logger.info("Tool %s denied by policy", tool_name)
                    yield StreamUpdate(
                        additional_properties=dict(
                            system_props(
                                self.name,
                                "stopped",
                                approval_result.reason or "This action is not allowed.",
                            )
                        ),
                    )
                    return

                if approval_result.verdict == CommandVerdict.ALLOW:
                    if self._approval_policy == ApprovalPolicy.AUTO_APPROVE:
                        approval_status = ApprovalStatus.AUTO_POLICY
                    else:
                        approval_status = ApprovalStatus.AUTO_SAFE

                if approval_result.verdict == CommandVerdict.REQUIRE_APPROVAL:
                    approval_future: asyncio.Future[str] = (
                        asyncio.get_running_loop().create_future()
                    )
                    yield ApprovalRequest(
                        prompt=_format_approval_prompt(tool_name, tool_args),
                        respond=approval_future.set_result,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        category=approval_result.category or "",
                        reason=approval_result.reason,
                    )
                    user_response = await approval_future
                    normalized = user_response.strip().lower().rstrip(".!,")

                    if normalized in ("yes", "approve"):
                        approval_status = ApprovalStatus.USER
                    elif normalized == AGENT_INPUT_SESSION_AUTO_APPROVE:
                        approval_status = ApprovalStatus.AUTO_SESSION
                    elif normalized in ("no", "deny"):
                        logger.info("User denied tool %s", tool_name)
                        yield StreamUpdate(
                            additional_properties=dict(
                                system_props(
                                    self.name,
                                    "stopped",
                                    "User denied the requested action.",
                                )
                            ),
                        )
                        return
                    else:
                        # Alternative instructions — abort batch, model re-plans
                        results.append(
                            f"The user declined the `{tool_name}` call and "
                            f"provided alternative instructions: {user_response}"
                        )
                        break

                # Yield tool call event (only for tools that will actually execute)
                yield StreamUpdate(
                    text=f"Using tool: {tool_name}",
                    additional_properties=dict(
                        tool_call_props(
                            source=self.name,
                            tool=tool_name,
                            tool_args=tool_args,
                            tool_call_id=tool_call_id,
                            approval_status=approval_status,
                        )
                    ),
                )

                # Dispatch: registry agent / request_user_input / regular tool
                tool_result = ""
                last_handoff: HandoffInfo | None = None
                is_user_input = False
                sub_agent_user_stopped = False
                agent_entry = (
                    self._agent_registry.get(tool_name)
                    if tool_name in self._tool_map
                    else None
                )
                if agent_entry is not None:
                    if tool_name == "delegate_cua":
                        # tool_args comes from model JSON — coerce to expected
                        # shapes so a malformed value doesn't abort the run.
                        raw_task = tool_args.get("task", "")
                        raw_context = tool_args.get("context", "")
                        raw_files = tool_args.get("files")
                        file_paths: list[str] = []
                        if isinstance(raw_files, list):
                            for item in raw_files:  # pyright: ignore[reportUnknownVariableType]
                                if isinstance(item, str):
                                    file_paths.append(item)
                        sub_kwargs = {
                            "task": await build_delegate_cua_task(
                                self,
                                task=raw_task if isinstance(raw_task, str) else "",
                                context=raw_context
                                if isinstance(raw_context, str)
                                else "",
                                file_paths=file_paths,
                            )
                        }
                    else:
                        sub_kwargs = tool_args

                    last_text = ""
                    while True:
                        try:
                            async for event in agent_entry.agent.run_stream(
                                **sub_kwargs
                            ):
                                yield event
                                if isinstance(event, StreamUpdate) and event.text:
                                    last_text = event.text
                                    props = event.additional_properties or {}
                                    if props.get("type") == "final_answer":
                                        handoff = props.get("handoff")
                                        if isinstance(handoff, dict):
                                            last_handoff = cast(HandoffInfo, handoff)
                                if is_subagent_user_stop(event):
                                    sub_agent_user_stopped = True
                            tool_result = last_text or "Task completed"
                            if sub_agent_user_stopped:
                                user_stopped_any_subagent = True
                            break
                        except TypeError as e:
                            tool_result = ToolCallError(
                                f"{tool_name}: invalid arguments ({e})"
                            ).to_output()
                            break
                        except BrowserSlotPoolFullError:
                            # Wait on user reply, then retry; preserves
                            # in-memory chat history / viewport / tool outputs.
                            future: asyncio.Future[str] = (
                                asyncio.get_running_loop().create_future()
                            )
                            yield InputRequest(
                                prompt=LIVE_BROWSER_POOL_FULL_PROMPT,
                                respond=future.set_result,
                            )
                            await future

                elif tool_name == "request_user_input":
                    is_user_input = True
                    prompt = tool_args.get(
                        "prompt", "Please provide input to continue."
                    )
                    future: asyncio.Future[str] = (
                        asyncio.get_running_loop().create_future()
                    )
                    yield InputRequest(prompt=prompt, respond=future.set_result)
                    user_response = await future
                    tool_result = f"User response: {user_response}"
                else:
                    tool = self._tool_map.get(tool_name)
                    if tool is None:
                        tool_result = ToolCallError(
                            f"Unknown tool: {tool_name}. "
                            f"Available: {', '.join(self._tool_map)}"
                        ).to_output()
                    elif tool.execute is None:
                        tool_result = ToolCallError(
                            f"{tool_name} is not directly executable"
                        ).to_output()
                    else:
                        if tool_name in ("scroll_down", "scroll_up"):
                            self._viewport.scroll_count += 1
                        else:
                            self._viewport.scroll_count = 0
                        try:
                            output = await tool.execute(self, **tool_args)
                            tool_result = output.to_output(self._viewport)
                        except Exception as e:
                            tool_result = ToolCallError(f"{tool_name}: {e}").to_output()
                            logger.error(
                                "Tool %s failed: %s", tool_name, e, exc_info=True
                            )

                # Truncate per-call output
                tool_result = format_tool_output(
                    data={"output": tool_result},
                    truncatable_fields=["output"],
                    budget=self._max_tool_response_bytes,
                    outputs_dir=self._outputs_dir,
                    to_guest_path=self._to_guest_path,
                )

                # Model gets the handoff envelope; the UI event stays clean.
                model_result = (
                    build_handoff_from_info(tool_result, last_handoff)
                    if last_handoff is not None
                    else tool_result
                )
                results.append(model_result.strip())

                # Yield tool result event
                yield StreamUpdate(
                    text=tool_result,
                    additional_properties=dict(
                        tool_result_props(
                            source=self.name,
                            tool_call_id=tool_call_id,
                            tool=tool_name,
                        )
                    ),
                )

                # User-input changes world state — abort remaining batch
                if is_user_input:
                    break

                # Sub-agent user-stop also aborts the rest of the batch:
                # any later tool_call in the same response (e.g. a second
                # delegate_cua) would re-run the just-stopped task before
                # the "do not re-delegate" directive (appended below) is
                # ever sent to the model.
                if sub_agent_user_stopped:
                    break

            # Combine all batched results into a single user message
            if results:
                combined = "\n".join(
                    f"<tool_response>{r.strip()}</tool_response>" for r in results
                )
                pending.append(user_msg(combined))

            if user_stopped_any_subagent:
                pending.append(
                    user_msg(
                        "<system>The user stopped a sub-agent before "
                        "completion. Do not re-delegate the same task. "
                        "Treat the sub-agent's summary above as final and "
                        "either answer with what was collected or ask the "
                        "user how to proceed.</system>"
                    )
                )

            # --- Pause check (after batch) ---
            pause_request = self._make_pause_request()
            if pause_request is not None:
                request, future = pause_request
                yield request
                user_response = await future
                pending.append(user_msg(user_response))

    # ------------------------------------------------------------------
    # Final answer generation
    # ------------------------------------------------------------------

    async def _generate_final_answer(
        self, chat: OmniResponses, pending: list[Message]
    ) -> str:
        """Call the LLM with a final-answer prompt on top of current state.

        Sends the in-flight outbox plus a final-answer prompt without
        persisting either into the session. Used as the max-rounds
        fallback path so the conversation history is left untouched
        for any post-mortem inspection.
        """
        raw = await chat.generate(
            pending + [user_msg(self._final_answer_prompt)],
            persist=False,
            call_type="final_answer",
        )

        answer = extract_answer(raw)
        if answer is not None:
            return answer

        return raw.strip()

    # ------------------------------------------------------------------
    # Pause
    # ------------------------------------------------------------------

    def _make_pause_request(
        self,
    ) -> tuple[InputRequest, asyncio.Future[str]] | None:
        """If paused, create an InputRequest + Future. Otherwise return None."""
        if not self._pause_controller or not self._pause_controller.is_paused:
            return None
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        return (
            InputRequest(
                prompt="Task paused. Please type a message to continue or provide additional instructions.",
                respond=future.set_result,
            ),
            future,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_guest_path(self, path: Path) -> Path:
        """Translate host path to guest path for sandbox."""
        if self._sandbox is not None and hasattr(self._sandbox, "to_guest_path"):
            return self._sandbox.to_guest_path(path)
        return path

    def _apply_loaded_state(self, chat: OmniResponses) -> bool:
        """Restore conversation and viewport from the preloaded state payload."""
        loaded = self._loaded_state
        self._loaded_state = {}
        if not loaded:
            return False
        restored = chat.restore_state(loaded)
        if not restored:
            # Don't touch viewport if the conversation didn't restore;
            # the agent is treated as fresh, so viewport must be too.
            return False
        viewport_raw = loaded.get("viewport")
        if isinstance(viewport_raw, dict):
            viewport: dict[str, Any] = cast(dict[str, Any], viewport_raw)
            current_file = viewport.get("current_file")
            if current_file is None or isinstance(current_file, str):
                self._viewport.current_file = current_file
            current_line = viewport.get("current_line")
            if isinstance(current_line, int):
                self._viewport.current_line = current_line
            scroll_count = viewport.get("scroll_count")
            if isinstance(scroll_count, int):
                self._viewport.scroll_count = scroll_count
        return True

    async def _close_orphan_tool_call(self, chat: OmniResponses) -> Message | None:
        """Build a synthetic tool_response for an unanswered tool_call, or None."""
        messages = chat.messages
        if not messages:
            return None
        last = messages[-1]
        if last.get("role") != "assistant":
            return None
        content = last.get("content", "")
        if not isinstance(content, str):
            return None
        if "<tool_call>" not in content or "<answer>" in content:
            return None

        parsed = parse_response(content)
        if not parsed.tool_call_blocks:
            return None

        parts: list[str] = []
        for block in parsed.tool_call_blocks:
            if isinstance(block, ParseError):
                parts.append(
                    "<tool_response>Previous tool call could not be parsed "
                    "and produced no result.</tool_response>"
                )
                continue
            call = block.call
            tool_name = call.get("name", "") if isinstance(call, dict) else ""
            tool_name = tool_name if isinstance(tool_name, str) else ""
            summary = await self._summarize_orphan_tool(tool_name)
            parts.append(f"<tool_response>{summary}</tool_response>")
        return user_msg("\n".join(parts))

    async def _summarize_orphan_tool(self, tool_name: str) -> str:
        """Build tool_response text for an interrupted tool."""
        agent_entry = self._agent_registry.get(tool_name) if tool_name else None
        if agent_entry is not None:
            summarizer = getattr(agent_entry.agent, "summarize_progress", None)
            if summarizer is not None:
                try:
                    text, info = await summarizer()
                    if isinstance(text, str) and text.strip():
                        return build_handoff_from_info(text.strip(), info)
                except Exception as exc:
                    logger.warning(
                        "summarize_progress failed for %r: %s", tool_name, exc
                    )
        label = tool_name or "previous tool"
        return (
            f"The previous `{label}` call was interrupted by the user "
            "before it could return. No partial output is available. "
            "Continue using only the information already in this "
            "conversation."
        )

    async def _save_state(self) -> None:
        """Write the current conversation and viewport to omni_state.json."""
        if self._state_path is None or self._chat is None:
            return
        payload = self._chat.snapshot_state()
        payload["viewport"] = {
            "current_file": self._viewport.current_file,
            "current_line": self._viewport.current_line,
            "scroll_count": self._viewport.scroll_count,
        }
        await asyncio.to_thread(write_state, self._state_path, payload)

    async def close(self) -> None:
        """Clean up resources.

        Closes the underlying ``AsyncOpenAI`` HTTP client so the httpx
        connection pool / file descriptors are released
        deterministically. Without this, long-running processes
        (server mode) leak FDs across sessions. The reference is left
        in place — calling ``run_stream`` after ``close`` would fail
        with a "client closed" error from openai, which is the right
        signal.
        """
        await self._client.close()
        await self._agent_registry.close_all()


# ------------------------------------------------------------------
# Approval helpers (module-level, used by OmniAgent.run_stream)
# ------------------------------------------------------------------


def _format_approval_prompt(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Build a human-readable approval prompt for the given tool call."""
    if tool_name == "bash":
        cmd = tool_args.get("command", "")
        return (
            f"The agent wants to run the following bash command:\n"
            f"```\n{cmd}\n```\n"
            f"Do you approve? (`yes`/`no`, or suggest an alternative)"
        )
    args_summary = ", ".join(f"`{k}={v!r}`" for k, v in tool_args.items())
    return (
        f"The agent wants to use tool `{tool_name}`"
        f" with arguments: {args_summary}\n"
        f"Do you approve? (`yes`/`no`, or suggest an alternative)"
    )


def _check_tool_approval(
    tool_entry: Tool | None,
    tool_name: str,
    tool_args: dict[str, Any],
    policy: ApprovalPolicy,
    is_sandbox: bool,
    *,
    current_file: str | None = None,
) -> ClassificationResult:
    """Determine the approval verdict for a tool call.

    Returns a full ``ClassificationResult`` with verdict, category, and
    reason so callers can propagate metadata to approval requests.

    The verdict depends on four dimensions:

    1. **Approval Policy** (outermost):

       - ``auto_approve``: everything → ALLOW.
       - ``require_approval_untrusted`` (default): classifiers decide.
       - ``require_approval_all``: everything → REQUIRE_APPROVAL.

    2. **Tool type** — determines *which* classifier runs:

       - ``bash``: ``classify_bash_command`` (command name + flags,
         no sandbox/path awareness).
       - ``create`` / ``edit`` / ``insert``: ``classify_file_tool``
         (path + sandbox awareness).
       - Read-only tools (``open``, ``goto``, ``scroll_*``,
         ``search_*``, ``find_file``, ``request_user_input``,
         ``delegate_cua``): always ALLOW (no classifier,
         ``requires_approval=False``).

    3. **Sandbox type** (file tools only):

       - Isolated sandbox (``is_sandbox=True``, e.g. Quicksand):
         workspace writes are safe.
       - NullSandbox or no sandbox (``is_sandbox=False``): all writes
         need approval.

    4. **Path** (file tools only):

       - ``/workspace/…`` + isolated sandbox → ALLOW.
       - ``/mounts/…`` or other → REQUIRE_APPROVAL.

    See ``_command_policy`` module docstring for classifier details.
    """
    _allow = ClassificationResult(CommandVerdict.ALLOW, None, "")

    if policy == ApprovalPolicy.AUTO_APPROVE:
        return _allow

    if policy == ApprovalPolicy.REQUIRE_APPROVAL_ALL:
        return ClassificationResult(
            CommandVerdict.REQUIRE_APPROVAL, None, "All tools require approval."
        )

    if tool_entry is None:
        # Unknown tool — will error downstream, don't prompt
        return _allow

    # require_approval_untrusted: use classifier if available
    if tool_entry.approval_check is not None:
        # Inject _current_file for edit/insert (which have no filename arg)
        enriched_args = tool_args
        if current_file and "_current_file" not in tool_args:
            enriched_args = {**tool_args, "_current_file": current_file}
        return tool_entry.approval_check(tool_name, enriched_args, is_sandbox)

    # Fallback: boolean flag
    if tool_entry.requires_approval:
        return ClassificationResult(
            CommandVerdict.REQUIRE_APPROVAL, None, "This tool requires approval."
        )

    return _allow
