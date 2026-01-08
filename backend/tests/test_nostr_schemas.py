"""Tests for Nostr schemas."""

import pytest
from datetime import datetime
from hashscope.nostr.schemas import (
    ShareEvent,
    TelemetryEvent,
    PoolInfo,
    StratumData,
    Stats,
)


def test_pool_info():
    """Test PoolInfo model."""
    pool = PoolInfo(host="pool.example.com", port=3333)
    assert pool.host == "pool.example.com"
    assert pool.port == 3333


def test_stratum_data():
    """Test StratumData model."""
    stratum = StratumData(
        method="mining.submit",
        id=123,
        params=["worker1", "job123", "00000000", "507c0baa", "b2957c02"],
    )
    assert stratum.method == "mining.submit"
    assert stratum.id == 123
    assert len(stratum.params) == 5


def test_share_event():
    """Test ShareEvent model."""
    share = ShareEvent(
        run_id="test-run-123",
        event_id="event-456",
        seq=1,
        ts="2024-01-01T12:00:00Z",
        pool=PoolInfo(host="pool.example.com", port=3333),
        stratum=StratumData(
            method="mining.submit",
            id=1,
            params=["worker1", "job123", "00000000", "507c0baa", "b2957c02"],
        ),
    )

    assert share.schema == "hashscope.v1"
    assert share.run_id == "test-run-123"
    assert share.event_id == "event-456"
    assert share.seq == 1
    assert share.pool.host == "pool.example.com"
    assert share.stratum.method == "mining.submit"


def test_share_event_with_context():
    """Test ShareEvent with optional context."""
    share = ShareEvent(
        run_id="test-run-123",
        event_id="event-456",
        seq=1,
        ts="2024-01-01T12:00:00Z",
        pool=PoolInfo(host="pool.example.com", port=3333),
        stratum=StratumData(method="mining.submit", id=1, params=[]),
        context={"session_id": "session-789", "miner_peer": "192.168.1.1:12345"},
    )

    assert share.context is not None
    assert share.context["session_id"] == "session-789"
    assert share.context["miner_peer"] == "192.168.1.1:12345"


def test_stats():
    """Test Stats model."""
    stats = Stats(
        share_events_received_total=10,
        submits_attempted_total=10,
        submits_accepted_total=9,
        submits_rejected_total=1,
        last_submit_latency_ms=123.45,
    )

    assert stats.share_events_received_total == 10
    assert stats.submits_attempted_total == 10
    assert stats.submits_accepted_total == 9
    assert stats.submits_rejected_total == 1
    assert stats.last_submit_latency_ms == 123.45


def test_telemetry_event():
    """Test TelemetryEvent model."""
    telemetry = TelemetryEvent(
        run_id="test-run-123",
        agent_id="agent-001",
        ts="2024-01-01T12:00:00Z",
        pool_target=PoolInfo(host="pool.example.com", port=3333),
        conn_state="connected",
        stats=Stats(
            share_events_received_total=5,
            submits_attempted_total=5,
            submits_accepted_total=4,
            submits_rejected_total=1,
        ),
    )

    assert telemetry.schema == "hashscope.v1"
    assert telemetry.run_id == "test-run-123"
    assert telemetry.agent_id == "agent-001"
    assert telemetry.conn_state == "connected"
    assert telemetry.stats.submits_accepted_total == 4


def test_telemetry_event_with_errors():
    """Test TelemetryEvent with errors list."""
    telemetry = TelemetryEvent(
        run_id="test-run-123",
        agent_id="agent-001",
        ts="2024-01-01T12:00:00Z",
        pool_target=PoolInfo(host="pool.example.com", port=3333),
        conn_state="error",
        stats=Stats(),
        errors=["Connection lost", "Failed to submit"],
    )

    assert len(telemetry.errors) == 2
    assert "Connection lost" in telemetry.errors


def test_share_event_json_serialization():
    """Test ShareEvent JSON serialization."""
    share = ShareEvent(
        run_id="test-run-123",
        event_id="event-456",
        seq=1,
        ts="2024-01-01T12:00:00Z",
        pool=PoolInfo(host="pool.example.com", port=3333),
        stratum=StratumData(method="mining.submit", id=1, params=["param1"]),
    )

    json_str = share.model_dump_json()
    assert "test-run-123" in json_str
    assert "event-456" in json_str
    assert "mining.submit" in json_str


def test_telemetry_event_json_serialization():
    """Test TelemetryEvent JSON serialization."""
    telemetry = TelemetryEvent(
        run_id="test-run-123",
        agent_id="agent-001",
        ts="2024-01-01T12:00:00Z",
        pool_target=PoolInfo(host="pool.example.com", port=3333),
        conn_state="connected",
        stats=Stats(),
    )

    json_str = telemetry.model_dump_json()
    assert "test-run-123" in json_str
    assert "agent-001" in json_str
    assert "connected" in json_str

