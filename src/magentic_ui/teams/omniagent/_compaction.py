"""Context compaction helpers for OmniAgent.

Provides the prompt strings and message-assembly helper used by
:class:`OmniResponses` when the conversation history crosses the
compaction threshold.

Compaction replaces the bulk of the history with a single user message
containing an LLM-generated summary. The prompt constants and handoff
framing live here so they are easy to find, review, and adjust without
touching the LLM I/O code.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ._parse import ParsedToolCall, parse_response

if TYPE_CHECKING:
    from ._messages import Message

COMPACTION_PROMPT = """\
A previous LLM has been working on this task. Your job now is different: \
write a structured handoff summary so another LLM can resume the work \
seamlessly.

IMPORTANT: This is a meta-task. Ignore the system prompt's rule about \
wrapping every response in <tool_call> or <answer> tags. Do NOT call any \
tools. Wrap your summary in <summary>...</summary> tags and write only \
that — no other content.

Inside <summary>, use these EXACT section headings:

## Task
One-sentence description of what the user asked for.

## Actions Completed
Numbered list of every concrete action taken. Be specific — include \
exact file names, paths, URLs, commands, rename pairs, form fields, \
search queries, or values. Example entries:
- Renamed `doc1.pdf` → `Tax_Return_2025.pdf`
- Visited https://example.com/dashboard and extracted the Q3 revenue figure ($4.2M)
- Ran `pip install pandas` and confirmed import works
- Asked user about preferred folder structure; they chose by-date

## Current State
Where the work stands right now:
- Position in any iteration (e.g., "processed files A–M, next is notes.txt")
- Data collected so far (key values, intermediate results, accumulated lists)
- Any files or resources currently open
- Errors encountered and how they were resolved

## Remaining Work
Exact items still to be done, in order. If iterating over a list, \
name the specific unprocessed items. If the task is open-ended, \
describe the next concrete step.

## User Preferences & Constraints
Any rules, preferences, or decisions the user communicated or confirmed \
during the session (e.g., naming conventions, sites to use, format \
requirements, items to skip).

Be exhaustive on specifics and terse on prose. Prefer bullet lists over \
paragraphs. The next LLM has zero memory — anything you omit is lost."""


HANDOFF_PREFIX = """\
Another language model started to solve this problem and produced a summary \
of its thinking process. Trust the summary's facts and continue from where \
the previous LLM left off. The files listed under "Files already reviewed" \
have been read and their key facts are in the summary — you may re-open or \
scroll within them if you need a specific detail not captured, but don't \
re-read them just to verify the summary. Here is the summary:"""


def extract_summary(text: str) -> str:
    """Extract content from ``<summary>...</summary>`` tags.

    Tolerates partial tagging from the model:

    - Both tags present: returns the text between them.
    - Only opening tag: returns everything after it.
    - Only closing tag: returns everything before it.
    - Neither tag: returns the raw text (stripped).

    All return values are stripped of leading/trailing whitespace.
    """
    open_tag, close_tag = "<summary>", "</summary>"
    has_open = open_tag in text
    has_close = close_tag in text

    start = text.index(open_tag) + len(open_tag) if has_open else 0
    if has_close:
        # When both tags are present, look for the close tag *after* the
        # open tag — an in-prose ``</summary>`` before the wrapper must
        # not anchor the extraction. ``str.find`` returns -1 on miss so
        # ``"noise</summary><summary>real"`` (close-before-open with no
        # close-after-open) cleanly falls through to the open-only path
        # below instead of raising.
        end = text.find(close_tag, start)
        if end != -1:
            return text[start:end].strip()
    return text[start:].strip()


def extract_opened_files(messages: list[Message]) -> list[str]:
    """Return unique task-file paths from `open` tool calls; skip `.agent/` paths."""
    seen: set[str] = set()
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        for block in parse_response(content).tool_call_blocks:
            if not isinstance(block, ParsedToolCall):
                continue
            if block.call.get("name") != "open":
                continue
            path = block.call.get("arguments", {}).get("path")
            if not isinstance(path, str):
                continue
            # Skip internal harness artifacts (spill files, transcript log).
            if "/.agent/" in path or path.startswith(".agent/"):
                continue
            seen.add(path)
    return sorted(seen)


def build_handoff_message(
    prev_handoff: str | None,
    summary: str,
    transcript_path: Path | None = None,
    files_reviewed: list[str] | None = None,
) -> str:
    """Assemble the user-role message that replaces old history after compaction."""
    parts = [HANDOFF_PREFIX]
    if prev_handoff:
        parts.append(f"\n\nPrevious handoff:\n{prev_handoff}")
    parts.append(f"\n\n{summary}")
    if files_reviewed:
        files_block = "\n".join(f"- {p}" for p in files_reviewed)
        parts.append(f"\n\nFiles already reviewed:\n{files_block}")
    if transcript_path is not None:
        parts.append(
            f"\n\nThe previous LLM's full action log (its tool calls and "
            f"reasoning) is saved at `{transcript_path}`. Open it or `grep` "
            f"it via the bash tool if you need details not captured above. "
            f"This file is the agent's own log — not a task data file."
        )
    return "".join(parts)
