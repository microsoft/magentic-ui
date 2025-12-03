# api/ws.py
import json
from datetime import datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from loguru import logger

from ...datamodel import Run
from ..auth import DEV_ORIGINS, WS_PROTOCOL_TAG, is_allowed_host, is_valid_token
from ..deps import get_db, get_websocket_manager
from ..managers import WebSocketManager

router = APIRouter()


def authenticate_websocket(websocket: WebSocket) -> tuple[bool, str | None]:
    """Validate WS auth + Host header. Returns (allowed, subprotocol_to_echo).

    HTTP middleware does not run for WebSocket handshakes, so the Host
    allowlist (DNS-rebinding defense) is enforced here alongside the
    auth check.

    Two accepted auth paths:
    - Subprotocol: client offers ``[WS_PROTOCOL_TAG, <token>]``; we verify
      the token and echo ``WS_PROTOCOL_TAG`` back on accept.
    - Dev-origin bypass: requests from the Vite dev server skip the token
      check (same rule as HTTP API requests).
    """
    if not is_allowed_host(websocket.headers.get("host", "")):
        return False, None

    origin = websocket.headers.get("origin", "")
    if origin in DEV_ORIGINS:
        return True, None

    protocols = websocket.scope.get("subprotocols") or []
    if (
        len(protocols) == 2
        and protocols[0] == WS_PROTOCOL_TAG
        and is_valid_token(protocols[1])
    ):
        return True, WS_PROTOCOL_TAG
    return False, None


@router.websocket("/runs/{run_id}")
async def run_websocket(
    websocket: WebSocket,
    run_id: int,
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
    db=Depends(get_db),
):
    """WebSocket endpoint for run communication"""
    allowed, auth_subprotocol = authenticate_websocket(websocket)
    if not allowed:
        logger.warning(f"WebSocket auth failed for run {run_id}")
        await websocket.close(code=4401, reason="Unauthorized")
        return

    # Verify run exists and is in valid state
    run_response = db.get(Run, filters={"id": run_id}, return_json=False)
    if not run_response.status or not run_response.data:
        logger.warning(f"Run not found: {run_id}")
        await websocket.close(code=4004, reason="Run not found")
        return

    # run = run_response.data[0]
    # if run.status not in [RunStatus.CREATED, RunStatus.ACTIVE]:
    #     await websocket.close(code=4003, reason="Run not in valid state")
    #     return

    # Connect websocket
    connected = await ws_manager.connect(
        websocket, run_id, subprotocol=auth_subprotocol
    )
    if not connected:
        await websocket.close(code=4002, reason="Failed to establish connection")
        return

    try:
        logger.info(f"WebSocket connection established for run {run_id}")

        while True:
            try:
                raw_message = await websocket.receive_text()
                message = json.loads(raw_message)

                if message.get("type") == "start":
                    # Handle start message
                    logger.info(f"Received start request for run {run_id}")
                    task_raw = message.get("task")
                    raw_files = message.get("files")
                    files = raw_files if isinstance(raw_files, list) else None
                    # Frontend sends task as JSON: {"content": "actual message"}
                    # Unwrap to get the actual content
                    if isinstance(task_raw, str):
                        try:
                            parsed = json.loads(task_raw)
                            task = (
                                parsed.get("content", task_raw)
                                if isinstance(parsed, dict)
                                else task_raw
                            )
                        except json.JSONDecodeError:
                            task = task_raw
                    else:
                        task = task_raw
                    # Note: settings_config from the frontend is forwarded
                    # to the manager. If empty ({}), the manager uses its
                    # CLI --config file as-is.
                    raw_settings = message.get("settings_config")
                    settings_config = (
                        raw_settings if isinstance(raw_settings, dict) else {}
                    )
                    if task:
                        # start_stream owns lifecycle: waits for any previous
                        # stream to finish, then launches a new background task.
                        await ws_manager.start_stream(
                            run_id,
                            task,
                            files=files,
                            settings_config=settings_config,
                        )
                    else:
                        logger.warning(f"Invalid start message format for run {run_id}")
                        await websocket.send_json(
                            {
                                "type": "error",
                                "error": "Invalid start message format",
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )

                elif message.get("type") == "stop":
                    logger.info(f"Received stop request for run {run_id}")
                    reason = message.get("reason") or "User requested stop/cancellation"
                    # stop_run cancels the stream task, waits for cleanup,
                    # then sends "stopped" status — fully done when it returns.
                    await ws_manager.stop_run(run_id, reason=reason)
                    break

                elif message.get("type") == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )

                elif message.get("type") == "input_response":
                    # Handle input response from client
                    response = message.get("response")
                    raw_files = message.get("files")
                    files = raw_files if isinstance(raw_files, list) else None
                    if isinstance(response, str):
                        await ws_manager.handle_input_response(
                            run_id, response, files=files
                        )
                    else:
                        logger.warning(
                            f"Invalid input response format for run {run_id}: "
                            f"'response' must be a string, got {type(response).__name__}"
                        )

                elif message.get("type") == "approval_response":
                    # Handle structured approval response (Approve/Deny buttons)
                    decision = message.get("decision")
                    source = message.get("source", "user")
                    if decision in ("approve", "deny") and source in (
                        "user",
                        "auto_session",
                    ):
                        await ws_manager.handle_approval_response(
                            run_id, decision, source
                        )
                    else:
                        logger.warning(
                            f"Invalid approval_response for run {run_id}: "
                            f"decision={decision}, source={source}"
                        )

                elif message.get("type") == "continuation_response":
                    # Handle structured continuation response from the
                    # max-rounds card (Continue / Stop buttons).
                    decision = message.get("decision")
                    if decision in ("continue", "stop"):
                        await ws_manager.handle_continuation_response(run_id, decision)
                    else:
                        logger.warning(
                            f"Invalid continuation_response for run {run_id}: "
                            f"decision={decision}"
                        )

                elif message.get("type") == "pause":
                    logger.info(f"Received pause request for run {run_id}")
                    await ws_manager.pause_run(run_id)

                elif message.get("type") == "resume":
                    logger.info(f"Received resume request for run {run_id}")
                    await ws_manager.resume_run(run_id)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {raw_message}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": "Invalid message format",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        await ws_manager.disconnect(run_id, ws=websocket)
