"""Tests for Nostr constants."""

from hashscope.nostr.constants import (
    KIND_SHARE_EVENT,
    KIND_TELEMETRY_EVENT,
    TAG_HASHSCOPE,
    TAG_SCHEMA,
    TAG_KEY_T,
    TAG_KEY_RUN,
    TAG_KEY_TYPE,
    TAG_TYPE_SHARE,
    TAG_TYPE_TELEMETRY,
)


def test_event_kinds():
    """Test event kind constants."""
    assert KIND_SHARE_EVENT == 30078
    assert KIND_TELEMETRY_EVENT == 30079


def test_tag_constants():
    """Test tag constants."""
    assert TAG_HASHSCOPE == "hashscope"
    assert TAG_SCHEMA == "hashscope.v1"


def test_tag_keys():
    """Test tag key constants."""
    assert TAG_KEY_T == "t"
    assert TAG_KEY_RUN == "run"
    assert TAG_KEY_TYPE == "type"


def test_tag_type_values():
    """Test tag type values."""
    assert TAG_TYPE_SHARE == "share"
    assert TAG_TYPE_TELEMETRY == "telemetry"

