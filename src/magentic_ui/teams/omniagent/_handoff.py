"""Formats a sub-agent handoff into the OmniAgent tool_response body."""

from __future__ import annotations

from ...agents.message_schemas import HandoffInfo, HandoffReason, HandoffStatus

_NOTE_BY_REASON: dict[HandoffReason, str] = {
    HandoffReason.MAX_ROUNDS: (
        "NOTE: Fara stopped early after reaching the max rounds; "
        "the result below is partial."
    ),
    HandoffReason.ORPHAN_RECOVERY: (
        "NOTE: Fara was interrupted; this result was reconstructed on "
        "resume and is partial."
    ),
    HandoffReason.CONSECUTIVE_ERRORS: (
        "NOTE: Fara aborted after repeated errors; the result below is partial."
    ),
}
_NOTE_FALLBACK = "NOTE: Fara did not finish; the result below is partial."


def _dedupe(items: list[str]) -> list[str]:
    """Drop exact-duplicate strings, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_handoff(
    summary: str,
    *,
    status: HandoffStatus,
    reason: HandoffReason,
    last_url: str | None,
    facts: list[str],
) -> tuple[str, HandoffInfo]:
    """Build the tool_response body and the structured handoff info."""
    facts = _dedupe([f.strip() for f in facts if f.strip()])
    has_extras = bool(last_url) or bool(facts)

    blocks: list[str] = []
    if status != HandoffStatus.COMPLETED:
        blocks.append(_NOTE_BY_REASON.get(reason, _NOTE_FALLBACK))
    if last_url:
        blocks.append(f"LAST URL: {last_url}")
    if summary:
        blocks.append(f"SUMMARY:\n{summary}" if has_extras else summary)
    if facts:
        blocks.append("FACTS:\n" + "\n".join(f"- {f}" for f in facts))

    body = "\n\n".join(blocks)
    info: HandoffInfo = {
        "status": status.value,
        "reason": reason.value,
        "last_url": last_url,
        "facts": facts,
    }
    return body, info


def build_handoff_from_info(summary: str, info: HandoffInfo) -> str:
    """Build the tool_response body from a clean summary and HandoffInfo."""
    body, _ = build_handoff(
        summary,
        status=HandoffStatus(info["status"]),
        reason=HandoffReason(info["reason"]),
        last_url=info.get("last_url"),
        facts=list(info.get("facts") or []),
    )
    return body
