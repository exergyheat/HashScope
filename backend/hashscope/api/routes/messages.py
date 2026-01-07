"""Message-related API endpoints."""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from ...capture.models import CapturedMessage, MessageDirection
from ..dependencies import get_storage

router = APIRouter()


@router.get("/messages", response_model=list[CapturedMessage])
async def get_messages(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    direction: Optional[MessageDirection] = Query(None, description="Filter by direction"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of messages"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
):
    """Get captured messages with optional filtering."""
    storage = get_storage()
    messages = await storage.get_messages(
        session_id=session_id,
        direction=direction,
        limit=limit,
        offset=offset,
    )
    return messages


@router.get("/messages/{message_id}", response_model=CapturedMessage)
async def get_message(message_id: str):
    """Get a specific message by ID."""
    storage = get_storage()
    message = await storage.get_message_by_id(message_id)

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    return message

