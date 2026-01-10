"""Message-related API endpoints."""

import asyncio
import json
import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ...capture.models import CapturedMessage, MessageDirection
from ..dependencies import get_storage, get_proxy_server

logger = logging.getLogger(__name__)

router = APIRouter()


class ReplayRequest(BaseModel):
    """Request body for replaying a message with optional modifications."""
    modified_message: Optional[str] = None  # JSON string of the modified message


class ReplayResponse(BaseModel):
    """Response from replaying a message."""
    success: bool
    pool_response: Optional[dict] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None


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


@router.post("/messages/{message_id}/replay", response_model=ReplayResponse)
async def replay_message(message_id: str, request: ReplayRequest = None):
    """
    Replay a mining.submit message to the pool for debugging.

    This reuses the existing authenticated session and sends the message
    to the pool, returning the response without forwarding it to the miner.

    Optionally accepts a modified_message in the request body to send custom parameters.
    """
    storage = get_storage()
    message = await storage.get_message_by_id(message_id)

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify it's a mining.submit from miner to pool
    if message.direction != MessageDirection.MINER_TO_POOL:
        raise HTTPException(
            status_code=400,
            detail="Can only replay messages from miner to pool"
        )

    if not message.decoded or message.decoded.get("method") != "mining.submit":
        raise HTTPException(
            status_code=400,
            detail="Can only replay mining.submit messages"
        )

    # Get the active session
    proxy_server = get_proxy_server()
    active_session = proxy_server.get_active_session(message.session_id)

    if not active_session:
        raise HTTPException(
            status_code=404,
            detail="Session not active. The miner connection may have closed."
        )

    try:
        # Use modified message if provided, otherwise use original
        if request and request.modified_message:
            logger.info(f"Replaying MODIFIED message {message_id} via session {message.session_id}")
            message_data = request.modified_message
            # Validate it's valid JSON
            try:
                modified_json = json.loads(message_data)
                logger.debug(f"Modified message: {modified_json}")
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid JSON in modified_message: {str(e)}"
                )
        else:
            logger.info(f"Replaying original message {message_id} via session {message.session_id}")
            # Reconstruct the message to send
            if message.decoded:
                message_data = json.dumps(message.decoded)
            else:
                # Fallback to raw message
                raw_message = message.raw
                try:
                    import base64
                    decoded_bytes = base64.b64decode(raw_message)
                    message_data = decoded_bytes.decode() if isinstance(decoded_bytes, bytes) else decoded_bytes
                except Exception:
                    message_data = raw_message if isinstance(raw_message, str) else raw_message.decode()

        # Use the session's replay method
        pool_response, latency_ms = await active_session.replay_message(message_data)

        if pool_response:
            logger.info(f"Replay successful: {pool_response}")

            # Capture the replay as a message in the message list
            replay_message_id = await active_session.capture_replay_message(
                request_data=message_data,
                response_dict=pool_response,
                latency_ms=latency_ms
            )
            logger.debug(f"Captured replay message as {replay_message_id}")

            return ReplayResponse(
                success=True,
                pool_response=pool_response,
                latency_ms=latency_ms
            )
        else:
            return ReplayResponse(
                success=False,
                error="No response received from pool"
            )

    except asyncio.TimeoutError:
        logger.error(f"Timeout replaying message to pool")
        return ReplayResponse(
            success=False,
            error="Timeout waiting for pool response"
        )
    except Exception as e:
        logger.error(f"Error replaying message: {e}", exc_info=True)
        return ReplayResponse(
            success=False,
            error=str(e)
        )

