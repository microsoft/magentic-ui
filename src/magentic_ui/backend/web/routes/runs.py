# /api/runs routes
import os
from typing import Dict, List
from datetime import datetime
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from loguru import logger

from ...datamodel import Message, Run, RunStatus, Session
from ..deps import get_db, get_websocket_manager
from ...teammanager import TeamManager

router = APIRouter()


class CreateRunRequest(BaseModel):
    session_id: int
    user_id: str


@router.post("/")
async def create_run(
    request: CreateRunRequest,
    db=Depends(get_db),
) -> Dict:
    """Return the existing run for a session or create a new one"""
    # First check if session exists and belongs to user
    session_response = db.get(
        Session,
        filters={"id": request.session_id, "user_id": request.user_id},
        return_json=False,
    )
    if not session_response.status or not session_response.data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get the latest run for this session
    run_response = db.get(
        Run,
        filters={"session_id": request.session_id},
        return_json=False,
    )

    if not run_response.status or not run_response.data:
        # Create a new run if one doesn't exist
        try:
            run_response = db.upsert(
                Run(
                    created_at=datetime.now(),
                    session_id=request.session_id,
                    status=RunStatus.CREATED,
                    user_id=request.user_id,
                ),
                return_json=False,
            )
            if not run_response.status:
                raise HTTPException(status_code=400, detail=run_response.message)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    # Return the run (either existing or newly created)
    run = None
    if isinstance(run_response.data, list):
        # get the run with the latest created_at
        run = max(run_response.data, key=lambda x: x.created_at)
    else:
        run = run_response.data
    return {"status": run_response.status, "data": {"run_id": str(run.id)}}


# We might want to add these endpoints:

@router.get("/download")
async def download_file(file_path: str):
    """
    下载文件接口
    
    Args:
        file_path: 文件路径，相对于 /app/workspace/ 目录
        
    Returns:
        FileResponse: 文件下载响应
    """
    try:
        # 解码URL编码的文件路径
        decoded_path = unquote(file_path)
        
        # 构建完整文件路径，确保在workspace目录下
        workspace_path = os.environ.get("INTERNAL_WORKSPACE_ROOT", "./workspace")
        full_file_path = os.path.join(workspace_path, decoded_path.lstrip("/"))
        
        # 检查文件是否存在
        if not os.path.exists(full_file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # 检查是否为文件（不是目录）
        if not os.path.isfile(full_file_path):
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # 获取文件名用于下载
        filename = os.path.basename(full_file_path)
        
        # 返回文件下载响应
        return FileResponse(
            path=str(full_file_path),
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{run_id}")
async def get_run(run_id: int, db=Depends(get_db)) -> Dict:
    """Get run details including task and result"""
    run = db.get(Run, filters={"id": run_id}, return_json=False)
    if not run.status or not run.data:
        raise HTTPException(status_code=404, detail="Run not found")

    return {"status": True, "data": run.data[0]}


@router.get("/{run_id}/messages")
async def get_run_messages(run_id: int, db=Depends(get_db)) -> Dict:
    """Get all messages for a run"""
    messages = db.get(
        Message, filters={"run_id": run_id}, order="created_at asc", return_json=False
    )

    return {"status": True, "data": messages.data}


@router.post("/{run_id}/upload")
async def upload_files(
    run_id: int,
    files: List[UploadFile] = File(...),
    db=Depends(get_db),
    ws_manager=Depends(get_websocket_manager),
) -> Dict:
    """Upload files for a specific run and save them to the run directory"""
    # Verify run exists
    run_response = db.get(Run, filters={"id": run_id}, return_json=False)
    if not run_response.status or not run_response.data:
        raise HTTPException(status_code=404, detail="Run not found")

    run = run_response.data[0]

    # Create a temporary team manager to get run paths, this does not create any ressources
    team_manager = TeamManager(
        internal_workspace_root=ws_manager.internal_workspace_root,
        external_workspace_root=ws_manager.external_workspace_root,
        inside_docker=ws_manager.inside_docker,
        config=ws_manager.config,
        run_without_docker=ws_manager.run_without_docker,
    )

    # Prepare run paths (this creates the directories)
    paths = team_manager.prepare_run_paths(run=run)

    uploaded_files = []

    for file in files:
        # Save file to run directory
        filename = file.filename
        try:
            assert filename is not None
        except Exception as e:
            logger.error(f"Error getting filename: {e}")
            continue

        file_path = paths.internal_run_dir / filename

        # Ensure the directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        uploaded_files.append(
            {
                "name": filename,
                "size": len(content),
                "path": str(file_path),
                "relative_path": f"files/user/{run.user_id}/{run.session_id}/{run.id}/{filename}",
            }
        )

    # Notify the team manager about the uploaded files so they don't get marked as generated
    if hasattr(ws_manager, "_team_managers") and run_id in ws_manager._team_managers:
        team_manager = ws_manager._team_managers[run_id]
        uploaded_file_names = {file["name"] for file in uploaded_files}
        team_manager.add_uploaded_files(uploaded_file_names)
    else:
        logger.warning(
            f"Team manager not found for run {run_id}, files uploaded but not tracked"
        )

    return {
        "status": True,
        "message": f"Successfully uploaded {len(uploaded_files)} files",
        "files": uploaded_files,
    }
