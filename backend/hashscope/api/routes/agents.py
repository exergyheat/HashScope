"""Agent telemetry API endpoints."""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Optional
import asyncio
import json
import logging

from ..dependencies import get_telemetry_storage
from ...nostr.schemas import TelemetryEvent

router = APIRouter()
logger = logging.getLogger(__name__)

# Import for handling WebSocket disconnections gracefully
try:
    from uvicorn.protocols.utils import ClientDisconnected
except ImportError:
    # Fallback if running under different ASGI server
    ClientDisconnected = Exception


@router.get("/agents")
async def get_agents():
    """Get all active agents with their latest telemetry."""
    telemetry_storage = get_telemetry_storage()
    agents = await telemetry_storage.get_agents()
    return agents


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get detailed telemetry for a specific agent."""
    telemetry_storage = get_telemetry_storage()

    latest = await telemetry_storage.get_latest_telemetry(agent_id)
    if not latest:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent_id": agent_id,
        "latest": latest.model_dump(),
    }


@router.get("/agents/{agent_id}/history")
async def get_agent_history(agent_id: str, limit: int = 50):
    """Get telemetry history for a specific agent."""
    telemetry_storage = get_telemetry_storage()

    history = await telemetry_storage.get_agent_telemetry(agent_id, limit=limit)
    if not history:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent_id": agent_id,
        "history": [t.model_dump() for t in history],
    }


@router.websocket("/ws/agents")
async def agents_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time agent telemetry updates."""
    await websocket.accept()
    telemetry_storage = get_telemetry_storage()

    # Queue for this WebSocket connection
    queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue()

    async def telemetry_callback(telemetry: TelemetryEvent):
        """Callback to receive telemetry events."""
        try:
            await queue.put(telemetry)
        except Exception as e:
            logger.error(f"Error queuing telemetry: {e}")

    # Subscribe to telemetry updates
    telemetry_storage.subscribe(telemetry_callback)

    try:
        # Send initial agent list
        agents = await telemetry_storage.get_agents()
        await websocket.send_json({
            "type": "init",
            "agents": agents,
        })

        # Stream updates
        while True:
            try:
                # Wait for new telemetry with timeout
                telemetry = await asyncio.wait_for(queue.get(), timeout=30.0)

                try:
                    await websocket.send_json({
                        "type": "telemetry",
                        "agent_id": telemetry.agent_id,
                        "data": telemetry.model_dump(),
                    })
                except (WebSocketDisconnect, ClientDisconnected):
                    # Client disconnected during send, exit gracefully
                    break

            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except (WebSocketDisconnect, ClientDisconnected):
                    # Client disconnected during ping, exit gracefully
                    break

    except WebSocketDisconnect:
        logger.info("Agent telemetry WebSocket disconnected (normal)")
    except ClientDisconnected:
        logger.info("Agent telemetry WebSocket client disconnected (normal)")
    except Exception as e:
        logger.error(f"Error in agent telemetry WebSocket: {e}", exc_info=True)
    finally:
        # Unsubscribe
        telemetry_storage.unsubscribe(telemetry_callback)

