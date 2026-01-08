"""Nostr protocol integration for HashScope."""

from .constants import KIND_SHARE_EVENT, KIND_TELEMETRY_EVENT, TAG_HASHSCOPE, TAG_SCHEMA
from .schemas import ShareEvent, TelemetryEvent, PoolInfo, StratumData, Stats
from .client import NostrClient

__all__ = [
    "KIND_SHARE_EVENT",
    "KIND_TELEMETRY_EVENT",
    "TAG_HASHSCOPE",
    "TAG_SCHEMA",
    "ShareEvent",
    "TelemetryEvent",
    "PoolInfo",
    "StratumData",
    "Stats",
    "NostrClient",
]

