"""Telemetry storage for agent events."""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional, Callable, Awaitable

from ..nostr.schemas import TelemetryEvent

logger = logging.getLogger(__name__)


class TelemetryStorage:
    """Thread-safe in-memory storage for agent telemetry."""

    def __init__(self, max_per_agent: int = 100):
        """
        Initialize telemetry storage.

        Args:
            max_per_agent: Maximum telemetry events to store per agent
        """
        self.max_per_agent = max_per_agent

        # Per-agent telemetry storage (ring buffer)
        self._agent_telemetry: dict[str, deque[TelemetryEvent]] = defaultdict(
            lambda: deque(maxlen=max_per_agent)
        )

        # Latest telemetry per agent (for quick access)
        self._latest_telemetry: dict[str, TelemetryEvent] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Subscribers for real-time updates
        self._subscribers: list[Callable[[TelemetryEvent], Awaitable[None]]] = []

    async def add_telemetry(self, telemetry: TelemetryEvent) -> None:
        """
        Add a telemetry event to storage.

        Args:
            telemetry: The telemetry event to store
        """
        async with self._lock:
            agent_id = telemetry.agent_id
            history_count = len(self._agent_telemetry[agent_id])
            self._agent_telemetry[agent_id].append(telemetry)
            self._latest_telemetry[agent_id] = telemetry
            logger.info(f"💾 Stored telemetry for agent {agent_id} (history: {history_count + 1} events)")

        # Notify subscribers (outside lock)
        logger.info(f"🔔 Notifying {len(self._subscribers)} subscribers about telemetry from {agent_id}")
        await self._notify_subscribers(telemetry)

    async def get_agents(self) -> list[dict]:
        """
        Get list of all agents with their latest telemetry.

        Returns:
            List of agent summaries
        """
        async with self._lock:
            agents = []
            for agent_id, telemetry in self._latest_telemetry.items():
                agents.append({
                    "agent_id": agent_id,
                    "last_seen": telemetry.ts,
                    "conn_state": telemetry.conn_state,
                    "stats": telemetry.stats.model_dump(),
                    "pool_target": telemetry.pool_target.model_dump(),
                })
            return agents

    async def get_agent_telemetry(
        self,
        agent_id: str,
        limit: int = 50,
    ) -> list[TelemetryEvent]:
        """
        Get telemetry history for a specific agent.

        Args:
            agent_id: The agent ID
            limit: Maximum number of events to return

        Returns:
            List of telemetry events (newest first)
        """
        async with self._lock:
            telemetry_list = list(self._agent_telemetry.get(agent_id, []))
            # Reverse to get newest first
            telemetry_list.reverse()
            return telemetry_list[:limit]

    async def get_latest_telemetry(self, agent_id: str) -> Optional[TelemetryEvent]:
        """
        Get the latest telemetry for a specific agent.

        Args:
            agent_id: The agent ID

        Returns:
            Latest telemetry event or None if not found
        """
        async with self._lock:
            return self._latest_telemetry.get(agent_id)

    def subscribe(self, callback: Callable[[TelemetryEvent], Awaitable[None]]) -> None:
        """
        Subscribe to real-time telemetry updates.

        Args:
            callback: Async function to call with each new telemetry event
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[TelemetryEvent], Awaitable[None]]) -> None:
        """
        Unsubscribe from real-time updates.

        Args:
            callback: The callback to remove
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def _notify_subscribers(self, telemetry: TelemetryEvent) -> None:
        """Notify all subscribers of a new telemetry event."""
        for i, callback in enumerate(self._subscribers):
            try:
                logger.debug(f"📞 Calling subscriber {i+1}/{len(self._subscribers)} for agent {telemetry.agent_id}")
                await callback(telemetry)
                logger.debug(f"✅ Subscriber {i+1} notified successfully")
            except Exception as e:
                logger.error(f"❌ Error notifying subscriber {i+1}: {e}", exc_info=True)

    async def clear(self) -> None:
        """Clear all stored telemetry."""
        async with self._lock:
            self._agent_telemetry.clear()
            self._latest_telemetry.clear()

