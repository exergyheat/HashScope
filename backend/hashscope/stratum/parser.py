"""Stratum protocol parser."""

import json
import logging
from typing import Optional

from .models import StratumMessage, ParsedMessage

logger = logging.getLogger(__name__)


class StratumParser:
    """Parser for Stratum v1 protocol (JSON-RPC over newline-delimited JSON)."""

    @staticmethod
    def parse(data: bytes) -> ParsedMessage:
        """
        Parse raw bytes into a Stratum message.

        Best-effort parsing - returns parse errors without raising exceptions.

        Args:
            data: Raw bytes from TCP stream

        Returns:
            ParsedMessage with success status and either message or error
        """
        try:
            # Decode as UTF-8
            text = data.decode("utf-8").strip()

            if not text:
                return ParsedMessage(
                    success=False,
                    error="Empty message",
                    raw_data=data.hex()
                )

            # Parse JSON
            json_data = json.loads(text)

            # Validate it looks like JSON-RPC
            if not isinstance(json_data, dict):
                return ParsedMessage(
                    success=False,
                    error="Message is not a JSON object",
                    raw_data=text
                )

            # Parse into StratumMessage model
            message = StratumMessage(**json_data)

            return ParsedMessage(
                success=True,
                message=message,
                raw_data=text
            )

        except UnicodeDecodeError as e:
            return ParsedMessage(
                success=False,
                error=f"UTF-8 decode error: {e}",
                raw_data=data.hex()
            )
        except json.JSONDecodeError as e:
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = data.hex()
            return ParsedMessage(
                success=False,
                error=f"JSON parse error: {e}",
                raw_data=text
            )
        except Exception as e:
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = data.hex()
            return ParsedMessage(
                success=False,
                error=f"Parse error: {e}",
                raw_data=text
            )

    @staticmethod
    def encode(message: StratumMessage) -> bytes:
        """
        Encode a Stratum message to bytes.

        Args:
            message: StratumMessage to encode

        Returns:
            Newline-terminated JSON bytes
        """
        json_str = json.dumps(message.model_dump(exclude_none=True), separators=(',', ':'))
        return (json_str + "\n").encode("utf-8")

