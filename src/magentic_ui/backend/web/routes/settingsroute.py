# api/routes/settings.py
import os
import yaml
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from ...datamodel import Settings
from ..deps import get_db

router = APIRouter()


def _get_or_create_settings(user_id: str, db) -> Settings:
    """Get existing settings or create default ones for user_id"""
    response = db.get(Settings, filters={"user_id": user_id})
    if response.status and response.data:
        return response.data[0]

    # Create default settings
    default_settings = Settings(user_id=user_id)
    upsert_response = db.upsert(default_settings)
    if not upsert_response.status:
        raise HTTPException(status_code=500, detail=upsert_response.message)

    return upsert_response.data


@router.get("/")
async def get_settings(user_id: str, db=Depends(get_db)) -> Dict:
    try:
        settings = _get_or_create_settings(user_id, db)
        return {"status": True, "data": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/")
async def update_settings(settings: Settings, db=Depends(get_db)) -> Dict:
    try:
        # Get existing settings to preserve the id
        existing = _get_or_create_settings(settings.user_id, db)
        settings.id = existing.id if hasattr(existing, "id") else existing["id"]

        response = db.upsert(settings)
        if not response.status:
            raise HTTPException(status_code=400, detail=response.message)
        return {"status": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/config-info")
async def get_config_info() -> Dict:
    """Get information about whether the app was started with a config file"""
    config_file = os.environ.get("_CONFIG")
    has_config_file = config_file is not None
    config_content = None

    if has_config_file and config_file:
        try:
            with open(config_file, "r") as f:
                config_content = yaml.safe_load(f)
        except Exception as e:
            # If we can't read the config file, just log the error but don't fail
            print(f"Warning: Could not read config file {config_file}: {e}")

    return {
        "status": True,
        "data": {
            "has_config_file": has_config_file,
            "config_file_path": config_file if has_config_file else None,
            "config_content": config_content,
        },
    }
