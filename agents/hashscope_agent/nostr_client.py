"""Nostr client for agent - subscribes to ShareEvents and publishes telemetry."""

import asyncio
import json
import logging
import hashlib
import time
from typing import Optional, Callable
from datetime import datetime

import websockets
from coincurve import PrivateKey

logger = logging.getLogger(__name__)


class AgentNostrClient:
    """Simplified Nostr client for agent operations."""

    def __init__(
        self,
        relay_url: str,
        private_key_hex: str,
        run_id: str,
        kind_share: int = 30078,
        kind_telemetry: int = 30079,
    ):
        """
        Initialize agent Nostr client.

        Args:
            relay_url: WebSocket URL of Nostr relay
            private_key_hex: Hex-encoded secp256k1 private key
            run_id: Run ID to filter events
            kind_share: Share event kind
            kind_telemetry: Telemetry event kind
        """
        self.relay_url = relay_url
        self.run_id = run_id
        self.kind_share = kind_share
        self.kind_telemetry = kind_telemetry

        self.private_key = PrivateKey(bytes.fromhex(private_key_hex))
        self.public_key_hex = self.private_key.public_key.format(compressed=True)[1:].hex()

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.share_event_handler: Optional[Callable] = None

        self._read_task: Optional[asyncio.Task] = None
        self._last_seen_ts: Optional[int] = None

    async def connect(self) -> bool:
        """
        Connect to Nostr relay.

        Returns:
            True if connected successfully
        """
        try:
            logger.info(f"🔌 Connecting to Nostr relay: {self.relay_url}")
            self.ws = await websockets.connect(self.relay_url)
            self.connected = True
            logger.info(f"✅ Connected to Nostr relay: {self.relay_url}")
            logger.info(f"🔑 Public key: {self.public_key_hex[:16]}...{self.public_key_hex[-8:]}")

            # Start reading messages
            self._read_task = asyncio.create_task(self._read_loop())
            logger.info("🚀 Started message read loop")

            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Nostr relay: {e}", exc_info=True)
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from Nostr relay."""
        logger.info("Disconnecting from Nostr relay")
        self.connected = False

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            await self.ws.close()
            self.ws = None

    async def subscribe_to_share_events(
        self,
        handler: Callable[[dict], None],
        since: Optional[int] = None,
    ):
        """
        Subscribe to ShareEvents for this run_id.

        Args:
            handler: Callback function for share events
            since: Unix timestamp to start from (optional)
        """
        self.share_event_handler = handler

        if since is None:
            since = int(time.time()) - 60  # Start from 1 minute ago

        self._last_seen_ts = since

        # Use simpler filters for better relay compatibility
        # We'll filter by run_id in the handler
        filters = {
            "kinds": [self.kind_share],
            "since": since,
        }

        subscription_id = f"shares_{self.run_id}"
        req_message = json.dumps(["REQ", subscription_id, filters])

        if self.ws:
            await self.ws.send(req_message)
            logger.info(f"📡 Subscribed to ShareEvents (kind {self.kind_share})")
            logger.info(f"🔍 Filters: {json.dumps(filters, indent=2)}")
            logger.info(f"📝 Subscription ID: {subscription_id}")

    async def publish_telemetry(self, telemetry_content: str) -> bool:
        """
        Publish a telemetry event.

        Args:
            telemetry_content: JSON string of telemetry data

        Returns:
            True if published successfully
        """
        try:
            tags = [
                ["t", "hashscope"],
                ["run", self.run_id],
                ["type", "telemetry"],
                ["schema", "hashscope.v1"],
            ]

            event = self._create_event(self.kind_telemetry, telemetry_content, tags)

            if self.ws:
                event_id = event.get("id", "unknown")[:16]
                logger.info(f"📤 Publishing telemetry event: id={event_id}... kind={self.kind_telemetry}")
                message = json.dumps(["EVENT", event])
                await self.ws.send(message)
                return True

            logger.warning("⚠️  Cannot publish telemetry: not connected")
            return False

        except Exception as e:
            logger.error(f"❌ Failed to publish telemetry: {e}", exc_info=True)
            return False

    def _create_event(self, kind: int, content: str, tags: list) -> dict:
        """
        Create and sign a Nostr event.

        Args:
            kind: Event kind
            content: Event content
            tags: Event tags

        Returns:
            Signed event dict
        """
        created_at = int(time.time())

        # Build event for signing
        event_for_signing = [
            0,  # Reserved for future use
            self.public_key_hex,
            created_at,
            kind,
            tags,
            content,
        ]

        # Serialize and hash
        serialized = json.dumps(event_for_signing, separators=(',', ':'), ensure_ascii=False)
        event_hash = hashlib.sha256(serialized.encode('utf-8')).digest()

        # Sign (schnorr signature returns 64 bytes)
        signature = self.private_key.sign_schnorr(event_hash)

        event = {
            "id": event_hash.hex(),
            "pubkey": self.public_key_hex,
            "created_at": created_at,
            "kind": kind,
            "tags": tags,
            "content": content,
            "sig": signature.hex(),
        }

        return event

    async def _read_loop(self):
        """Read and process messages from relay."""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    msg_type = data[0] if isinstance(data, list) and len(data) > 0 else None

                    if msg_type == "EVENT":
                        # ["EVENT", subscription_id, event]
                        if len(data) >= 3:
                            sub_id = data[1]
                            event = data[2]
                            event_id = event.get("id", "unknown")[:16]
                            event_kind = event.get("kind", "?")
                            event_pubkey = event.get("pubkey", "")[:16]

                            logger.info(f"📨 Received EVENT: id={event_id}... kind={event_kind} pubkey={event_pubkey}... sub={sub_id}")
                            await self._handle_event(event)

                    elif msg_type == "OK":
                        # ["OK", event_id, accepted, message]
                        event_id = data[1] if len(data) > 1 else "unknown"
                        event_id_short = event_id[:16] if len(event_id) > 16 else event_id
                        accepted = data[2] if len(data) > 2 else False
                        if accepted:
                            logger.info(f"✅ Event accepted: {event_id_short}...")
                        else:
                            message_text = data[3] if len(data) > 3 else ""
                            logger.warning(f"❌ Event rejected: {event_id_short}... - {message_text}")

                    elif msg_type == "NOTICE":
                        # ["NOTICE", message]
                        notice = data[1] if len(data) > 1 else ""
                        logger.info(f"📢 Relay notice: {notice}")

                    elif msg_type == "EOSE":
                        # ["EOSE", subscription_id] - End Of Stored Events
                        sub_id = data[1] if len(data) > 1 else "unknown"
                        logger.info(f"🏁 End of stored events for subscription: {sub_id}")

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from relay: {message}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in read loop: {e}", exc_info=True)
        finally:
            self.connected = False

    async def _handle_event(self, event: dict):
        """
        Handle incoming Nostr event.

        Args:
            event: Nostr event dict
        """
        try:
            # Update last seen timestamp
            created_at = event.get("created_at", 0)
            if created_at > (self._last_seen_ts or 0):
                self._last_seen_ts = created_at

            # Check if it's a ShareEvent
            if event.get("kind") == self.kind_share:
                logger.info(f"🔄 Processing ShareEvent...")
                content = json.loads(event.get("content", "{}"))

                # Filter by run_id (since we can't use tag filters on some relays)
                event_run_id = content.get("run_id")
                if event_run_id != self.run_id:
                    logger.debug(f"⏭️  Ignoring ShareEvent from different run_id: {event_run_id}")
                    return

                logger.info(f"✅ ShareEvent for our run_id: {self.run_id}")
                # Call handler if registered
                if self.share_event_handler:
                    logger.info(f"📞 Calling share event handler")
                    self.share_event_handler(content)
                else:
                    logger.warning("⚠️  No share event handler registered")

        except Exception as e:
            logger.error(f"❌ Error handling event: {e}", exc_info=True)

