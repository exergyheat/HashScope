"""Stratum message models."""

from typing import Any, Optional
from pydantic import BaseModel


class StratumMessage(BaseModel):
    """Stratum v1 JSON-RPC message."""

    id: Optional[int | str] = None
    method: Optional[str] = None
    params: Optional[list[Any] | dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Any] = None


class ParsedMessage(BaseModel):
    """Result of parsing a raw message."""

    success: bool
    message: Optional[StratumMessage] = None
    error: Optional[str] = None
    raw_data: str

