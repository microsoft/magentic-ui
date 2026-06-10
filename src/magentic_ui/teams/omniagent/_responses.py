"""Conversation history and LLM I/O for a single OmniAgent session.

Defines :class:`OmniResponses`, which owns the conversation state and
all interaction with the OpenAI chat completions API for one agent run.

The class is the only place in OmniAgent that calls the LLM or mutates
the message list. Isolating these concerns keeps the agent loop
(tool dispatch, response parsing, pause/resume) focused on control flow
rather than I/O and bookkeeping.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import openai
from openai import AsyncOpenAI
from openai.lib.streaming.chat import (
    ContentDeltaEvent,
    FunctionToolCallArgumentsDeltaEvent,
    RefusalDeltaEvent,
)

from ...agents.message_schemas import (
    compaction_end_props,
    compaction_start_props,
)
from ...agents.web_surfer.fara._types import StreamUpdate
from ._compaction import (
    COMPACTION_PROMPT,
    HANDOFF_PREFIX,
    build_handoff_message,
    extract_opened_files,
    extract_summary,
)
from ._messages import Message, assistant_msg, system_msg, user_msg

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion

logger = logging.getLogger(__name__)

_RETRY_DELAY_SECONDS = 5.0
_MAX_RETRY_ATTEMPTS = 3
_MAX_EMERGENCY_COMPACTIONS = 2

# Stream events whose arrival means the model has started producing
# output. Matching against the SDK's concrete classes (rather than a
# ``.delta`` suffix) fails at import if the SDK renames them, instead of
# silently never emitting "generating".
_FIRST_TOKEN_EVENTS = (
    ContentDeltaEvent,
    RefusalDeltaEvent,
    FunctionToolCallArgumentsDeltaEvent,
)

# Default compaction threshold in tokens. When ``total_tokens`` from the
# most recent persistent generate call reaches this value, the next
# ``maybe_compact`` call summarizes history into a handoff message.
#
# Sized for the typical ~32K context target: leaves roughly 12K tokens
# of headroom below the context ceiling for the next round's tool
# output (~3K), assistant response (~4K), and a safety margin. Users
# running larger-context models can override via the constructor kwarg;
# a follow-up PR will wire this through YAML config.
DEFAULT_COMPACTION_THRESHOLD = 20_000

# Fraction of the model's advertised maximum context length to use as
# the new threshold when the emergency handler resizes after a
# context_length_exceeded error. Also used as the fallback multiplier
# applied to the current threshold when the max cannot be parsed.
_EMERGENCY_THRESHOLD_FRACTION = 0.75

# Extract the model's max context length from a context_length_exceeded
# error message. Phrasing matches OpenAI's format, which vLLM also
# copies verbatim into its error messages.
_CONTEXT_LENGTH_RE = re.compile(r"maximum context length is (\d+)")


def _is_context_length_exceeded(error: openai.BadRequestError) -> bool:
    """Detect a context_length_exceeded error across OpenAI and vLLM formats.

    Two detection paths because backends disagree on ``error.code``:

    - **OpenAI API** sets ``error.code = "context_length_exceeded"``
      (a string). Matches directly on the code field.
    - **vLLM** sets ``error.code = 400`` (the integer HTTP status)
      and only signals the specific condition via the error message
      phrasing. Detected via substring match on the message.

    Either path is sufficient — both OpenAI and vLLM use the same
    message phrasing (``"maximum context length is N tokens"``), so
    the message path covers vLLM and the code path covers OpenAI.
    """
    if error.code == "context_length_exceeded":
        return True
    return "maximum context length" in (error.message or "")


class OmniResponses:
    """Conversation state and LLM I/O for a single OmniAgent session.

    The history is seeded with the provided system prompt at
    construction time and grows through subsequent calls to
    :meth:`generate`. All history mutations, token accounting, and
    trajectory writes happen here — callers never touch the message
    list directly.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        system_prompt: str,
        transcripts_dir: Path | None = None,
        observability_dir: Path | None = None,
        guest_transcripts_dir: Path | None = None,
        compaction_threshold: int | None = DEFAULT_COMPACTION_THRESHOLD,
        source_name: str = "OmniAgent",
        temperature: float = 0.6,
    ) -> None:
        """Initialize an empty session seeded with the system prompt.

        Args:
            client: OpenAI async client used for chat completions calls.
            model: Model identifier passed on each completion request.
            system_prompt: System message placed at the start of the
                conversation.
            transcripts_dir: Host-side directory for ``transcript.md``
                (agent-visible). Pass ``None`` to disable.
            observability_dir: Host-side directory for ``trace.jsonl``
                and per-compaction snapshots (host-only). Pass ``None``
                to disable.
            guest_transcripts_dir: Sandbox-visible path to the directory
                where ``transcript.md`` lives. Used to build the
                handoff pointer.
            compaction_threshold: Token count at or above which
                :meth:`maybe_compact` summarizes history. ``None``
                disables compaction.
            source_name: Agent name stamped onto compaction stream
                events.
            temperature: Sampling temperature passed to the API on
                every call.
        """
        self._client = client
        self._model = model
        self._temperature = temperature
        self._messages: list[Message] = [system_msg(system_prompt)]
        self._total_tokens = 0
        self._round_counter = 0
        self._compaction_threshold = compaction_threshold
        self._source_name = source_name
        self._prev_handoff: str | None = None

        self._transcripts_dir = transcripts_dir
        self._observability_dir = observability_dir
        self._transcript_md_path: Path | None = None
        self._trace_jsonl_path: Path | None = None
        self._guest_transcript_md: Path | None = None
        self._compaction_count = 0

        if transcripts_dir is not None:
            transcripts_dir.mkdir(parents=True, exist_ok=True)
            self._transcript_md_path = transcripts_dir / "transcript.md"
            self._transcript_md_path.unlink(missing_ok=True)

        if observability_dir is not None:
            observability_dir.mkdir(parents=True, exist_ok=True)
            self._trace_jsonl_path = observability_dir / "trace.jsonl"
            self._trace_jsonl_path.unlink(missing_ok=True)

        if guest_transcripts_dir is not None:
            self._guest_transcript_md = guest_transcripts_dir / "transcript.md"

    # ------------------------------------------------------------------
    # Read-only state inspectors
    # ------------------------------------------------------------------

    @property
    def messages(self) -> list[Message]:
        """Shallow copy of the current conversation history.

        Returns a new list so callers cannot mutate internal state by
        appending or popping. Individual message dicts inside the list
        are the same references held by the session, so callers must
        treat them as read-only — mutating a message's ``content`` or
        ``role`` in place would corrupt the session's history.
        """
        return list(self._messages)

    @property
    def total_tokens(self) -> int:
        """Total tokens reported by the most recent persistent call.

        Set from ``response.usage.total_tokens`` after each
        :meth:`generate` call with ``persist=True``. Zero before the
        first persistent call.
        """
        return self._total_tokens

    # ------------------------------------------------------------------
    # Snapshot / restore (multi-turn resume)
    # ------------------------------------------------------------------

    def append_assistant_message(self, text: str) -> None:
        """Append an assistant message to history without an LLM call."""
        self._messages.append(assistant_msg(text))

    def snapshot_state(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the conversation state."""
        return {
            "messages": list(self._messages),
            "total_tokens": self._total_tokens,
            "prev_handoff": self._prev_handoff,
            "compaction_count": self._compaction_count,
        }

    def restore_state(self, loaded: dict[str, Any]) -> bool:
        """Replace conversation body from ``loaded``; keep current system prompt.

        All-or-nothing: returns ``False`` and leaves state untouched if any
        restored entry is missing a string ``role`` or a ``str | list`` ``content``.
        """
        messages_raw = loaded.get("messages")
        if not isinstance(messages_raw, list) or len(messages_raw) <= 1:  # pyright: ignore[reportUnknownArgumentType]
            return False
        messages = cast(list[Any], messages_raw)
        restored_body: list[Message] = []
        for m in messages[1:]:
            if not isinstance(m, dict):
                return False
            msg = cast(dict[str, Any], m)
            role = msg.get("role")
            content = msg.get("content")
            if not isinstance(role, str):
                return False
            if isinstance(content, list):
                # Multimodal content: each part must be a dict per the
                # OpenAI chat schema. Reject if any element isn't.
                content_list = cast(list[Any], content)
                if not all(isinstance(part, dict) for part in content_list):
                    return False
            elif not isinstance(content, str):
                return False
            restored_body.append(cast(Message, msg))
        if not restored_body:
            return False
        self._messages = [self._messages[0]] + restored_body
        tokens = loaded.get("total_tokens")
        if isinstance(tokens, int):
            self._total_tokens = tokens
        handoff = loaded.get("prev_handoff")
        if handoff is None or isinstance(handoff, str):
            self._prev_handoff = handoff
        compactions = loaded.get("compaction_count")
        if isinstance(compactions, int):
            self._compaction_count = compactions
        return True

    # ------------------------------------------------------------------
    # LLM entry point
    # ------------------------------------------------------------------

    async def generate(
        self,
        new_input: str | list[Message] | None = None,
        *,
        persist: bool = True,
        call_type: str = "round",
    ) -> str:
        """Back-compat wrapper around :meth:`generate_streaming`.

        Drains the streaming variant and returns just the assistant
        text, discarding the intermediate ``"generating"`` transition.
        Suitable for callers that only need the final text and do not
        surface streaming progress to the UI (e.g. compaction summary
        and final-answer fallback).
        """
        text = ""
        async for kind, payload in self.generate_streaming(
            new_input, persist=persist, call_type=call_type
        ):
            if kind == "result":
                text = cast(str, payload)
        return text

    async def generate_streaming(
        self,
        new_input: str | list[Message] | None = None,
        *,
        persist: bool = True,
        call_type: str = "round",
    ) -> AsyncIterator[tuple[Literal["state", "result"], Any]]:
        """Send the current history plus optional new input to the LLM.

        Yields ``("state", "generating")`` once the model starts replying
        (suppressed if the call fails before the first token), then
        ``("result", text)`` with the assistant's full response.

        On a context_length_exceeded error with ``persist`` True,
        emergency compaction runs in place and the call retries with the
        compacted history. The retry is gated on ``persist`` so the
        compaction summary call (``persist=False``) can't recurse.

        Args:
            new_input: Content to include on top of the existing
                history. A string is wrapped as a user message. A list
                of :class:`Message` is appended as-is. ``None`` sends
                the history unchanged.
            persist: Whether this call contributes to the ongoing
                conversation. When ``True`` (the normal agent loop
                case), ``new_input`` and the model's response are
                appended to history and :attr:`total_tokens` is
                refreshed. When ``False``, the call is a one-off —
                history and token count are left untouched. Use
                ``persist=False`` for auxiliary prompts whose output
                should not become part of the main conversation.
            call_type: Tag written to the ``llm_call`` trace event so
                consumers can distinguish main agent rounds
                (``"round"``, default) from auxiliary calls like
                ``"compaction"`` and ``"final_answer"``. Trace logging
                is unconditional — even ``persist=False`` calls land
                in ``trace.jsonl`` for observability.
        """
        extra = _normalize_input(new_input)

        emergency_attempts = 0
        response: ChatCompletion | None = None
        while True:
            prompt_messages = self._messages + extra
            try:
                async for kind, payload in self._call_api(prompt_messages):
                    if kind == "state":
                        yield ("state", payload)
                    else:
                        response = payload
                break
            except openai.BadRequestError as e:
                if not persist or not _is_context_length_exceeded(e):
                    raise
                if emergency_attempts >= _MAX_EMERGENCY_COMPACTIONS:
                    logger.error(
                        f"Context length still exceeded after "
                        f"{emergency_attempts} emergency compactions; "
                        f"giving up: {e}"
                    )
                    raise
                emergency_attempts += 1
                logger.warning(
                    f"Context length exceeded; forcing emergency compaction: {e}"
                )
                self._lower_threshold_from_error(e)
                await self._compact()
                # Loop back — rebuild prompt_messages with refreshed
                # self._messages (now compacted) plus the same extra.

        # Explicit guard (not assert, which -O strips): _call_api always
        # yields a result on the success path.
        if response is None:
            raise RuntimeError("_call_api returned without yielding a completion")
        text = response.choices[0].message.content or ""

        usage = response.usage
        if usage:
            logger.info(
                "LLM response: tokens(in=%d, out=%d, total=%d)",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )

        if persist:
            self._round_counter += 1

        # Always log to trace.jsonl — observability is independent of
        # persistence. Non-persistent calls (compaction, final-answer
        # fallback) share the round number of the last persistent round.
        await self._append_trace(
            {
                "event": "llm_call",
                "type": call_type,
                "round": self._round_counter,
                "prompt_messages": prompt_messages,
                "response": text,
                "tokens": {
                    "prompt": usage.prompt_tokens if usage else 0,
                    "completion": usage.completion_tokens if usage else 0,
                    "total": usage.total_tokens if usage else 0,
                },
            }
        )

        if persist:
            self._messages.extend(extra)
            self._messages.append(assistant_msg(text))
            self._total_tokens = usage.total_tokens if usage else 0
            await self._append_transcript(extra + [assistant_msg(text)])

        yield ("result", text)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _call_api(
        self, messages: list[Message]
    ) -> AsyncIterator[tuple[Literal["state", "result"], Any]]:
        """Invoke chat completions, retrying only transient errors.

        Yields ``("state", "generating")`` once the model starts replying
        (at most once per call), then ``("result", ChatCompletion)`` when
        the stream is drained. Streaming exists only to distinguish
        "waiting" from "replying"; tokens themselves are never surfaced.

        Retries transient errors (429, timeout, connection, 5xx) up to
        ``_MAX_RETRY_ATTEMPTS`` — but only before ``"generating"`` is
        emitted. After the model has started, a mid-stream failure is
        terminal: resending would regress the UI from "generating" back
        to "waiting" and waste the partial response.

        Permanent errors propagate immediately. The emergency
        context-length handler lives in :meth:`generate_streaming`, where
        the original ``new_input`` is in scope.

        Raises:
            RuntimeError: If every attempt hit a transient error.
            openai.OpenAIError: On any permanent error.
        """
        attempt = 0
        while True:
            generation_started = False
            try:
                async with self._client.chat.completions.stream(
                    model=self._model,
                    messages=messages,  # type: ignore[arg-type]  # Message is TypedDict
                    temperature=self._temperature,
                    top_p=0.8,
                    presence_penalty=1.0,
                    # Required for a usage block on streamed completions;
                    # without it token accounting resets to 0 and
                    # ``maybe_compact`` never fires.
                    stream_options={"include_usage": True},
                    extra_body={
                        "top_k": 20,
                        "min_p": 0,
                        "chat_template_kwargs": {"enable_thinking": False},
                    },
                ) as stream:
                    async for event in stream:
                        # A delta event means the model has started replying.
                        if not generation_started and isinstance(
                            event, _FIRST_TOKEN_EVENTS
                        ):
                            generation_started = True
                            yield ("state", "generating")
                    completion = await stream.get_final_completion()
                yield ("result", completion)
                return
            except openai.RateLimitError as e:
                if generation_started:
                    raise
                logger.warning(
                    "Rate limit (429); retrying in %.0fs: %s",
                    _RETRY_DELAY_SECONDS,
                    e,
                )
            except openai.APITimeoutError as e:
                if generation_started:
                    raise
                logger.warning(
                    "Request timeout; retrying in %.0fs: %s",
                    _RETRY_DELAY_SECONDS,
                    e,
                )
            except openai.APIConnectionError as e:
                if generation_started:
                    raise
                logger.warning(
                    "Connection error; retrying in %.0fs: %s",
                    _RETRY_DELAY_SECONDS,
                    e,
                )
            except openai.APIStatusError as e:
                if e.status_code < 500 or generation_started:
                    raise
                logger.warning(
                    "Server error %s; retrying in %.0fs: %s",
                    e.status_code,
                    _RETRY_DELAY_SECONDS,
                    e,
                )
            attempt += 1
            if attempt >= _MAX_RETRY_ATTEMPTS:
                raise RuntimeError(
                    f"Chat completion failed after {_MAX_RETRY_ATTEMPTS} "
                    f"attempts with transient errors"
                )
            await asyncio.sleep(_RETRY_DELAY_SECONDS)

    def _lower_threshold_from_error(self, error: openai.BadRequestError) -> None:
        """Lower ``compaction_threshold`` after a context_length_exceeded error.

        Parses the advertised maximum context length from the error
        message and sets the new threshold to
        ``max * _EMERGENCY_THRESHOLD_FRACTION``. Falls back to
        ``current * _EMERGENCY_THRESHOLD_FRACTION`` if the regex does
        not match, or leaves the threshold at ``None`` if it was
        already disabled.
        """
        old = self._compaction_threshold
        match = _CONTEXT_LENGTH_RE.search(error.message or "")
        new: int | None
        if match:
            new = int(int(match.group(1)) * _EMERGENCY_THRESHOLD_FRACTION)
        elif old is not None:
            new = int(old * _EMERGENCY_THRESHOLD_FRACTION)
        else:
            new = None
        self._compaction_threshold = new
        logger.warning(
            f"Lowering compaction threshold {old} -> {new} after context_length_exceeded"
        )

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    async def maybe_compact(self) -> AsyncIterator[StreamUpdate]:
        """Run compaction if history has crossed the threshold.

        Checks ``total_tokens`` against ``compaction_threshold``; if at
        or above, yields a ``compaction_start`` event, runs
        :meth:`_compact`, then yields a ``compaction_end`` event. No-op
        otherwise.

        Yields:
            Stream updates wrapping the compaction-start and
            compaction-end events when a compaction runs.
        """
        threshold = self._compaction_threshold
        if threshold is None or self._total_tokens < threshold:
            return
        logger.info(
            f"Compaction triggered: tokens={self._total_tokens} "
            f"threshold={threshold} round={self._round_counter}"
        )
        yield StreamUpdate(
            additional_properties=dict(
                compaction_start_props(
                    source=self._source_name,
                    tokens_before=self._total_tokens,
                )
            ),
        )
        await self._compact()
        yield StreamUpdate(
            additional_properties=dict(compaction_end_props(source=self._source_name)),
        )

    async def _compact(self) -> None:
        """Summarize history and replace it with a handoff user message.

        Steps:

        1. Hoist a trailing assistant message containing ``<tool_call>``
           if any — this preserves the agent's pending action across
           the compaction boundary so the loop's next step still has
           context for tool execution.
        2. Call the LLM with a compaction prompt and
           ``persist=False`` to generate the summary. The meta-call
           bypasses the emergency handler to avoid recursion.
        3. Rebuild history as ``[system, *real_user_msgs, handoff,
           *hoisted]``. Real user messages are kept verbatim;
           ``<tool_response>`` user messages are dropped since their
           content is distilled into the summary.
        4. Store the fresh summary as ``_prev_handoff`` so a later
           compaction can chain it.
        5. Reset ``total_tokens`` to ``0`` — the next persistent
           :meth:`generate` call will refresh it from the new usage.
        """
        # Counter advances once per compaction regardless of whether the
        # transcript snapshot succeeds, so trace numbering stays correct
        # even if disk logging has been disabled.
        self._compaction_count += 1

        # Step 1: hoist
        hoisted: list[Message] = []
        if self._messages:
            last = self._messages[-1]
            if last.get("role") == "assistant":
                content = last.get("content", "")
                if isinstance(content, str) and "<tool_call>" in content:
                    hoisted.append(self._messages.pop())

        tokens_before = self._total_tokens

        try:
            # Step 2: summarize. Strip the <summary> wrapper the prompt asks
            # the model to use; fall back to raw text if the wrapper is
            # missing or partial.
            raw_summary = await self.generate(
                new_input=[user_msg(COMPACTION_PROMPT)],
                persist=False,
                call_type="compaction",
            )
            summary = extract_summary(raw_summary)

            # Step 3: snapshot the transcript BEFORE mutating self._messages.
            # Best-effort — snapshot failure does not abort compaction.
            snapshot_path = await self._snapshot_transcript()

            # Step 4: rebuild history — keep real user messages verbatim, drop
            # tool responses (their content is summarized) and any previous
            # handoff (its summary is text-chained into the fresh handoff via
            # self._prev_handoff, so a verbatim copy would bloat history).
            system = self._messages[0]
            real_user_msgs = [
                m
                for m in self._messages[1:]
                if m.get("role") == "user"
                and not _is_skippable_user_content(m.get("content"))
            ]
            handoff = build_handoff_message(
                self._prev_handoff,
                summary,
                transcript_path=self._guest_transcript_md,
                files_reviewed=extract_opened_files(self._messages),
            )
            handoff_msg = user_msg(handoff)
            new_messages: list[Message] = [
                system,
                *real_user_msgs,
                handoff_msg,
                *hoisted,
            ]

            # Steps 5 and 6: commit
            self._messages = new_messages
            self._prev_handoff = summary
            self._total_tokens = 0

            # Step 7: record compaction in the disk log. Append only the
            # handoff to the transcript — the hoisted message was already
            # written when it originally appeared, and real_user_msgs were
            # written in prior rounds.
            await self._append_transcript([handoff_msg])
            await self._append_trace(
                {
                    "event": "compaction",
                    "round": self._round_counter,
                    "compaction_n": self._compaction_count,
                    "tokens_before": tokens_before,
                    "summary": summary,
                    "handoff": handoff,
                    "snapshot": str(snapshot_path) if snapshot_path else None,
                }
            )
        except Exception:
            # Restore the hoisted tool_call message so state stays
            # consistent if the summarize call raised partway through.
            if hoisted:
                self._messages.extend(hoisted)
            raise

    # ------------------------------------------------------------------
    # On-disk logging: transcript.md + trace.jsonl + snapshot copies
    # ------------------------------------------------------------------

    async def _append_transcript(self, items: list[Message]) -> None:
        """Append rendered messages to ``transcript.md``.

        No-op when ``transcripts_dir`` is not configured or has been
        disabled after a previous write failure. Writes run on a
        worker thread via :func:`asyncio.to_thread` so the event loop
        stays responsive even if the disk is slow.
        """
        if self._transcript_md_path is None or not items:
            return
        text = _render_items(items)
        try:
            await asyncio.to_thread(_append_text, self._transcript_md_path, text)
        except (OSError, UnicodeError) as exc:
            logger.warning(
                f"Disabling transcript after write failure "
                f"for {self._transcript_md_path}: {exc}"
            )
            self._transcript_md_path = None

    async def _append_trace(self, event: dict[str, Any]) -> None:
        """Append a JSON record to ``trace.jsonl``.

        No-op when tracing is not configured or has been disabled
        after a previous write failure. Non-serializable events
        propagate as ``TypeError`` — those are programmer bugs, not
        runtime conditions to swallow.
        """
        if self._trace_jsonl_path is None:
            return
        line = json.dumps({"ts": _now_iso(), **event}, ensure_ascii=False) + "\n"
        try:
            await asyncio.to_thread(_append_text, self._trace_jsonl_path, line)
        except (OSError, UnicodeError) as exc:
            logger.warning(
                f"Disabling trace after write failure "
                f"for {self._trace_jsonl_path}: {exc}"
            )
            self._trace_jsonl_path = None

    async def _snapshot_transcript(self) -> Path | None:
        """Copy the live transcript to ``transcript.compaction_N.md``.

        Runs on a worker thread. Returns the snapshot path on success,
        ``None`` when snapshotting is disabled or the source file is
        missing. A copy failure is logged but does not abort
        compaction — the agent still gets its summary; eval may miss
        one snapshot.
        """
        if (
            self._observability_dir is None
            or self._transcript_md_path is None
            or not self._transcript_md_path.exists()
        ):
            return None
        snapshot_path = (
            self._observability_dir
            / f"transcript.compaction_{self._compaction_count}.md"
        )
        try:
            await asyncio.to_thread(
                shutil.copy, self._transcript_md_path, snapshot_path
            )
            return snapshot_path
        except (OSError, shutil.SameFileError) as exc:
            logger.warning(
                f"Skipping compaction snapshot after copy failure "
                f"for {snapshot_path}: {exc}"
            )
            return None


def _now_iso() -> str:
    """Current UTC time in ISO-8601 format with trailing ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_text(path: Path, text: str) -> None:
    """Create the parent directory if needed and append ``text`` to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


def _render_items(items: list[Message]) -> str:
    """Render a list of messages as chronological markdown blocks.

    Each message becomes an ``### <Role>`` heading followed by a blank
    line and its content verbatim. Non-string content is serialized as
    JSON so the transcript stays grep-friendly for any message shape.
    """
    lines: list[str] = []
    for m in items:
        role = m["role"].capitalize()
        content = m["content"]
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        lines.append(f"### {role}\n\n{content}\n")
    return "\n".join(lines) + "\n"


def _is_skippable_user_content(content: str | list[dict[str, Any]] | None) -> bool:
    """True for user-message content that should be dropped during compaction.

    Compaction preserves real human input verbatim and summarizes the
    rest. User-role messages containing tool responses (which are bulk
    tool output) or a previous handoff (whose summary is already
    text-chained into the new handoff) are dropped.
    """
    if not isinstance(content, str):
        return False
    return content.lstrip().startswith(("<tool_response>", HANDOFF_PREFIX))


def _normalize_input(
    new_input: str | list[Message] | None,
) -> list[Message]:
    """Coerce the ``new_input`` parameter of :meth:`OmniResponses.generate`.

    Args:
        new_input: A string (new user message content), an existing
            list of messages (returned as a shallow copy), or ``None``
            (no extra messages).

    Returns:
        A list of :class:`Message` to append to the history for this
        call. Empty when ``new_input`` is ``None``.
    """
    if new_input is None:
        return []
    if isinstance(new_input, str):
        return [user_msg(new_input)]
    return list(new_input)
