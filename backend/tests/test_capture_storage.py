"""Tests for capture storage."""

import pytest
from datetime import datetime
from hashscope.capture.storage import CaptureStorage
from hashscope.capture.models import CapturedMessage, MessageDirection


@pytest.mark.asyncio
class TestCaptureStorage:
    """Test the capture storage system."""

    async def test_add_and_retrieve_message(self):
        """Test adding and retrieving a message."""
        storage = CaptureStorage(max_total=100, max_per_session=50)

        message = CapturedMessage(
            id="test-1",
            ts_recv=datetime.utcnow(),
            ts_fwd=datetime.utcnow(),
            direction=MessageDirection.MINER_TO_POOL,
            session_id="session-1",
            peer="192.168.1.100:12345",
            raw='{"id":1,"method":"mining.subscribe"}',
            decoded={"id": 1, "method": "mining.subscribe"},
            parse_error=None,
            size_bytes=35,
        )

        await storage.add_message(message)

        messages = await storage.get_messages()
        assert len(messages) == 1
        assert messages[0].id == "test-1"

    async def test_filter_by_session(self):
        """Test filtering messages by session."""
        storage = CaptureStorage()

        # Add messages from different sessions
        for i in range(5):
            message = CapturedMessage(
                id=f"msg-{i}",
                ts_recv=datetime.utcnow(),
                direction=MessageDirection.MINER_TO_POOL,
                session_id=f"session-{i % 2}",
                peer="192.168.1.100:12345",
                raw="{}",
                decoded={},
                size_bytes=2,
            )
            await storage.add_message(message)

        # Get messages for session-0
        messages = await storage.get_messages(session_id="session-0")
        assert len(messages) == 3
        assert all(m.session_id == "session-0" for m in messages)

    async def test_filter_by_direction(self):
        """Test filtering messages by direction."""
        storage = CaptureStorage()

        # Add messages in both directions
        for i in range(4):
            direction = MessageDirection.MINER_TO_POOL if i % 2 == 0 else MessageDirection.POOL_TO_MINER
            message = CapturedMessage(
                id=f"msg-{i}",
                ts_recv=datetime.utcnow(),
                direction=direction,
                session_id="session-1",
                peer="192.168.1.100:12345",
                raw="{}",
                decoded={},
                size_bytes=2,
            )
            await storage.add_message(message)

        # Get messages miner to pool
        messages = await storage.get_messages(direction=MessageDirection.MINER_TO_POOL)
        assert len(messages) == 2
        assert all(m.direction == MessageDirection.MINER_TO_POOL for m in messages)

    async def test_get_sessions(self):
        """Test getting session metadata."""
        storage = CaptureStorage()

        # Add messages from two sessions
        for session_id in ["session-1", "session-2"]:
            message = CapturedMessage(
                id=f"{session_id}-msg",
                ts_recv=datetime.utcnow(),
                direction=MessageDirection.MINER_TO_POOL,
                session_id=session_id,
                peer=f"192.168.1.{session_id[-1]}:12345",
                raw="{}",
                decoded={},
                size_bytes=2,
            )
            await storage.add_message(message)

        sessions = await storage.get_sessions()
        assert len(sessions) == 2
        assert sessions[0]["session_id"] in ["session-1", "session-2"]
        assert sessions[0]["message_count"] == 1

    async def test_max_messages_limit(self):
        """Test that storage respects max messages limit."""
        storage = CaptureStorage(max_total=10)

        # Add more messages than the limit
        for i in range(15):
            message = CapturedMessage(
                id=f"msg-{i}",
                ts_recv=datetime.utcnow(),
                direction=MessageDirection.MINER_TO_POOL,
                session_id="session-1",
                peer="192.168.1.100:12345",
                raw="{}",
                decoded={},
                size_bytes=2,
            )
            await storage.add_message(message)

        messages = await storage.get_messages()
        assert len(messages) == 10  # Should only keep the last 10

    async def test_subscribe_to_updates(self):
        """Test subscribing to message updates."""
        storage = CaptureStorage()
        received_messages = []

        async def callback(message: CapturedMessage):
            received_messages.append(message)

        storage.subscribe(callback)

        # Add a message
        message = CapturedMessage(
            id="test-1",
            ts_recv=datetime.utcnow(),
            direction=MessageDirection.MINER_TO_POOL,
            session_id="session-1",
            peer="192.168.1.100:12345",
            raw="{}",
            decoded={},
            size_bytes=2,
        )
        await storage.add_message(message)

        # Callback should have been called
        assert len(received_messages) == 1
        assert received_messages[0].id == "test-1"

