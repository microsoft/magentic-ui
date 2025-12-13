# /api/scripts routes
import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from ...datamodel import Script
from ..deps import get_db, get_workspace_config
from ..managers.script_executor import ScriptExecutor

router = APIRouter()


class CreateScriptRequest(BaseModel):
    user_id: str
    task: str
    start_url: str
    actions: List[Dict[str, Any]]
    viewport_width: int = 1280
    viewport_height: int = 720
    session_id: Optional[int] = None


class RunScriptRequest(BaseModel):
    user_id: str


@router.get("/")
async def list_scripts(user_id: str, db=Depends(get_db)) -> Dict:
    """Get all scripts for a user"""
    response = db.get(Script, filters={"user_id": user_id})
    return {"status": True, "data": response.data}


@router.get("/{script_id}")
async def get_script(script_id: int, user_id: str, db=Depends(get_db)) -> Dict:
    """Get a specific script"""
    response = db.get(Script, filters={"id": script_id, "user_id": user_id})
    if not response.status or not response.data:
        raise HTTPException(status_code=404, detail="Script not found")
    return {"status": True, "data": response.data[0]}


@router.post("/")
async def create_script(request: CreateScriptRequest, db=Depends(get_db)) -> Dict:
    """Create a new script"""
    if not request.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    script = Script(
        user_id=request.user_id,
        task=request.task,
        start_url=request.start_url,
        actions=request.actions,
        viewport_width=request.viewport_width,
        viewport_height=request.viewport_height,
        session_id=request.session_id,
    )

    response = db.upsert(script)
    if not response.status:
        raise HTTPException(status_code=400, detail=response.message)

    return {"status": True, "data": response.data}


@router.put("/{script_id}")
async def update_script(
    script_id: int, user_id: str, request: CreateScriptRequest, db=Depends(get_db)
) -> Dict:
    """Update an existing script"""
    existing = db.get(Script, filters={"id": script_id, "user_id": user_id})
    if not existing.status or not existing.data:
        raise HTTPException(status_code=404, detail="Script not found")

    existing_data = existing.data[0]
    # Preserve created_at from existing record
    created_at = existing_data.get("created_at") if isinstance(existing_data, dict) else getattr(existing_data, "created_at", None)

    script = Script(
        id=script_id,
        user_id=request.user_id,
        task=request.task,
        start_url=request.start_url,
        actions=request.actions,
        viewport_width=request.viewport_width,
        viewport_height=request.viewport_height,
        session_id=request.session_id,
        created_at=created_at,
    )

    response = db.upsert(script)
    if not response.status:
        raise HTTPException(status_code=400, detail=response.message)

    return {"status": True, "data": response.data, "message": "Script updated successfully"}


@router.delete("/{script_id}")
async def delete_script(script_id: int, user_id: str, db=Depends(get_db)) -> Dict:
    """Delete a specific script"""
    response = db.delete(Script, filters={"id": script_id, "user_id": user_id})
    if not response.status:
        raise HTTPException(status_code=400, detail=response.message)
    return {"status": True, "data": response.data}


@router.post("/{script_id}/run")
async def run_script(
    script_id: int,
    request: RunScriptRequest,
    db=Depends(get_db),
) -> Dict:
    """
    Run a script. This endpoint returns immediately and the script
    execution will be handled by the WebSocket connection.

    The actual execution happens in the frontend by:
    1. Getting the script data
    2. Creating a new session
    3. Sending the script to the orchestrator via WebSocket
    """
    user_id = request.user_id

    # Get the script
    response = db.get(Script, filters={"id": script_id, "user_id": user_id})
    if not response.status or not response.data:
        raise HTTPException(status_code=404, detail="Script not found")

    script_data = response.data[0]

    # Increment run count
    try:
        current_run_count = script_data.get("run_count", 0) if isinstance(script_data, dict) else getattr(script_data, "run_count", 0)
        # Preserve created_at from existing record
        created_at = script_data.get("created_at") if isinstance(script_data, dict) else getattr(script_data, "created_at", None)

        # Update run count in database
        update_script = Script(
            id=script_id,
            user_id=user_id,
            task=script_data.get("task") if isinstance(script_data, dict) else script_data.task,
            start_url=script_data.get("start_url") if isinstance(script_data, dict) else script_data.start_url,
            actions=script_data.get("actions") if isinstance(script_data, dict) else script_data.actions,
            viewport_width=script_data.get("viewport_width", 1280) if isinstance(script_data, dict) else script_data.viewport_width,
            viewport_height=script_data.get("viewport_height", 720) if isinstance(script_data, dict) else script_data.viewport_height,
            session_id=script_data.get("session_id") if isinstance(script_data, dict) else script_data.session_id,
            run_count=current_run_count + 1,
            created_at=created_at,
        )
        db.upsert(update_script)
    except Exception as e:
        logger.warning(f"Failed to update run count: {e}")

    return {
        "status": True,
        "data": {
            "script": script_data,
            "message": "Script ready to run. Use WebSocket to execute.",
        },
    }


