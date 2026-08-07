"""In-memory storage for captured messages."""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Optional, Callable, Awaitable

from .models import CapturedMessage, MessageDirection

logger = logging.getLogger(__name__)


class CaptureStorage:
    """Thread-safe in-memory storage for captured messages."""

    def __init__(self, max_total: int = 50_000, max_per_session: int = 10_000):
        """
        Initialize storage.

        Args:
            max_total: Maximum total messages to store
            max_per_session: Maximum messages per session
        """
        self.max_total = max_total
        self.max_per_session = max_per_session

        # Global message storage (ring buffer)
        self._messages: deque[CapturedMessage] = deque(maxlen=max_total)

        # Per-session storage
        self._session_messages: dict[str, deque[CapturedMessage]] = defaultdict(
            lambda: deque(maxlen=max_per_session)
        )

        # Session metadata
        self._session_metadata: dict[str, dict] = {}

        # Pending requests waiting for responses (by session_id -> jsonrpc_id -> message)
        self._pending_requests: dict[str, dict[int | str, CapturedMessage]] = defaultdict(dict)

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Subscribers for real-time updates
        self._subscribers: list[Callable[[CapturedMessage], Awaitable[None]]] = []

        # Session broadcast control (Iteration 2)
        self._session_broadcast_enabled: dict[str, bool] = {}
        self._session_repeat_count: dict[str, int] = {}  # Number of times to repeat each share

        # Auto-replay control (load testing)
        self._session_auto_replay_enabled: dict[str, bool] = {}
        self._session_auto_replay_count: dict[str, int] = {}  # Number of auto-replays (1-100)

    async def add_message(self, message: CapturedMessage, notify: bool = True) -> None:
        """
        Add a captured message to storage.
        Automatically pairs requests with their responses.

        Args:
            message: The captured message to store
            notify: Whether to notify WebSocket subscribers (default True)
        """
        should_notify = False
        is_new_message = False  # Track if we're adding a new message vs updating existing

        async with self._lock:
            # Check if message with this ID already exists (deduplication)
            existing_msg = next((m for m in self._messages if m.id == message.id), None)
            if existing_msg:
                logger.debug(f"Message {message.id} already exists, skipping")
                return
            # Check if this is a response to a pending request
            if message.is_response and message.jsonrpc_id is not None:
                # Look for matching request in this session
                pending = self._pending_requests.get(message.session_id, {})
                if message.jsonrpc_id in pending:
                    # Found the matching request!
                    request_msg = pending[message.jsonrpc_id]

                    # Update the request message with the response data
                    request_msg.response = message.decoded
                    request_msg.response_ts_recv = message.ts_recv
                    request_msg.response_raw = message.raw
                    request_msg.paired_message_id = message.id

                    # Calculate latency in milliseconds
                    latency_delta = message.ts_recv - request_msg.ts_recv
                    request_msg.latency_ms = latency_delta.total_seconds() * 1000

                    # Remove from pending
                    del pending[message.jsonrpc_id]

                    # Notify subscribers about the updated request (with response now)
                    should_notify = True
                    notify_msg = request_msg
                    is_new_message = False  # Just updating existing message

                    logger.debug(
                        f"Paired response {message.id} with request {request_msg.id} "
                        f"(jsonrpc_id={message.jsonrpc_id})"
                    )

                    # Don't store the response as a separate message
                    # Just update the existing request
                else:
                    # Response without matching request - store it normally
                    self._messages.append(message)
                    self._session_messages[message.session_id].append(message)
                    should_notify = True
                    notify_msg = message
                    is_new_message = True

            # If it's a request, store it and track as pending
            elif message.is_request and message.jsonrpc_id is not None:
                self._messages.append(message)
                self._session_messages[message.session_id].append(message)

                # Track as pending request
                self._pending_requests[message.session_id][message.jsonrpc_id] = message

                should_notify = True
                notify_msg = message
                is_new_message = True

            # Not a request/response pair (e.g., notification) - store normally
            else:
                self._messages.append(message)
                self._session_messages[message.session_id].append(message)
                should_notify = True
                notify_msg = message
                is_new_message = True

            # Update session metadata
            if message.session_id not in self._session_metadata:
                self._session_metadata[message.session_id] = {
                    "session_id": message.session_id,
                    "peer": message.peer,
                    "first_seen": message.ts_recv,
                    "last_seen": message.ts_recv,
                    "message_count": 0,
                    "user_agent": None,
                    "mining_session_id": None,
                    "difficulty": None,
                    "pool_host": None,
                    "pool_port": None,
                    "pool_connected": False,
                }

            metadata = self._session_metadata[message.session_id]
            metadata["last_seen"] = message.ts_recv
            # Only increment count when adding a NEW message, not when pairing response with request
            if is_new_message:
                metadata["message_count"] += 1

            # Extract user agent and mining session ID from mining.subscribe
            if (message.decoded and
                message.decoded.get("method") == "mining.subscribe" and
                message.decoded.get("params")):
                params = message.decoded["params"]
                if isinstance(params, list) and len(params) > 0:
                    # First param is user agent
                    if params[0] and not metadata.get("user_agent"):
                        metadata["user_agent"] = params[0]
                    # Second param (if present) is mining session ID for reconnection
                    if len(params) > 1 and params[1] and not metadata.get("mining_session_id"):
                        metadata["mining_session_id"] = params[1]

            # Extract difficulty from mining.set_difficulty (sent by pool)
            if (message.decoded and
                message.decoded.get("method") == "mining.set_difficulty" and
                message.decoded.get("params")):
                params = message.decoded["params"]
                if isinstance(params, list) and len(params) > 0:
                    # First param is the difficulty value
                    metadata["difficulty"] = params[0]
                    logger.debug(f"Updated difficulty for session {message.session_id}: {params[0]}")

        # Notify subscribers (outside lock to avoid blocking)
        if should_notify and notify:
            await self._notify_subscribers(notify_msg)

    async def get_messages(
        self,
        session_id: Optional[str] = None,
        direction: Optional[MessageDirection] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CapturedMessage]:
        """
        Get messages with optional filtering.

        Args:
            session_id: Filter by session ID
            direction: Filter by direction
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of captured messages
        """
        async with self._lock:
            # Choose source
            if session_id:
                messages = list(self._session_messages.get(session_id, []))
            else:
                messages = list(self._messages)

            # Filter by direction
            if direction:
                messages = [m for m in messages if m.direction == direction]

            # Sort by timestamp (newest first)
            # Use response timestamp if available (for paired messages), otherwise use request timestamp
            messages.sort(key=lambda m: m.response_ts_recv or m.ts_recv, reverse=True)

            # Apply pagination
            return messages[offset:offset + limit]

    async def get_message_by_id(self, message_id: str) -> Optional[CapturedMessage]:
        """
        Get a specific message by ID.

        Args:
            message_id: The message ID

        Returns:
            The message if found, None otherwise
        """
        async with self._lock:
            for msg in self._messages:
                if msg.id == message_id:
                    return msg
        return None

    async def get_sessions(self) -> list[dict]:
        """
        Get all session metadata.

        Returns:
            List of session metadata dicts
        """
        async with self._lock:
            sessions = []
            for session_id, metadata in self._session_metadata.items():
                session_data = metadata.copy()
                # Add broadcast status
                session_data["broadcast_enabled"] = self._session_broadcast_enabled.get(session_id, False)
                session_data["repeat_count"] = self._session_repeat_count.get(session_id, 1)
                # Add auto-replay status
                session_data["auto_replay_enabled"] = self._session_auto_replay_enabled.get(session_id, False)
                session_data["auto_replay_count"] = self._session_auto_replay_count.get(session_id, 1)

                # Ensure pool fields exist (for backward compatibility with old sessions)
                if "pool_host" not in session_data:
                    session_data["pool_host"] = None
                if "pool_port" not in session_data:
                    session_data["pool_port"] = None
                if "pool_connected" not in session_data:
                    session_data["pool_connected"] = None

                sessions.append(session_data)
            return sessions

    async def get_session_stats(self, session_id: str) -> Optional[dict]:
        """
        Get statistics for a specific session.

        Args:
            session_id: The session ID

        Returns:
            Session statistics or None if not found
        """
        async with self._lock:
            if session_id not in self._session_metadata:
                return None

            messages = self._session_messages[session_id]
            metadata = self._session_metadata[session_id].copy()

            # Calculate additional stats
            if messages:
                miner_to_pool = sum(1 for m in messages if m.direction == MessageDirection.MINER_TO_POOL)
                pool_to_miner = sum(1 for m in messages if m.direction == MessageDirection.POOL_TO_MINER)
                parse_errors = sum(1 for m in messages if m.parse_error)

                metadata["stats"] = {
                    "total_messages": len(messages),
                    "miner_to_pool": miner_to_pool,
                    "pool_to_miner": pool_to_miner,
                    "parse_errors": parse_errors,
                }

            return metadata

    def subscribe(self, callback: Callable[[CapturedMessage], Awaitable[None]]) -> None:
        """
        Subscribe to real-time message updates.

        Args:
            callback: Async function to call with each new message
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[CapturedMessage], Awaitable[None]]) -> None:
        """
        Unsubscribe from real-time updates.

        Args:
            callback: The callback to remove
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def _notify_subscribers(self, message: CapturedMessage) -> None:
        """Notify all subscribers of a new message."""
        for callback in self._subscribers:
            try:
                await callback(message)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}", exc_info=True)

    async def clear(self) -> None:
        """Clear all stored messages."""
        async with self._lock:
            self._messages.clear()
            self._session_messages.clear()
            self._session_metadata.clear()

    # Session broadcast control methods (Iteration 2)

    async def enable_session_broadcast(self, session_id: str) -> None:
        """
        Enable ShareEvent publishing for a session.

        Args:
            session_id: The session ID to enable
        """
        async with self._lock:
            self._session_broadcast_enabled[session_id] = True
            logger.info(f"Enabled broadcast for session {session_id}")

    async def disable_session_broadcast(self, session_id: str) -> None:
        """
        Disable ShareEvent publishing for a session.

        Args:
            session_id: The session ID to disable
        """
        async with self._lock:
            self._session_broadcast_enabled[session_id] = False
            logger.info(f"Disabled broadcast for session {session_id}")

    async def is_session_broadcast_enabled(self, session_id: str) -> bool:
        """
        Check if ShareEvent publishing is enabled for a session.

        Args:
            session_id: The session ID to check

        Returns:
            True if broadcast is enabled, False otherwise (default)
        """
        async with self._lock:
            return self._session_broadcast_enabled.get(session_id, False)

    async def set_session_repeat_count(self, session_id: str, repeat_count: int) -> None:
        """
        Set the repeat count for a session (load testing feature).

        Args:
            session_id: The session ID
            repeat_count: Number of times to repeat each share (1-1000)
        """
        # Clamp to reasonable bounds
        repeat_count = max(1, min(repeat_count, 1000))
        async with self._lock:
            self._session_repeat_count[session_id] = repeat_count
            logger.info(f"Set repeat count for session {session_id} to {repeat_count}")

    async def get_session_repeat_count(self, session_id: str) -> int:
        """
        Get the repeat count for a session.

        Args:
            session_id: The session ID

        Returns:
            Repeat count (default 1)
        """
        async with self._lock:
            return self._session_repeat_count.get(session_id, 1)

    # Auto-replay control methods (load testing)

    async def enable_session_auto_replay(self, session_id: str) -> None:
        """Enable auto-replay for a session."""
        async with self._lock:
            self._session_auto_replay_enabled[session_id] = True
            logger.info(f"Enabled auto-replay for session {session_id}")

    async def disable_session_auto_replay(self, session_id: str) -> None:
        """Disable auto-replay for a session."""
        async with self._lock:
            self._session_auto_replay_enabled[session_id] = False
            logger.info(f"Disabled auto-replay for session {session_id}")

    async def is_session_auto_replay_enabled(self, session_id: str) -> bool:
        """Check if auto-replay is enabled for a session."""
        async with self._lock:
            return self._session_auto_replay_enabled.get(session_id, False)

    async def set_session_auto_replay_count(self, session_id: str, count: int) -> None:
        """Set the auto-replay count for a session (1-900000)."""
        if not (1 <= count <= 900_000):
            raise ValueError("Auto-replay count must be between 1 and 900,000")
        async with self._lock:
            self._session_auto_replay_count[session_id] = count
            logger.info(f"Session {session_id} auto-replay count set to {count}")

    async def get_session_auto_replay_count(self, session_id: str) -> int:
        """Get the auto-replay count for a session (default 1)."""
        async with self._lock:
            return self._session_auto_replay_count.get(session_id, 1)

    async def register_session(
        self,
        session_id: str,
        peer: str,
        pool_host: str,
        pool_port: int,
    ) -> None:
        """
        Register a session when it starts (before pool connection).

        Args:
            session_id: The session ID
            peer: Miner peer address (IP:port)
            pool_host: Target pool hostname
            pool_port: Target pool port
        """
        async with self._lock:
            if session_id not in self._session_metadata:
                now = datetime.utcnow()
                self._session_metadata[session_id] = {
                    "session_id": session_id,
                    "peer": peer,
                    "first_seen": now,
                    "last_seen": now,
                    "message_count": 0,
                    "user_agent": None,
                    "mining_session_id": None,
                    "difficulty": None,
                    "pool_host": pool_host,
                    "pool_port": pool_port,
                    "pool_connected": False,
                }
                logger.info(f"Registered session {session_id} targeting pool {pool_host}:{pool_port}")

    async def update_session_pool_status(
        self,
        session_id: str,
        connected: bool,
        pool_peer: Optional[str] = None,
    ) -> None:
        """
        Update pool connection status for a session.

        Args:
            session_id: The session ID
            connected: Whether pool connection is established
            pool_peer: Optional resolved pool peer address (IP:port)
        """
        async with self._lock:
            if session_id in self._session_metadata:
                self._session_metadata[session_id]["pool_connected"] = connected
                if pool_peer:
                    self._session_metadata[session_id]["pool_peer"] = pool_peer
                status_str = "connected" if connected else "failed"
                logger.info(f"Session {session_id} pool status: {status_str}")

    async def update_session_fields(
        self,
        session_id: str,
        **fields: Any,
    ) -> None:
        """
        Merge arbitrary fields into session metadata (hashsplit labels, workers, etc.).

        Ignores unknown sessions. Does not remove existing keys unless overwritten.
        """
        if not fields:
            return
        async with self._lock:
            if session_id not in self._session_metadata:
                return
            for key, value in fields.items():
                if value is not None:
                    self._session_metadata[session_id][key] = value

