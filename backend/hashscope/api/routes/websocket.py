"""WebSocket endpoint for real-time message streaming."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ...capture.models import CapturedMessage
from ..dependencies import get_storage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time message streaming.

    Query parameters:
    - session_id: Optional filter to only receive messages for a specific session
    """
    await websocket.accept()

    storage = get_storage()

    async def message_callback(message: CapturedMessage):
        """Callback for new messages."""
        # Filter by session if requested
        if session_id and message.session_id != session_id:
            return

        try:
            # Send message to client
            await websocket.send_json(message.model_dump(mode='json'))
        except Exception as e:
            logger.error(f"Error sending message to websocket: {e}")

    # Subscribe to new messages
    storage.subscribe(message_callback)

    try:
        # Keep connection alive
        while True:
            # Receive messages from client (if any)
            data = await websocket.receive_text()
            # We don't process client messages for now, just keep connection alive

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Unsubscribe on disconnect
        storage.unsubscribe(message_callback)

