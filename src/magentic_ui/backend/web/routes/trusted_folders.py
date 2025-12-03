# api/routes/trusted_folders.py
"""
Trusted Folders API.

CRUD endpoints for managing the user's "Always Allow" folder list.
Each folder is stored as an independent database row, allowing
concurrent add/remove without read-modify-write conflicts.
"""

from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...datamodel import TrustedFolder
from ..deps import get_db

router = APIRouter()


class TrustedFolderCreate(BaseModel):
    """Request body for adding a trusted folder."""

    name: str
    path: str


@router.get("/")
async def list_trusted_folders(user_id: str, db=Depends(get_db)) -> Dict:
    """List all trusted folders for a user."""
    response = db.get(TrustedFolder, filters={"user_id": user_id})
    if not response.status:
        raise HTTPException(status_code=500, detail=response.message)
    folders: List[Dict] = []
    if response.data:
        folders = [{"id": f.id, "name": f.name, "path": f.path} for f in response.data]
    return {"status": True, "data": folders}


@router.post("/")
async def add_trusted_folder(
    user_id: str, body: TrustedFolderCreate, db=Depends(get_db)
) -> Dict:
    """Add a folder to the trusted list. Skips if path already exists."""
    # Check for duplicate
    existing = db.get(TrustedFolder, filters={"user_id": user_id, "path": body.path})
    if not existing.status:
        raise HTTPException(status_code=500, detail="Failed to check existing folders")
    if existing.data:
        f = existing.data[0]
        return {"status": True, "data": {"id": f.id, "name": f.name, "path": f.path}}

    folder = TrustedFolder(user_id=user_id, name=body.name, path=body.path)
    response = db.upsert(folder)
    if not response.status:
        # Handle concurrent insert: re-fetch existing row
        existing = db.get(
            TrustedFolder, filters={"user_id": user_id, "path": body.path}
        )
        if existing.status and existing.data:
            f = existing.data[0]
            return {
                "status": True,
                "data": {"id": f.id, "name": f.name, "path": f.path},
            }
        raise HTTPException(status_code=500, detail="Failed to add folder")

    # upsert returns a dict (return_json=True by default)
    data = response.data
    return {
        "status": True,
        "data": {"id": data["id"], "name": data["name"], "path": data["path"]},
    }


@router.delete("/{folder_id}")
async def remove_trusted_folder(
    user_id: str, folder_id: int, db=Depends(get_db)
) -> Dict:
    """Remove a folder from the trusted list by ID, scoped to user."""
    response = db.delete(TrustedFolder, filters={"id": folder_id, "user_id": user_id})
    message = getattr(response, "message", "") or ""
    if (not response.status) or "not found" in message.lower():
        raise HTTPException(status_code=404, detail="Folder not found")
    return {"status": True, "data": None}
