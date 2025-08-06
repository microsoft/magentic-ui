# api/ws.py
import asyncio
import json
import os
from datetime import datetime
import time

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from loguru import logger

from ...datamodel import Run
from ..deps import get_db, get_websocket_manager
from ..managers import WebSocketManager
from ...utils.utils import construct_task

router = APIRouter()


@router.websocket("/runs/{run_id}")
async def run_websocket(
    websocket: WebSocket,
    run_id: int,
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
    db=Depends(get_db),
):
    """WebSocket endpoint for run communication"""
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
    connected = await ws_manager.connect(websocket, run_id)
    if not connected:
        await websocket.close(code=4002, reason="Failed to establish connection")
        return
    # 用于监控操作记录，如果超过时间没有收到消息，则主动关闭链接
    last_action_time = time.time()
    max_idle_time = 7200
    stop_running = False
    try:
        logger.info(f"WebSocket connection established for run {run_id}")

        while True:
            try:
                raw_message = await websocket.receive_text()
                message = json.loads(raw_message)

                if message.get("type") == "start":
                    # Handle start message
                    logger.info(f"Received start request for run {run_id}")
                    
                    # Save uploaded files to run directory
                    files = message.get("files")
                    if files:
                        try:
                            # Get run info to build the path
                            run_response = db.get(
                                Run, filters={"id": run_id}, return_json=False
                            )
                            if run_response.status and run_response.data:
                                run_data = run_response.data[0] if isinstance(run_response.data, list) else run_response.data
                                run_suffix = os.path.join(
                                    "files",
                                    "user",
                                    str(run_data.user_id or "unknown_user"),
                                    str(run_data.session_id or "unknown_session"),
                                    str(run_data.id or "unknown_run"),
                                )
                                run_dir = str(ws_manager.internal_workspace_root / run_suffix)
                                
                                # Save files to disk
                                from ...utils.utils import save_uploaded_files
                                save_uploaded_files(files, run_dir)
                        except Exception as e:
                            logger.warning(f"Failed to save uploaded files: {e}")
                    
                    task = construct_task(
                        query=message.get("task"), 
                        files=files
                    )
                    team_config = message.get("team_config")
                    settings_config = message.get("settings_config")
                    if task and team_config:
                        # await ws_manager.start_stream(run_id, task, team_config)
                        asyncio.create_task(
                            ws_manager.start_stream(
                                run_id, task, team_config, settings_config
                            )
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
                    await ws_manager.stop_run(run_id, reason=reason)
                    break

                elif message.get("type") == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )

                elif message.get("type") == "input_response":
                    # Handle input response from client
                    response = message.get("response")
                    if response is not None:
                        await ws_manager.handle_input_response(run_id, response)
                    else:
                        logger.warning(
                            f"Invalid input response format for run {run_id}"
                        )
                elif message.get("type") == "pause":
                    logger.info(f"Received pause request for run {run_id}")
                    await ws_manager.pause_run(run_id)

                elif message.get("type") == "resume":
                    logger.info(f"Received resume request for run {run_id}")
                    await ws_manager.resume_run(run_id)
                elif message.get("type") == "terminal_input":
                    logger.info(f"Received terminal input request for run {run_id}")
                    terminal_reason = message.get("terminal_reason") or "User request cancellation"
                    await ws_manager.stop_run(run_id, reason=terminal_reason)
                    stop_running = True
                    break
                elif time.time() - last_action_time > max_idle_time:
                    logger.warning(f"No action received for run {run_id} in {max_idle_time} seconds, closing connection")
                    stop_running = True
                    break
                else:
                    last_action_time = time.time()
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
        stop_running = True
    finally:
        await ws_manager.disconnect(run_id, stop_running=stop_running)
