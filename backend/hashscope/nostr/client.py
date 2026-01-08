"""Nostr WebSocket client for HashScope."""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Optional
from collections import deque

import websockets
from coincurve import PrivateKey
import hashlib

from .constants import (
    TAG_KEY_T,
    TAG_KEY_RUN,
    TAG_KEY_TYPE,
    TAG_KEY_POOL,
    TAG_KEY_AGENT,
    TAG_KEY_SCHEMA,
    TAG_HASHSCOPE,
    TAG_SCHEMA,
)

logger = logging.getLogger(__name__)


class NostrClient:
    """Async Nostr WebSocket client."""

    def __init__(
        self,
        relay_url: str,
        private_key_hex: str,
        max_reconnect_delay: int = 30,
        event_queue_size: int = 1000,
    ):
        """
        Initialize Nostr client.

        Args:
            relay_url: WebSocket URL of Nostr relay (e.g., wss://relay.damus.io)
            private_key_hex: Hex-encoded secp256k1 private key
            max_reconnect_delay: Maximum reconnect delay in seconds
            event_queue_size: Maximum size of outbound event queue
        """
        self.relay_url = relay_url
        self.private_key = PrivateKey(bytes.fromhex(private_key_hex))
        self.public_key_hex = self.private_key.public_key.format(compressed=True)[1:].hex()
        self.max_reconnect_delay = max_reconnect_delay
        self.event_queue_size = event_queue_size

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.reconnect_delay = 1
        self.subscription_id_counter = 0
        self.subscriptions: dict[str, dict[str, Any]] = {}
        self.event_handlers: dict[str, Callable] = {}

        # Outbound event queue
        self.event_queue: deque = deque(maxlen=event_queue_size)

        # Background tasks
        self._message_task: Optional[asyncio.Task] = None
        self._publish_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

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
            self.reconnect_delay = 1
            logger.info(f"✅ Connected to Nostr relay: {self.relay_url}")
            logger.info(f"🔑 Public key: {self.public_key_hex[:16]}...{self.public_key_hex[-8:]}")

            # Start background tasks
            self._message_task = asyncio.create_task(self._handle_messages())
            self._publish_task = asyncio.create_task(self._publish_loop())
            logger.info("🚀 Started message handler and publish loop")

            # Resubscribe to any existing subscriptions
            if self.subscriptions:
                logger.info(f"♻️  Resubscribing to {len(self.subscriptions)} existing subscriptions")
                for sub_id, filters in self.subscriptions.items():
                    await self._send_req(sub_id, filters)
                    logger.info(f"📡 Resubscribed: {sub_id} with filters: {filters}")

            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Nostr relay: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from Nostr relay."""
        logger.info("Disconnecting from Nostr relay")
        self.connected = False

        # Cancel background tasks
        if self._message_task:
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass

        if self._publish_task:
            self._publish_task.cancel()
            try:
                await self._publish_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def publish_event(
        self,
        kind: int,
        content: str,
        tags: Optional[list[list[str]]] = None,
    ) -> bool:
        """
        Publish an event to the relay (queued, non-blocking).

        Args:
            kind: Event kind
            content: Event content (JSON string)
            tags: Event tags

        Returns:
            True if queued successfully
        """
        if tags is None:
            tags = []

        event = self._create_event(kind, content, tags)

        # Queue the event (drops oldest if full)
        try:
            self.event_queue.append(event)
            return True
        except Exception as e:
            logger.error(f"Failed to queue event: {e}")
            return False

    async def subscribe(
        self,
        filters: dict[str, Any],
        handler: Callable[[dict], None],
        subscription_id: Optional[str] = None,
    ) -> str:
        """
        Subscribe to events matching filters.

        Args:
            filters: Nostr filters (e.g., {"kinds": [30078], "#t": ["hashscope"]})
            handler: Callback function for received events
            subscription_id: Optional subscription ID (generated if not provided)

        Returns:
            Subscription ID
        """
        if subscription_id is None:
            self.subscription_id_counter += 1
            subscription_id = f"hashscope_{self.subscription_id_counter}"

        self.subscriptions[subscription_id] = filters
        self.event_handlers[subscription_id] = handler

        if self.connected and self.ws:
            await self._send_req(subscription_id, filters)
            logger.info(f"📡 Active subscription created: {subscription_id}")
        else:
            logger.warning(f"⚠️  Subscription {subscription_id} created but not sent (not connected)")

        logger.info(f"📝 Subscription registered: {subscription_id}")
        logger.info(f"🔍 Filters: {json.dumps(filters, indent=2)}")
        return subscription_id

    async def unsubscribe(self, subscription_id: str):
        """Unsubscribe from events."""
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            del self.event_handlers[subscription_id]

            if self.connected and self.ws:
                await self._send_close(subscription_id)

            logger.info(f"Unsubscribed: {subscription_id}")

    async def _handle_messages(self):
        """Handle incoming WebSocket messages."""
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

                            if sub_id in self.event_handlers:
                                handler = self.event_handlers[sub_id]
                                try:
                                    logger.debug(f"🔄 Calling handler for subscription: {sub_id}")
                                    handler(event)
                                    logger.debug(f"✅ Handler completed for: {sub_id}")
                                except Exception as e:
                                    logger.error(f"❌ Error in event handler for {sub_id}: {e}", exc_info=True)
                            else:
                                logger.warning(f"⚠️  No handler found for subscription: {sub_id}")
                    elif msg_type == "OK":
                        # ["OK", event_id, accepted, message]
                        event_id = data[1] if len(data) > 1 else "unknown"
                        event_id_short = event_id[:16] if len(event_id) > 16 else event_id
                        accepted = data[2] if len(data) > 2 else False
                        message = data[3] if len(data) > 3 else ""
                        if accepted:
                            logger.info(f"✅ Event accepted: {event_id_short}...")
                        else:
                            logger.warning(f"❌ Event rejected: {event_id_short}... - {message}")
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
                    logger.error(f"Error handling message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
        finally:
            self.connected = False
            # Trigger reconnect
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _publish_loop(self):
        """Continuously publish queued events."""
        while True:
            try:
                if self.connected and self.ws and self.event_queue:
                    event = self.event_queue.popleft()
                    await self._send_event(event)
                else:
                    await asyncio.sleep(0.1)
            except IndexError:
                # Queue empty
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in publish loop: {e}")
                await asyncio.sleep(1)

    async def _reconnect_loop(self):
        """Reconnect loop with exponential backoff."""
        while not self.connected:
            logger.info(f"Reconnecting in {self.reconnect_delay}s...")
            await asyncio.sleep(self.reconnect_delay)

            success = await self.connect()
            if not success:
                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    def _create_event(self, kind: int, content: str, tags: list[list[str]]) -> dict:
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

    async def _send_event(self, event: dict):
        """Send EVENT message to relay."""
        if self.ws:
            event_id = event.get("id", "unknown")[:16]
            event_kind = event.get("kind", "?")
            logger.info(f"📤 Sending event: id={event_id}... kind={event_kind}")
            message = json.dumps(["EVENT", event])
            await self.ws.send(message)

    async def _send_req(self, subscription_id: str, filters: dict[str, Any]):
        """Send REQ message to relay."""
        if self.ws:
            message = json.dumps(["REQ", subscription_id, filters])
            await self.ws.send(message)

    async def _send_close(self, subscription_id: str):
        """Send CLOSE message to relay."""
        if self.ws:
            message = json.dumps(["CLOSE", subscription_id])
            await self.ws.send(message)

    @staticmethod
    def generate_private_key() -> str:
        """
        Generate a new private key for testing.

        Returns:
            Hex-encoded private key
        """
        key = PrivateKey()
        return key.secret.hex()

