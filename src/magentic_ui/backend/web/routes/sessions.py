# api/routes/sessions.py
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import func
from sqlmodel import Session as DBSession, select

from ...datamodel import Message, Run, Session, RunStatus
from ..deps import get_db, get_websocket_manager

router = APIRouter()


def _to_iso_utc(dt: Optional[datetime]) -> Optional[str]:
    """Serialize a datetime as an ISO-8601 UTC string.

    SQLite drops tzinfo on `DateTime(timezone=True)` columns, so values written
    via `func.now()` (which is UTC) come back as naive. All write paths in this
    codebase produce UTC datetimes (either via `func.now()` or `_utc_now()`),
    so naive values are safely treated as UTC here. Without this stamping,
    browsers interpret naive ISO strings as local time, producing nonsensical
    relative labels.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


@router.get("/")
async def list_sessions(user_id: str, db=Depends(get_db)) -> Dict:
    """List all sessions with latest run status for a user (single query)"""
    with DBSession(db.engine) as session:
        # Subquery: get max run.id per session (latest run)
        latest_run_subq = (
            select(Run.session_id, func.max(Run.id).label("max_run_id"))
            .group_by(Run.session_id)
            .subquery()
        )

        # Main query: Session -> latest run subquery -> Run
        # Order by latest activity (run.updated_at) so sessions with recent
        # status changes float to the top. Falls back to session creation time
        # for sessions that have no run yet.
        statement = (
            select(Session, Run)
            .outerjoin(latest_run_subq, Session.id == latest_run_subq.c.session_id)
            .outerjoin(Run, Run.id == latest_run_subq.c.max_run_id)
            .where(Session.user_id == user_id)
            .order_by(func.coalesce(Run.updated_at, Session.created_at).desc())
        )

        results = session.exec(statement).all()

        data = []
        for sess, run in results:
            item = {
                "session_id": sess.id,
                "name": sess.name,
                "created_at": _to_iso_utc(sess.created_at),
            }
            item["latest_run"] = (
                {
                    "run_id": run.id,
                    "status": run.status.value if run.status else None,
                    "updated_at": _to_iso_utc(run.updated_at),
                }
                if run
                else None
            )
            data.append(item)

        return {"status": True, "data": data}


@router.get("/{session_id}")
async def get_session(session_id: int, user_id: str, db=Depends(get_db)) -> Dict:
    """Get a specific session"""
    response = db.get(Session, filters={"id": session_id, "user_id": user_id})
    if not response.status or not response.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": True, "data": response.data[0]}


@router.post("/")
async def create_session(session: Session, db=Depends(get_db)) -> Dict:
    """Create a new session with an associated run"""
    # Create session
    session_response = db.upsert(session)
    if not session_response.status:
        raise HTTPException(status_code=400, detail=session_response.message)

    # Create associated run
    try:
        run = db.upsert(
            Run(
                session_id=session.id,
                status=RunStatus.CREATED,
                user_id=session.user_id,
                task=None,
                team_result=None,
            ),
            return_json=False,
        )
        if not run.status:
            # Clean up session if run creation failed
            raise HTTPException(status_code=400, detail=run.message)
        return {"status": True, "data": session_response.data}
    except Exception as e:
        # Clean up session if run creation failed
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{session_id}")
async def update_session(
    session_id: int, user_id: str, session: Session, db=Depends(get_db)
) -> Dict:
    """Update an existing session"""
    # First verify the session belongs to user
    existing = db.get(Session, filters={"id": session_id, "user_id": user_id})
    if not existing.status or not existing.data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update the session
    response = db.upsert(session)
    if not response.status:
        raise HTTPException(status_code=400, detail=response.message)

    return {
        "status": True,
        "data": response.data,
        "message": "Session updated successfully",
    }


@router.delete("/{session_id}")
async def delete_session(
    session_id: int,
    user_id: str,
    db=Depends(get_db),
    ws_manager=Depends(get_websocket_manager),
) -> Dict:
    """Delete a session and all its associated runs and messages"""
    # Verify the session belongs to the user before performing any actions.
    session_response = db.get(
        Session, filters={"id": session_id, "user_id": user_id}, return_json=False
    )
    if not session_response.status:
        raise HTTPException(
            status_code=500, detail="Database error while fetching session"
        )
    if not session_response.data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Stop any active runs before deleting DB records, otherwise the agent
    # keeps running indefinitely with no way to cancel it.
    runs_response = db.get(
        Run,
        filters={"session_id": session_id, "user_id": user_id},
        return_json=False,
    )
    if not runs_response.status:
        logger.warning(
            f"Failed to fetch runs for session {session_id}, "
            "active agents may not be stopped"
        )
    if runs_response.status and runs_response.data:
        for run in runs_response.data:
            if run.status in (
                RunStatus.ACTIVE,
                RunStatus.CREATED,
                RunStatus.PAUSED,
                RunStatus.AWAITING_INPUT,
            ):
                try:
                    await asyncio.wait_for(
                        ws_manager.stop_run(run.id, reason="Session deleted"),
                        timeout=10,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timed out stopping run {run.id}, proceeding with delete"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to stop run {run.id} during session delete: {e}"
                    )

    # Delete the session
    db.delete(filters={"id": session_id, "user_id": user_id}, model_class=Session)

    return {"status": True, "message": "Session deleted successfully"}


@router.get("/{session_id}/runs")
async def list_session_runs(session_id: int, user_id: str, db=Depends(get_db)) -> Dict:
    """Get complete session history organized by runs"""

    try:
        # 1. Verify session exists and belongs to user
        session = db.get(
            Session, filters={"id": session_id, "user_id": user_id}, return_json=False
        )
        if not session.status:
            raise HTTPException(
                status_code=500, detail="Database error while fetching session"
            )
        if not session.data:
            raise HTTPException(
                status_code=404, detail="Session not found or access denied"
            )

        # 2. Get ordered runs for session
        runs = db.get(
            Run, filters={"session_id": session_id}, order="asc", return_json=False
        )
        if not runs.status:
            raise HTTPException(
                status_code=500, detail="Database error while fetching runs"
            )

        # 3. Build response with messages per run
        run_data = []
        if runs.data:  # It's ok to have no runs
            for run in runs.data:
                try:
                    # Get messages for this specific run
                    messages = db.get(
                        Message,
                        filters={"run_id": run.id},
                        order="asc",
                        return_json=False,
                    )
                    if not messages.status:
                        logger.error(f"Failed to fetch messages for run {run.id}")
                        # Continue processing other runs even if one fails
                        messages.data = []

                    run_data.append(
                        {
                            "id": str(run.id),
                            "created_at": run.created_at,
                            "status": run.status,
                            "task": run.task,
                            "team_result": run.team_result,
                            "messages": messages.data or [],
                            "input_request": getattr(run, "input_request", None),
                            "agent_mode": getattr(run, "agent_mode", None),
                        }
                    )
                except Exception as e:
                    logger.error(f"Error processing run {run.id}: {str(e)}")
                    # Include run with error state instead of failing entirely
                    run_data.append(
                        {
                            "id": str(run.id),
                            "created_at": run.created_at,
                            "status": "ERROR",
                            "task": run.task,
                            "team_result": None,
                            "messages": [],
                            "error": f"Failed to process run: {str(e)}",
                            "input_request": getattr(run, "input_request", None),
                            "agent_mode": getattr(run, "agent_mode", None),
                        }
                    )

        return {"status": True, "data": {"runs": run_data}}

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in list_messages: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error while fetching session data"
        ) from e
