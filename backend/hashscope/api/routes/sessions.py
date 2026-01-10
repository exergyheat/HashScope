"""Session-related API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_storage, get_proxy_server

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


# Auto-replay endpoints (load testing)

@router.post("/sessions/{session_id}/auto-replay/enable")
async def enable_session_auto_replay(session_id: str):
    """Enable auto-replay for a session."""
    storage = get_storage()
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await storage.enable_session_auto_replay(session_id)
    return {"session_id": session_id, "auto_replay_enabled": True}


@router.post("/sessions/{session_id}/auto-replay/disable")
async def disable_session_auto_replay(session_id: str):
    """Disable auto-replay for a session."""
    storage = get_storage()
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await storage.disable_session_auto_replay(session_id)
    return {"session_id": session_id, "auto_replay_enabled": False}


@router.get("/sessions/{session_id}/auto-replay/status")
async def get_session_auto_replay_status(session_id: str):
    """Get the auto-replay status for a session."""
    storage = get_storage()
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    auto_replay_enabled = await storage.is_session_auto_replay_enabled(session_id)
    return {"session_id": session_id, "auto_replay_enabled": auto_replay_enabled}


class AutoReplayCountRequest(BaseModel):
    auto_replay_count: int = Field(..., ge=1, le=900_000)


@router.post("/sessions/{session_id}/auto-replay-count")
async def set_session_auto_replay_count(session_id: str, request: AutoReplayCountRequest):
    """Set the auto-replay count for a session (1-100)."""
    storage = get_storage()
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await storage.set_session_auto_replay_count(session_id, request.auto_replay_count)
    return {"session_id": session_id, "auto_replay_count": request.auto_replay_count}


@router.get("/sessions/{session_id}/auto-replay-count")
async def get_session_auto_replay_count(session_id: str):
    """Get the auto-replay count for a session."""
    storage = get_storage()
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    auto_replay_count = await storage.get_session_auto_replay_count(session_id)
    return {"session_id": session_id, "auto_replay_count": auto_replay_count}


# Session control

@router.post("/sessions/{session_id}/disconnect")
async def disconnect_session(session_id: str):
    """
    Forcefully disconnect a session.

    This closes both the pool and miner connections, forcing the miner
    to completely reconnect and establish a fresh session.
    """
    storage = get_storage()
    proxy_server = get_proxy_server()

    # Check if session exists
    session = await storage.get_session_stats(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get the active session
    active_session = proxy_server.get_active_session(session_id)
    if not active_session:
        raise HTTPException(
            status_code=404,
            detail="Session not active or already disconnected"
        )

    # Disconnect both pool and miner connections
    await active_session.disconnect_from_pool()

    return {
        "session_id": session_id,
        "message": "Session disconnected. Both pool and miner connections closed."
    }

