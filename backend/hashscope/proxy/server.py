"""Main proxy server."""

import asyncio
import json
import logging
from typing import Optional

from ..capture.storage import CaptureStorage
from ..capture.telemetry import TelemetryStorage
from ..config.settings import Settings
from ..nostr.client import NostrClient
from ..nostr.schemas import TelemetryEvent
from ..nostr.constants import (
    KIND_TELEMETRY_EVENT,
    TAG_KEY_T,
    TAG_KEY_RUN,
    TAG_KEY_TYPE,
    TAG_HASHSCOPE,
    TAG_TYPE_TELEMETRY,
)
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
        self._active_sessions: dict[str, ProxySession] = {}  # Track active sessions by session_id

        # Nostr client (Iteration 2)
        self.nostr_client: Optional[NostrClient] = None
        self._nostr_connect_task: Optional[asyncio.Task] = None

        # Telemetry storage (Iteration 2)
        self.telemetry_storage = TelemetryStorage()

    async def start(self) -> None:
        """Start the proxy server."""
        # Initialize Nostr client if enabled (Iteration 2)
        if self.settings.nostr_enabled and self.settings.nostr_relay_url:
            logger.info("Nostr enabled, initializing client...")
            try:
                # Generate private key if not provided
                nostr_sk = self.settings.nostr_sk
                if not nostr_sk:
                    nostr_sk = NostrClient.generate_private_key()
                    logger.info(f"Generated new Nostr private key: {nostr_sk}")
                    logger.info("Save this key to reuse: export NOSTR_SK={nostr_sk}")

                self.nostr_client = NostrClient(
                    relay_url=self.settings.nostr_relay_url,
                    private_key_hex=nostr_sk,
                )
                await self.nostr_client.connect()

                # Subscribe to telemetry events
                # Note: Using only 'kinds' filter for better relay compatibility
                # We'll filter by run_id in the handler
                filters = {
                    "kinds": [self.settings.nostr_kind_telemetry],
                }

                await self.nostr_client.subscribe(
                    filters=filters,
                    handler=self._handle_telemetry_event,
                    subscription_id=f"telemetry_{self.settings.run_id}",
                )

                logger.info(f"Nostr client connected to {self.settings.nostr_relay_url}")
                logger.info(f"Subscribed to telemetry events for run_id={self.settings.run_id}")
            except Exception as e:
                logger.error(f"Failed to initialize Nostr client: {e}", exc_info=True)
                self.nostr_client = None

        self.server = await asyncio.start_server(
            self._handle_client,
            self.settings.listen_host,
            self.settings.listen_port,
        )

        addr = self.server.sockets[0].getsockname() if self.server.sockets else ("?", "?")
        logger.info(f"Proxy server listening on {addr[0]}:{addr[1]}")
        logger.info(f"Forwarding to {self.settings.pool_host}:{self.settings.pool_port}")
        if self.settings.hashsplit_enabled:
            logger.info(
                "Hashsplit ENABLED (share-band): fee_pct=%s customer_user=%s fee_user=%s",
                self.settings.hashsplit_fee_percent,
                self.settings.hashsplit_customer_user or "(from miner authorize)",
                self.settings.hashsplit_fee_user or "(derive from customer)",
            )

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
            nostr_client=self.nostr_client,
            settings=self.settings,
        )

        # Store active session
        self._active_sessions[session.session_id] = session

        # Start the session in a task with cleanup
        async def run_session():
            try:
                await session.start()
            finally:
                # Clean up when session ends
                self._active_sessions.pop(session.session_id, None)

        task = asyncio.create_task(run_session())
        self._sessions.append(task)

        # Clean up completed sessions
        self._sessions = [t for t in self._sessions if not t.done()]

    def get_active_session(self, session_id: str) -> Optional[ProxySession]:
        """Get an active session by ID."""
        return self._active_sessions.get(session_id)

    def _handle_telemetry_event(self, event: dict) -> None:
        """
        Handle incoming telemetry event from Nostr.

        Args:
            event: Nostr event dict
        """
        try:
            logger.info(f"📊 Processing telemetry event from pubkey: {event.get('pubkey', '')[:16]}...")

            # Parse content as TelemetryEvent
            content = json.loads(event.get("content", "{}"))
            telemetry = TelemetryEvent(**content)

            # Filter by run_id (since we can't use tag filters on some relays)
            if telemetry.run_id != self.settings.run_id:
                logger.debug(f"⏭️  Ignoring telemetry from different run_id: {telemetry.run_id}")
                return

            # Store telemetry (schedule async task)
            asyncio.create_task(self.telemetry_storage.add_telemetry(telemetry))

            # Build rate info if available
            rate_info = ""
            if telemetry.stats.submits_per_second_1min is not None:
                rate_info = f", rate_1m={telemetry.stats.submits_per_second_1min:.2f}/s"
            if telemetry.stats.submits_per_second_10sec is not None:
                rate_info += f", rate_10s={telemetry.stats.submits_per_second_10sec:.2f}/s"

            logger.info(
                f"✅ Telemetry received from agent {telemetry.agent_id}: "
                f"state={telemetry.conn_state}, "
                f"pool_submits={telemetry.stats.submits_attempted_total}, "
                f"accepted={telemetry.stats.submits_accepted_total}, "
                f"rejected={telemetry.stats.submits_rejected_total}"
                f"{rate_info}"
            )

        except Exception as e:
            logger.error(f"❌ Error handling telemetry event: {e}", exc_info=True)

    async def stop(self) -> None:
        """Stop the proxy server."""
        logger.info("Stopping proxy server")

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Wait for all sessions to complete
        if self._sessions:
            await asyncio.gather(*self._sessions, return_exceptions=True)

        # Disconnect Nostr client
        if self.nostr_client:
            await self.nostr_client.disconnect()

