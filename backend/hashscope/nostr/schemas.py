"""Nostr event schemas for HashScope."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class PoolInfo(BaseModel):
    """Pool connection information."""
    host: str
    port: int


class StratumData(BaseModel):
    """Stratum message data."""
    method: str
    id: Optional[int | str] = None
    params: list[Any] = Field(default_factory=list)


class ShareEvent(BaseModel):
    """Share event published by MITM to agents."""
    schema: str = "hashscope.v1"
    run_id: str
    event_id: str
    seq: int
    ts: str  # ISO-8601 UTC timestamp
    pool: PoolInfo
    stratum: StratumData
    repeat_count: int = 1  # Number of times agent should submit (for load testing)
    context: Optional[dict[str, Any]] = None
    raw: Optional[str] = None  # base64 encoded, optional


class Stats(BaseModel):
    """Agent statistics."""
    share_events_received_total: int = 0
    submits_attempted_total: int = 0
    submits_accepted_total: int = 0
    submits_rejected_total: int = 0
    last_submit_latency_ms: Optional[float] = None
    submits_per_second_1min: Optional[float] = None
    submits_per_second_10sec: Optional[float] = None


class TelemetryEvent(BaseModel):
    """Telemetry event published by agents to MITM."""
    schema: str = "hashscope.v1"
    run_id: str
    agent_id: str
    ts: str  # ISO-8601 UTC timestamp
    pool_target: PoolInfo
    conn_state: str  # "connected" | "reconnecting" | "error"
    stats: Stats
    errors: list[str] = Field(default_factory=list)