@router.get("/{script_id}/python")
async def get_script_as_python(script_id: int, user_id: str, db=Depends(get_db)) -> Dict:
    """Get script as Python code for download"""
    from ....types import PlaywrightScript as PlaywrightScriptType, PlaywrightAction

    response = db.get(Script, filters={"id": script_id, "user_id": user_id})
    if not response.status or not response.data:
        raise HTTPException(status_code=404, detail="Script not found")

    script_data = response.data[0]

    # Convert to PlaywrightScript type for rendering
    actions = []
    raw_actions = script_data.get("actions", []) if isinstance(script_data, dict) else script_data.actions
    for action in raw_actions:
        actions.append(PlaywrightAction(
            action_type=action.get("action_type", ""),
            selector=action.get("selector"),
            value=action.get("value"),
            description=action.get("description", ""),
            wait_after=action.get("wait_after", 0),
        ))

    task = script_data.get("task", "") if isinstance(script_data, dict) else script_data.task
    start_url = script_data.get("start_url", "") if isinstance(script_data, dict) else script_data.start_url
    viewport_width = script_data.get("viewport_width", 1280) if isinstance(script_data, dict) else script_data.viewport_width
    viewport_height = script_data.get("viewport_height", 720) if isinstance(script_data, dict) else script_data.viewport_height

    pw_script = PlaywrightScriptType(
        task=task or "",
        start_url=start_url or "",
        actions=actions,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )

    python_code = pw_script.to_python_script()

    return {
        "status": True,
        "data": {
            "python_code": python_code,
            "filename": f"script_{script_id}.py",
        },
    }


@router.websocket("/{script_id}/execute")
async def execute_script_websocket(
    websocket: WebSocket,
    script_id: int,
    user_id: str,
    session_id: Optional[int] = None,
    db=Depends(get_db),
):
    """
    WebSocket endpoint for direct script execution without LLM.

    This provides fast script replay by directly executing saved Playwright actions.
    Progress is streamed via WebSocket messages.

    Message types sent:
    - script_execution_start: Script execution started
    - script_status: Status updates (starting_browser, browser_ready)
    - vnc_info: VNC connection info if available
    - action_start: Individual action started
    - action_complete: Individual action completed with screenshot
    - script_execution_complete: Script execution finished
    - script_execution_error: Error occurred
    """
    await websocket.accept()

    # Get the script
    response = db.get(Script, filters={"id": script_id, "user_id": user_id})
    if not response.status or not response.data:
        await websocket.send_json({
            "type": "error",
            "error": "Script not found",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await websocket.close(code=4004, reason="Script not found")
        return

    script_data = response.data[0]

    # Get workspace config
    workspace_config = get_workspace_config()
    workspace_root = workspace_config.get(
        "external_workspace_root",
        workspace_config.get("internal_workspace_root")
    )

    # Validate workspace_root
    if workspace_root is None:
        await websocket.send_json({
            "type": "error",
            "error": "Server configuration error: workspace_root not configured",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await websocket.close(code=4500, reason="Server configuration error")
        return

    # Create executor
    executor = ScriptExecutor(
        workspace_root=workspace_root,
        inside_docker=workspace_config.get("inside_docker", False),
        run_without_docker=workspace_config.get("run_without_docker", False),
    )

    # Helper to listen for stop messages from client
    async def listen_for_stop():
        """Listen for stop messages from the client."""
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "stop":
                    logger.info(f"Stop signal received for script {script_id}")
                    await executor.stop()
                    break
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected while listening for stop")
            await executor.stop()
        except Exception as e:
            logger.debug(f"Stop listener ended: {e}")

    try:
        # Update run count
        try:
            current_run_count = script_data.get("run_count", 0) if isinstance(script_data, dict) else getattr(script_data, "run_count", 0)
            created_at = script_data.get("created_at") if isinstance(script_data, dict) else getattr(script_data, "created_at", None)

            update_script = Script(
                id=script_id,
                user_id=user_id,
                task=script_data.get("task") if isinstance(script_data, dict) else script_data.task,
                start_url=script_data.get("start_url") if isinstance(script_data, dict) else script_data.start_url,
                actions=script_data.get("actions") if isinstance(script_data, dict) else script_data.actions,
                viewport_width=script_data.get("viewport_width", 1280) if isinstance(script_data, dict) else script_data.viewport_width,
                viewport_height=script_data.get("viewport_height", 720) if isinstance(script_data, dict) else script_data.viewport_height,
                session_id=script_data.get("session_id") if isinstance(script_data, dict) else script_data.session_id,
                run_count=current_run_count + 1,
                created_at=created_at,
            )
            db.upsert(update_script)
        except Exception as e:
            logger.warning(f"Failed to update run count: {e}")

        # Start stop listener in background
        stop_listener_task = asyncio.create_task(listen_for_stop())

        # Execute the script
        try:
            result = await executor.execute_script(
                websocket=websocket,
                script_data=script_data if isinstance(script_data, dict) else script_data.__dict__,
                session_id=session_id,
                db=db,
                user_id=user_id,
            )
            logger.info(f"Script {script_id} execution completed: success={result.success}")
        finally:
            # Cancel stop listener when execution completes
            stop_listener_task.cancel()
            try:
                await stop_listener_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected during script {script_id} execution")
        await executor.stop()
    except Exception as e:
        logger.error(f"Error executing script {script_id}: {e}")
        try:
            await websocket.send_json({
                "type": "script_execution_error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        await executor.stop()
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
