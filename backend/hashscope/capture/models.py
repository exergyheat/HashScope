"""Capture message models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class MessageDirection(str, Enum):
    """Direction of message flow."""
    MINER_TO_POOL = "miner_to_pool"
    POOL_TO_MINER = "pool_to_miner"
    HASHSCOPE_TO_POOL = "hashscope_to_pool"  # Replay for debugging


class CapturedMessage(BaseModel):
    """A captured message with all metadata."""

    id: str
    ts_recv: datetime
    ts_fwd: Optional[datetime] = None
    direction: MessageDirection
    session_id: str
    peer: str
    raw: str  # base64 or hex string
    decoded: Optional[dict[str, Any]] = None
    parse_error: Optional[str] = None
    size_bytes: int

    # Request/Response pairing
    jsonrpc_id: Optional[int | str] = None  # The JSON-RPC id field
    is_request: bool = False  # Has method field
    is_response: bool = False  # Has result or error field
    paired_message_id: Optional[str] = None  # ID of the paired request/response

    # Response data (for paired display)
    response: Optional[dict[str, Any]] = None  # The paired response message
    response_ts_recv: Optional[datetime] = None
    response_raw: Optional[str] = None
    latency_ms: Optional[float] = None  # Response latency in milliseconds

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

