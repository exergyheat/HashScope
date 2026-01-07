"""Session-related API endpoints."""

from fastapi import APIRouter, HTTPException

from ..dependencies import get_storage

router = APIRouter()


@router.get("/sessions")
async def get_sessions():
    """Get all sessions."""
    storage = get_storage()
    sessions = await storage.get_sessions()
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific session with statistics."""
    storage = get_storage()
    session = await storage.get_session_stats(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session

