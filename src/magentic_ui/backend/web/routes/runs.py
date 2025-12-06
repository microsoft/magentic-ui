# /api/runs routes
from typing import Dict, List
from datetime import datetime
import os
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from loguru import logger

from ...datamodel import Message, Run, RunStatus, Session
from ..deps import get_db, get_websocket_manager
from ...teammanager import TeamManager

# Security configuration for file uploads
# Allowed extensions for general document/media purposes
ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.md', '.csv', '.xlsx', '.xls',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg', '.webp',
    '.mp4', '.webm', '.ogg', '.mov', '.avi', '.wmv',
    '.json', '.xml', '.yaml', '.yml', '.html', '.css',
    '.java', '.cpp', '.c', '.sql'
}

# Explicitly forbidden extensions - prevents execution of scripts and binaries
FORBIDDEN_EXTENSIONS = {
    '.exe', '.dll', '.so', '.dylib', '.app', '.msi',
    '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.js', '.jar',
    '.py', '.sh', '.bash', '.zsh', '.ksh', '.csh', '.ps1', '.rb', '.pl'
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks.
    
    Args:
        filename: The original filename
        
    Returns:
        A sanitized filename
        
    Raises:
        ValueError: If the filename is invalid or contains suspicious patterns
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Remove any path separators to prevent directory traversal
    filename = os.path.basename(filename)
    
    # Check for null bytes
    if '\x00' in filename:
        raise ValueError("Filename contains null bytes")
    
    # Reject filenames that try to escape directories
    if '..' in filename or filename.startswith('.'):
        raise ValueError("Invalid filename: potential directory traversal attack")
    
    return filename

def validate_file_upload(file: UploadFile) -> None:
    """
    Validate file upload for security issues.
    
    Args:
        file: The uploaded file to validate
        
    Raises:
        ValueError: If the file fails validation
    """
    if not file.filename:
        raise ValueError("Filename is required")
    
    # Sanitize filename
    try:
        sanitized_name = sanitize_filename(file.filename)
    except ValueError as e:
        raise ValueError(f"Invalid filename: {str(e)}")
    
    # Get file extension
    _, ext = os.path.splitext(sanitized_name.lower())
    
    # Check for forbidden extensions
    if ext in FORBIDDEN_EXTENSIONS:
        raise ValueError(f"File type '{ext}' is not allowed for security reasons")
    
    # Warn if extension is not in allowed list (but still allow if not forbidden)
    if ext and ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Uploading file with uncommon extension: {ext}")
    
    # Check MIME type if available
    if file.content_type:
        mime_type = file.content_type.lower()
        # Reject executable MIME types
        dangerous_mimes = [
            'application/x-executable',
            'application/x-mach-binary',
            'application/x-elf',
            'application/x-object',
            'application/x-sharedlib',
            'application/x-shellscript',
            'application/x-msdos-program',
            'application/x-msdownload',
            'application/x-powershell',
        ]
        if mime_type in dangerous_mimes:
            raise ValueError(f"File MIME type '{mime_type}' is not allowed")

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
        # Validate file upload for security issues
        try:
            validate_file_upload(file)
        except ValueError as e:
            logger.error(f"File validation failed for {file.filename}: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        
        # Save file to run directory
        filename = file.filename
        try:
            assert filename is not None
        except Exception as e:
            logger.error(f"Error getting filename: {e}")
            continue

        # Sanitize the filename
        try:
            filename = sanitize_filename(filename)
        except ValueError as e:
            logger.error(f"Filename sanitization failed for {file.filename}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid filename: {str(e)}")

        file_path = paths.internal_run_dir / filename

        # Ensure the directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Read file content for size validation
        content = await file.read()
        
        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            logger.error(f"File size {len(content)} exceeds maximum allowed size {MAX_FILE_SIZE}")
            raise HTTPException(
                status_code=413, 
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f} MB"
            )
        
        # Write the file
        with open(file_path, "wb") as buffer:
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
