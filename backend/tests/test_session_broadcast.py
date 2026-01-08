"""Tests for session broadcast control."""

import pytest
from hashscope.capture.storage import CaptureStorage


@pytest.mark.asyncio
async def test_session_broadcast_disabled_by_default():
    """Test that broadcast is disabled by default for new sessions."""
    storage = CaptureStorage()

    enabled = await storage.is_session_broadcast_enabled("test-session-1")
    assert enabled is False


@pytest.mark.asyncio
async def test_enable_session_broadcast():
    """Test enabling broadcast for a session."""
    storage = CaptureStorage()

    await storage.enable_session_broadcast("test-session-1")
    enabled = await storage.is_session_broadcast_enabled("test-session-1")
    assert enabled is True


@pytest.mark.asyncio
async def test_disable_session_broadcast():
    """Test disabling broadcast for a session."""
    storage = CaptureStorage()

    # Enable first
    await storage.enable_session_broadcast("test-session-1")
    assert await storage.is_session_broadcast_enabled("test-session-1") is True

    # Then disable
    await storage.disable_session_broadcast("test-session-1")
    assert await storage.is_session_broadcast_enabled("test-session-1") is False


@pytest.mark.asyncio
async def test_multiple_sessions_independent():
    """Test that broadcast state is independent per session."""
    storage = CaptureStorage()

    await storage.enable_session_broadcast("session-1")
    await storage.enable_session_broadcast("session-2")
    await storage.disable_session_broadcast("session-1")

    assert await storage.is_session_broadcast_enabled("session-1") is False
    assert await storage.is_session_broadcast_enabled("session-2") is True
    assert await storage.is_session_broadcast_enabled("session-3") is False

