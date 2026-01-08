"""Session-related API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..dependencies import get_storage

router = APIRouter()


class RepeatCountRequest(BaseModel):
    """Request to set repeat count for a session."""
    repeat_count: int


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


# Broadcast control endpoints (Iteration 2)

@router.post("/sessions/{session_id}/broadcast/enable")
async def enable_session_broadcast(session_id: str):
    """Enable ShareEvent broadcasting for a session."""
    storage = get_storage()

    # Check if session exists
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await storage.enable_session_broadcast(session_id)

    return {"session_id": session_id, "broadcast_enabled": True}


@router.post("/sessions/{session_id}/broadcast/disable")
async def disable_session_broadcast(session_id: str):
    """Disable ShareEvent broadcasting for a session."""
    storage = get_storage()

    # Check if session exists
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await storage.disable_session_broadcast(session_id)

    return {"session_id": session_id, "broadcast_enabled": False}


@router.get("/sessions/{session_id}/broadcast/status")
async def get_session_broadcast_status(session_id: str):
    """Get broadcast status for a session."""
    storage = get_storage()

    # Check if session exists
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    broadcast_enabled = await storage.is_session_broadcast_enabled(session_id)

    return {"session_id": session_id, "broadcast_enabled": broadcast_enabled}


@router.post("/sessions/{session_id}/repeat-count")
async def set_session_repeat_count(session_id: str, request: RepeatCountRequest):
    """Set the repeat count for a session (load testing)."""
    storage = get_storage()

    # Check if session exists
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate repeat count
    if request.repeat_count < 1 or request.repeat_count > 1000:
        raise HTTPException(status_code=400, detail="Repeat count must be between 1 and 1000")

    await storage.set_session_repeat_count(session_id, request.repeat_count)

    return {"session_id": session_id, "repeat_count": request.repeat_count}


@router.get("/sessions/{session_id}/repeat-count")
async def get_session_repeat_count(session_id: str):
    """Get the repeat count for a session."""
    storage = get_storage()

    # Check if session exists
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    repeat_count = await storage.get_session_repeat_count(session_id)

    return {"session_id": session_id, "repeat_count": repeat_count}

