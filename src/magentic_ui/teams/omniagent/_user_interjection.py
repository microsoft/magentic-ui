"""User-interjection wrappers for OmniAgent's mid-run inbox.

These shape mid-run user steerings into a tagged block the model treats
as a priority interjection rather than as additional task context.
"""

from __future__ import annotations


def format_user_interjection(queued: str) -> str:
    """Wrap a single mid-run user message OmniAgent drained itself."""
    return (
        "<user_interjection>\n"
        f"{queued}\n\n"
        "---\n"
        "The user just sent the above message while you "
        "were working (mid-run, no prompt was open).\n"
        "IMPORTANT: treat this as the user's CURRENT priority. "
        "If it changes your direction, switch now; if it's a "
        "question, answer it before continuing. Do NOT silently "
        "keep executing your previous plan.\n"
        "</user_interjection>"
    )


def format_subagent_interjection(sub_msgs: list[str]) -> str:
    """Wrap user steerings drained by a sub-agent (e.g. Fara)."""
    if len(sub_msgs) == 1:
        msg_block = sub_msgs[0]
        msg_intro = (
            "The user just sent this message DIRECTLY to your "
            "sub-agent (mid-run, while the sub-agent was working):"
        )
    else:
        msg_block = "\n\n".join(f"  ({i + 1}) {m}" for i, m in enumerate(sub_msgs))
        msg_intro = (
            f"The user sent {len(sub_msgs)} messages DIRECTLY to "
            "your sub-agent (mid-run, in chronological order):"
        )
    return (
        "<user_interjection_to_subagent>\n"
        f"{msg_intro}\n\n"
        f"{msg_block}\n\n"
        "---\n"
        "IMPORTANT: the sub-agent already acted on the "
        "above; its result is shown in the tool_response. "
        "Treat the user's message(s) as their CURRENT intent "
        "(latest one wins on conflict). Do NOT silently "
        "re-issue your previous plan to the sub-agent — that "
        "would override the user. If the sub-agent already "
        "satisfied the user, produce an <answer> now; "
        "otherwise, plan your next step around what the user "
        "just asked for, not your original task.\n"
        "</user_interjection_to_subagent>"
    )
