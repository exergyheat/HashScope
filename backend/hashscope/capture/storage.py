"""In-memory storage for captured messages."""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional, Callable, Awaitable

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

    async def add_message(self, message: CapturedMessage) -> None:
        """
        Add a captured message to storage.
        Automatically pairs requests with their responses.

        Args:
            message: The captured message to store
        """
        should_notify = False
        is_new_message = False  # Track if we're adding a new message vs updating existing

        async with self._lock:
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
        if should_notify:
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
            return list(self._session_metadata.values())

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

