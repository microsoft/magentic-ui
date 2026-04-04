# api/routes/teams.py
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from ...datamodel import Team
from ..deps import get_db

router = APIRouter()


def _get_authenticated_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


@router.get("/")
async def list_teams(request: Request, db=Depends(get_db)) -> Dict:
    """List all teams for a user"""
    user_id = _get_authenticated_user_id(request)
    response = db.get(Team, filters={"user_id": user_id})
    return {"status": True, "data": response.data}


@router.get("/{team_id}")
async def get_team(team_id: int, request: Request, db=Depends(get_db)) -> Dict:
    """Get a specific team"""
    user_id = _get_authenticated_user_id(request)
    response = db.get(Team, filters={"id": team_id, "user_id": user_id})
    if not response.status or not response.data:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"status": True, "data": response.data[0]}


@router.post("/")
async def create_team(team: Team, request: Request, db=Depends(get_db)) -> Dict:
    """Create a new team"""
    team.user_id = _get_authenticated_user_id(request)
    response = db.upsert(team)
    if not response.status:
        raise HTTPException(status_code=400, detail=response.message)
    return {"status": True, "data": response.data}


@router.delete("/{team_id}")
async def delete_team(team_id: int, request: Request, db=Depends(get_db)) -> Dict:
    """Delete a team"""
    user_id = _get_authenticated_user_id(request)
    db.delete(filters={"id": team_id, "user_id": user_id}, model_class=Team)
    return {"status": True, "message": "Team deleted successfully"}
