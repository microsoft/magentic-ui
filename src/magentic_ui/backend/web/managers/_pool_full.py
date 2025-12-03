"""Pool-full handling for the websurfer_only mode.

When a top-level FaraWebSurfer fails to acquire a Quicksand browser slot,
this module surfaces an InputRequest and replays the run on user reply.

In ``all`` mode OmniAgent catches the same error inside its own run loop
and never reaches these helpers.
"""

# pyright: reportPrivateUsage=false
# These helpers are part of WebSocketManager's logic, split out only for
# file size — they intentionally call protected methods on the manager.

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from ...datamodel import RunStatus
from ....types import LIVE_BROWSER_POOL_FULL_PROMPT

if TYPE_CHECKING:
    from .connection import WebSocketManager


# Marker stored in message metadata so the frontend (or future tooling)
# can identify these prompts.
POOL_FULL_PROMPT_MARKER = "live_browser_pool_full"


async def handle_pool_full(
    ws_manager: "WebSocketManager", run_id: int, detail: str
) -> None:
    """Surface a pool-full failure as an InputRequest."""
    # Close the partial TM so _execute_stream's finally doesn't double-close.
    tm = ws_manager._team_managers.pop(run_id, None)
    if tm is not None:
        try:
            await tm.close()
        except Exception:
            logger.exception(
                f"Error closing partial team manager after pool full for run {run_id}"
            )

    prompt = LIVE_BROWSER_POOL_FULL_PROMPT

    # System status carries no content — SystemStatusMessage on the
    # frontend renders nothing for empty content, leaving only the
    # input_request card visible.
    await ws_manager._update_run_status(run_id, RunStatus.AWAITING_INPUT)

    await ws_manager._save_message(
        run_id,
        {
            "source": "system",
            "content": "",
            "metadata": {
                "source": "system",
                "type": "system",
                "status": "awaiting_input",
                "subtype": POOL_FULL_PROMPT_MARKER,
                "detail": detail,
            },
        },
    )

    await ws_manager._send_message(
        run_id,
        {
            "type": "input_request",
            "input_type": "text_input",
            "content": prompt,
        },
    )
    await ws_manager._save_message(
        run_id,
        {
            "source": "system",
            "content": [{"type": "text", "text": prompt}],
            "metadata": {
                "source": "system",
                "type": "input_request",
                "input_type": "text_input",
                "subtype": POOL_FULL_PROMPT_MARKER,
            },
        },
    )


async def maybe_retry_after_pool_full(
    ws_manager: "WebSocketManager", run_id: int, response: str
) -> bool:
    """Retry a pool-full run on user reply. Returns True if handled.

    ``"continue"`` (case-insensitive, optional trailing punctuation)
    replays the original task; any other reply is treated as a new task
    for the same run.
    """
    run = await ws_manager._get_run(run_id)
    if run is None or run.status != RunStatus.AWAITING_INPUT:
        return False

    original_task = ""
    if isinstance(run.task, dict):
        original_task = str(run.task.get("content") or "")
    else:
        original_task = str(getattr(run.task, "content", ""))

    normalized = response.strip().lower().rstrip(".!,")
    retry_original = normalized in ("continue", "")
    new_task = original_task if retry_original else response
    if not new_task:
        logger.warning(
            f"Pool-full retry for run {run_id}: no original task and empty reply"
        )
        return False

    # Echo the user's reply so it shows in the conversation. When the user
    # sent a continue-marker (or empty/whitespace), normalize the displayed
    # text to "continue" so the chat doesn't show an empty bubble.
    echoed = "continue" if retry_original else response
    await ws_manager._send_message(
        run_id,
        {
            "type": "message",
            "data": {"source": "user", "content": echoed},
        },
    )
    await ws_manager._save_message(
        run_id,
        {"source": "user", "content": echoed, "type": "user_message"},
    )

    branch = "original task" if retry_original else "new task from reply"
    logger.info(f"Retrying run {run_id} after pool-full ({branch})")
    await ws_manager.start_stream(run_id, new_task, echo_user_message=False)
    return True
