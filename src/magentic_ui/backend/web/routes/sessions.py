# api/routes/sessions.py
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from ...datamodel import Message, Run, Session, RunStatus, User
from ..deps import get_db
from ..auth_deps import get_current_user

router = APIRouter()


@router.get("/")
async def list_sessions(
    db=Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict:
    """List all sessions for the current authenticated user"""
    # Assuming Session.user_id should store the integer User.id
    # If Session.user_id stores email, use current_user.email
    logger.info(f"User {current_user.email} (ID: {current_user.id}) listing their sessions.")
    response = db.get(Session, filters={"user_id": current_user.id})
    return {"status": True, "data": response.data}


@router.get("/{session_id}")
async def get_session(
    session_id: int, 
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Get a specific session for the current authenticated user"""
    # Assuming Session.user_id should store the integer User.id
    logger.info(f"User {current_user.email} (ID: {current_user.id}) requesting session ID: {session_id}.")
    response = db.get(Session, filters={"id": session_id, "user_id": current_user.id})
    if not response.status or not response.data:
        raise HTTPException(status_code=404, detail="Session not found or access denied")
    return {"status": True, "data": response.data[0]}


@router.post("/")
async def create_session(
    session_data: Session, # Renamed to avoid conflict with Session type from sqlmodel
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Create a new session for the current authenticated user"""
    # Ensure the session is associated with the current user
    session_data.user_id = current_user.id # Assuming Session.user_id should be int
    logger.info(f"User {current_user.email} (ID: {current_user.id}) creating a new session.")
    
    # Create session
    session_response = db.upsert(session_data)
    if not session_response.status:
        raise HTTPException(status_code=400, detail=session_response.message)

    # Create associated run
    try:
        run_obj = Run( # Renamed variable to avoid conflict
            session_id=session_data.id, # Use id from the created session_data
            status=RunStatus.CREATED,
            user_id=current_user.id, # Associate run with current user
            task=None, # Or session_data.task if it exists and is relevant
            team_result=None,
        )
        run_response = db.upsert(run_obj, return_json=False) # Corrected variable name
        
        if not run_response.status:
            # Clean up session if run creation failed (consider this logic carefully)
            logger.error(f"Failed to create run for session {session_data.id}, run creation message: {run_response.message}")
            # db.delete(Session, filters={"id": session_data.id}) # Example cleanup
            raise HTTPException(status_code=400, detail=f"Failed to create associated run: {run_response.message}")
        return {"status": True, "data": session_response.data}
    except Exception as e:
        # Clean up session if run creation failed (consider this logic carefully)
        logger.error(f"Exception during run creation for session {session_data.id}: {e}")
        # db.delete(Session, filters={"id": session_data.id}) # Example cleanup
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{session_id}")
async def update_session(
    session_id: int, 
    session_update_data: Session, # Renamed to avoid conflict
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Update an existing session for the current authenticated user"""
    # First verify the session belongs to user
    logger.info(f"User {current_user.email} (ID: {current_user.id}) attempting to update session ID: {session_id}.")
    existing = db.get(Session, filters={"id": session_id, "user_id": current_user.id})
    if not existing.status or not existing.data:
        raise HTTPException(status_code=404, detail="Session not found or access denied")

    # Ensure user_id is not changed or is set to current user's ID
    session_update_data.user_id = current_user.id
    session_update_data.id = session_id # Ensure ID is maintained for upsert

    # Update the session
    response = db.upsert(session_update_data)
    if not response.status:
        raise HTTPException(status_code=400, detail=response.message)

    logger.info(f"Session ID {session_id} updated successfully by user {current_user.email}.")
    return {
        "status": True,
        "data": response.data,
        "message": "Session updated successfully",
    }


@router.delete("/{session_id}")
async def delete_session(
    session_id: int, 
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Delete a session for the current authenticated user"""
    logger.info(f"User {current_user.email} (ID: {current_user.id}) attempting to delete session ID: {session_id}.")
    # Verify session belongs to user before deleting
    existing = db.get(Session, filters={"id": session_id, "user_id": current_user.id})
    if not existing.status or not existing.data:
        raise HTTPException(status_code=404, detail="Session not found or access denied for deletion")
    
    # Delete the session
    delete_response = db.delete(filters={"id": session_id, "user_id": current_user.id}, model_class=Session)
    if not delete_response.status:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {delete_response.message}")

    logger.info(f"Session ID {session_id} deleted successfully by user {current_user.email}.")
    return {"status": True, "message": "Session deleted successfully"}


@router.get("/{session_id}/runs")
async def list_session_runs(
    session_id: int, 
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Get complete session history organized by runs for the current authenticated user"""
    logger.info(f"User {current_user.email} (ID: {current_user.id}) requesting runs for session ID: {session_id}.")
    try:
        # 1. Verify session exists and belongs to user
        session_obj = db.get( # Renamed variable
            Session, filters={"id": session_id, "user_id": current_user.id}, return_json=False
        )
        if not session_obj.status:
            raise HTTPException(
                status_code=500, detail="Database error while fetching session"
            )
        if not session_obj.data:
            raise HTTPException(
                status_code=404, detail="Session not found or access denied"
            )

        # 2. Get ordered runs for session (user_id on Run can also be checked if needed, but session ownership should suffice)
        runs_response = db.get( # Renamed variable
            Run, filters={"session_id": session_id}, order="asc", return_json=False
        )
        if not runs_response.status:
            raise HTTPException(
                status_code=500, detail="Database error while fetching runs"
            )

        # 3. Build response with messages per run
        run_data = []
        if runs_response.data:  # It's ok to have no runs
            for run_item in runs_response.data: # Renamed loop variable
                try:
                    # Get messages for this specific run
                    messages_response = db.get( # Renamed variable
                        Message,
                        filters={"run_id": run_item.id},
                        order="asc",
                        return_json=False,
                    )
                    if not messages_response.status:
                        logger.error(f"Failed to fetch messages for run {run_item.id}")
                        # Continue processing other runs even if one fails
                        messages_response.data = []

                    run_data.append(
                        {
                            "id": str(run_item.id),
                            "created_at": run_item.created_at,
                            "status": run_item.status,
                            "task": run_item.task,
                            "team_result": run_item.team_result,
                            "messages": messages_response.data or [],
                            "input_request": getattr(run_item, "input_request", None),
                        }
                    )
                except Exception as e:
                    logger.error(f"Error processing run {run_item.id}: {str(e)}")
                    # Include run with error state instead of failing entirely
                    run_data.append(
                        {
                            "id": str(run_item.id),
                            "created_at": run_item.created_at,
                            "status": "ERROR",
                            "task": run_item.task,
                            "team_result": None,
                            "messages": [],
                            "error": f"Failed to process run: {str(e)}",
                            "input_request": getattr(run_item, "input_request", None),
                        }
                    )
        logger.info(f"Successfully retrieved runs for session ID {session_id} for user {current_user.email}.")
        return {"status": True, "data": {"runs": run_data}}

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in list_messages: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error while fetching session data"
        ) from e
