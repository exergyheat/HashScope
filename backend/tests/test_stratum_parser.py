"""Tests for Stratum parser."""

import pytest
from hashscope.stratum.parser import StratumParser
from hashscope.stratum.models import StratumMessage


class TestStratumParser:
    """Test the Stratum protocol parser."""

    def test_parse_subscribe_request(self):
        """Test parsing a mining.subscribe request."""
        data = b'{"id": 1, "method": "mining.subscribe", "params": ["cpuminer/2.5.0"]}\n'

        result = StratumParser.parse(data)

        assert result.success is True
        assert result.message is not None
        assert result.message.id == 1
        assert result.message.method == "mining.subscribe"
        assert result.message.params == ["cpuminer/2.5.0"]
        assert result.error is None

    def test_parse_authorize_request(self):
        """Test parsing a mining.authorize request."""
        data = b'{"id": 2, "method": "mining.authorize", "params": ["username", "password"]}\n'

        result = StratumParser.parse(data)

        assert result.success is True
        assert result.message is not None
        assert result.message.id == 2
        assert result.message.method == "mining.authorize"
        assert result.message.params == ["username", "password"]

    def test_parse_response_with_result(self):
        """Test parsing a response with result."""
        data = b'{"id": 1, "result": [[["mining.notify", "1234"]], "deadbeef", 4], "error": null}\n'

        result = StratumParser.parse(data)

        assert result.success is True
        assert result.message is not None
        assert result.message.id == 1
        assert result.message.result is not None
        assert result.message.error is None

    def test_parse_notification(self):
        """Test parsing a notification (no id)."""
        data = b'{"method": "mining.notify", "params": ["job1", "prevhash", "coinbase1", "coinbase2", [], "version", "nbits", "ntime", true]}\n'

        result = StratumParser.parse(data)

        assert result.success is True
        assert result.message is not None
        assert result.message.id is None
        assert result.message.method == "mining.notify"

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        data = b'{"invalid json\n'

        result = StratumParser.parse(data)

        assert result.success is False
        assert result.error is not None
        assert "JSON parse error" in result.error

    def test_parse_empty_message(self):
        """Test parsing empty message."""
        data = b'\n'

        result = StratumParser.parse(data)

        assert result.success is False
        assert result.error == "Empty message"

    def test_parse_non_utf8(self):
        """Test parsing non-UTF-8 data."""
        data = b'\xff\xfe invalid utf-8\n'

        result = StratumParser.parse(data)

        assert result.success is False
        assert "UTF-8 decode error" in result.error

    def test_encode_message(self):
        """Test encoding a Stratum message."""
        message = StratumMessage(
            id=1,
            method="mining.subscribe",
            params=["cpuminer/2.5.0"]
        )

        encoded = StratumParser.encode(message)

        assert encoded.endswith(b'\n')
        assert b'"id":1' in encoded
        assert b'"method":"mining.subscribe"' in encoded
        assert b'"params":["cpuminer/2.5.0"]' in encoded

