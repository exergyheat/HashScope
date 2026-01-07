"""Main proxy server."""

import asyncio
import logging
from typing import Optional

from ..capture.storage import CaptureStorage
from ..config.settings import Settings
from .session import ProxySession

logger = logging.getLogger(__name__)


class ProxyServer:
    """TCP proxy server that accepts miner connections."""

    def __init__(self, settings: Settings, storage: CaptureStorage):
        """
        Initialize the proxy server.

        Args:
            settings: Application settings
            storage: Capture storage instance
        """
        self.settings = settings
        self.storage = storage
        self.server: Optional[asyncio.Server] = None
        self._sessions: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the proxy server."""
        self.server = await asyncio.start_server(
            self._handle_client,
            self.settings.listen_host,
            self.settings.listen_port,
        )

        addr = self.server.sockets[0].getsockname() if self.server.sockets else ("?", "?")
        logger.info(f"Proxy server listening on {addr[0]}:{addr[1]}")
        logger.info(f"Forwarding to {self.settings.pool_host}:{self.settings.pool_port}")

        async with self.server:
            await self.server.serve_forever()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle a new miner connection.

        Args:
            reader: Stream reader for the connection
            writer: Stream writer for the connection
        """
        peer = writer.get_extra_info('peername')
        logger.info(f"New miner connection from {peer}")

        # Create a new session
        session = ProxySession(
            miner_reader=reader,
            miner_writer=writer,
            pool_host=self.settings.get_pool_hostname(),
            pool_port=self.settings.pool_port,
            storage=self.storage,
        )

        # Start the session in a task
        task = asyncio.create_task(session.start())
        self._sessions.append(task)

        # Clean up completed sessions
        self._sessions = [t for t in self._sessions if not t.done()]

    async def stop(self) -> None:
        """Stop the proxy server."""
        logger.info("Stopping proxy server")

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Wait for all sessions to complete
        if self._sessions:
            await asyncio.gather(*self._sessions, return_exceptions=True)

