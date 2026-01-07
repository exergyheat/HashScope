"""Proxy session handling."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from ..capture.models import CapturedMessage, MessageDirection
from ..capture.storage import CaptureStorage
from ..stratum.parser import StratumParser

logger = logging.getLogger(__name__)


class ProxySession:
    """Represents a single miner connection and its upstream pool connection."""

    def __init__(
        self,
        miner_reader: asyncio.StreamReader,
        miner_writer: asyncio.StreamWriter,
        pool_host: str,
        pool_port: int,
        storage: CaptureStorage,
        session_id: Optional[str] = None,
    ):
        """
        Initialize a proxy session.

        Args:
            miner_reader: Stream reader for miner connection
            miner_writer: Stream writer for miner connection
            pool_host: Upstream pool hostname
            pool_port: Upstream pool port
            storage: Capture storage instance
            session_id: Optional session ID (generated if not provided)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.miner_reader = miner_reader
        self.miner_writer = miner_writer
        self.pool_host = pool_host
        self.pool_port = pool_port
        self.storage = storage
        self.parser = StratumParser()

        # Get peer info
        peer_info = miner_writer.get_extra_info('peername')
        self.miner_peer = f"{peer_info[0]}:{peer_info[1]}" if peer_info else "unknown"

        # Pool connection
        self.pool_reader: Optional[asyncio.StreamReader] = None
        self.pool_writer: Optional[asyncio.StreamWriter] = None
        self.pool_peer: Optional[str] = None

        self._message_counter = 0
        self._running = False

        logger.info(f"Session {self.session_id} created for miner {self.miner_peer}")

    async def start(self) -> None:
        """Start the proxy session."""
        try:
            # Connect to upstream pool
            self.pool_reader, self.pool_writer = await asyncio.open_connection(
                self.pool_host, self.pool_port
            )

            peer_info = self.pool_writer.get_extra_info('peername')
            self.pool_peer = f"{peer_info[0]}:{peer_info[1]}" if peer_info else "unknown"

            logger.info(
                f"Session {self.session_id}: Connected to pool {self.pool_host}:{self.pool_port}"
            )

            self._running = True

            # Start bidirectional relay
            await asyncio.gather(
                self._relay_miner_to_pool(),
                self._relay_pool_to_miner(),
                return_exceptions=True,
            )

        except Exception as e:
            logger.error(f"Session {self.session_id} error: {e}", exc_info=True)
        finally:
            await self._cleanup()

    async def _relay_miner_to_pool(self) -> None:
        """Relay messages from miner to pool."""
        try:
            while self._running:
                # Read until newline (Stratum messages are newline-delimited)
                data = await self.miner_reader.readuntil(b'\n')

                if not data:
                    break

                ts_recv = datetime.utcnow()

                # Parse the message
                parsed = self.parser.parse(data)

                # Capture the message
                await self._capture_message(
                    data=data,
                    direction=MessageDirection.MINER_TO_POOL,
                    ts_recv=ts_recv,
                    parsed=parsed,
                )

                # Forward to pool (byte-for-byte relay)
                if self.pool_writer:
                    self.pool_writer.write(data)
                    await self.pool_writer.drain()

        except asyncio.IncompleteReadError:
            logger.info(f"Session {self.session_id}: Miner disconnected")
        except Exception as e:
            logger.error(f"Session {self.session_id} miner relay error: {e}", exc_info=True)
        finally:
            self._running = False

    async def _relay_pool_to_miner(self) -> None:
        """Relay messages from pool to miner."""
        try:
            while self._running and self.pool_reader:
                # Read until newline (Stratum messages are newline-delimited)
                data = await self.pool_reader.readuntil(b'\n')

                if not data:
                    break

                ts_recv = datetime.utcnow()

                # Parse the message
                parsed = self.parser.parse(data)

                # Capture the message
                await self._capture_message(
                    data=data,
                    direction=MessageDirection.POOL_TO_MINER,
                    ts_recv=ts_recv,
                    parsed=parsed,
                )

                # Forward to miner (byte-for-byte relay)
                self.miner_writer.write(data)
                await self.miner_writer.drain()

        except asyncio.IncompleteReadError:
            logger.info(f"Session {self.session_id}: Pool disconnected")
        except Exception as e:
            logger.error(f"Session {self.session_id} pool relay error: {e}", exc_info=True)
        finally:
            self._running = False

    async def _capture_message(
        self,
        data: bytes,
        direction: MessageDirection,
        ts_recv: datetime,
        parsed,
    ) -> None:
        """Capture a message to storage."""
        self._message_counter += 1
        message_id = f"{self.session_id}-{self._message_counter}"

        # Prepare decoded data
        decoded = None
        parse_error = None
        jsonrpc_id = None
        is_request = False
        is_response = False

        if parsed.success and parsed.message:
            decoded = parsed.message.model_dump(exclude_none=True)

            # Extract JSON-RPC ID
            jsonrpc_id = parsed.message.id

            # Determine if it's a request or response
            # Request: has "method" field
            # Response: has "result" or "error" field
            is_request = parsed.message.method is not None
            is_response = (parsed.message.result is not None or
                          parsed.message.error is not None)

        elif parsed.error:
            parse_error = parsed.error

        # Create captured message
        captured = CapturedMessage(
            id=message_id,
            ts_recv=ts_recv,
            ts_fwd=datetime.utcnow(),
            direction=direction,
            session_id=self.session_id,
            peer=self.miner_peer if direction == MessageDirection.MINER_TO_POOL else self.pool_peer or "unknown",
            raw=parsed.raw_data,
            decoded=decoded,
            parse_error=parse_error,
            size_bytes=len(data),
            jsonrpc_id=jsonrpc_id,
            is_request=is_request,
            is_response=is_response,
        )

        await self.storage.add_message(captured)

    async def _cleanup(self) -> None:
        """Clean up connections."""
        logger.info(f"Session {self.session_id}: Cleaning up")

        self._running = False

        if self.miner_writer:
            try:
                self.miner_writer.close()
                await self.miner_writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing miner connection: {e}")

        if self.pool_writer:
            try:
                self.pool_writer.close()
                await self.pool_writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing pool connection: {e}")

