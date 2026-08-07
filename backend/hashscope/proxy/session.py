"""Proxy session handling."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from ..capture.models import CapturedMessage, MessageDirection
from ..capture.storage import CaptureStorage
from ..stratum.parser import StratumParser
from ..nostr.client import NostrClient
from ..nostr.schemas import ShareEvent, PoolInfo, StratumData
from ..nostr.constants import (
    KIND_SHARE_EVENT,
    TAG_KEY_T,
    TAG_KEY_RUN,
    TAG_KEY_TYPE,
    TAG_KEY_SCHEMA,
    TAG_HASHSCOPE,
    TAG_SCHEMA,
    TAG_TYPE_SHARE,
)
from ..config.settings import Settings
from .hashsplit import (
    build_set_difficulty,
    build_set_extranonce,
    denamespace_job_id,
    derive_fee_user,
    extract_notify_job_id,
    extract_submit_job_id,
    extract_subscribe_extranonce,
    rewrite_authorize_user,
    rewrite_notify_job_id,
    rewrite_submit_for_leg,
)

logger = logging.getLogger(__name__)

# Hashsplit leg labels
LEG_CUSTOMER = "customer"
LEG_FEE = "fee"


class ProxySession:
    """Represents a single miner connection and its upstream pool connection(s)."""

    def __init__(
        self,
        miner_reader: asyncio.StreamReader,
        miner_writer: asyncio.StreamWriter,
        pool_host: str,
        pool_port: int,
        storage: CaptureStorage,
        session_id: Optional[str] = None,
        nostr_client: Optional[NostrClient] = None,
        settings: Optional[Settings] = None,
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
            nostr_client: Optional Nostr client for publishing ShareEvents
            settings: Optional settings instance
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.miner_reader = miner_reader
        self.miner_writer = miner_writer
        self.pool_host = pool_host
        self.pool_port = pool_port
        self.storage = storage
        self.parser = StratumParser()
        self.nostr_client = nostr_client
        self.settings = settings

        # Get peer info
        peer_info = miner_writer.get_extra_info('peername')
        self.miner_peer = f"{peer_info[0]}:{peer_info[1]}" if peer_info else "unknown"

        # Pool connection (customer / single-pool path)
        self.pool_reader: Optional[asyncio.StreamReader] = None
        self.pool_writer: Optional[asyncio.StreamWriter] = None
        self.pool_peer: Optional[str] = None

        # Fee leg (hashsplit)
        self.fee_reader: Optional[asyncio.StreamReader] = None
        self.fee_writer: Optional[asyncio.StreamWriter] = None
        self.fee_peer: Optional[str] = None
        self.fee_pool_host: Optional[str] = None
        self.fee_pool_port: Optional[int] = None

        self.hashsplit_enabled = bool(settings and settings.hashsplit_enabled)
        self.active_leg: str = LEG_CUSTOMER
        self._job_leg: dict[str, str] = {}
        self._seen_response_ids: set[Any] = set()
        self._extranonce: dict[str, tuple[Optional[str], Optional[int]]] = {
            LEG_CUSTOMER: (None, None),
            LEG_FEE: (None, None),
        }
        self._difficulty: dict[str, Optional[float]] = {
            LEG_CUSTOMER: None,
            LEG_FEE: None,
        }
        self._customer_user: Optional[str] = None
        self._fee_user: Optional[str] = None
        self._switch_task: Optional[asyncio.Task] = None

        self._message_counter = 0
        self._running = False

        # ShareEvent sequence counter (Iteration 2)
        self._share_event_seq = 0

        # Replay response tracking
        self._replay_futures: dict[int | str, asyncio.Future] = {}

        logger.info(
            f"Session {self.session_id} created for miner {self.miner_peer}"
            f"{' [hashsplit ON]' if self.hashsplit_enabled else ''}"
        )
    async def replay_message(self, message_data: str) -> tuple[Optional[dict], float]:
        """
        Replay a message through the existing pool connection for debugging.

        The message is sent to the pool, and the response is intercepted by
        the relay task instead of being forwarded to the miner.

        Args:
            message_data: The JSON message to send (should be a complete line)

        Returns:
            Tuple of (response_dict, latency_ms)
        """
        if not self.pool_writer or not self.pool_reader:
            raise RuntimeError("Pool connection not established")

        import time

        # Parse message to get the ID
        try:
            message_dict = json.loads(message_data)
            message_id = message_dict.get("id")
            if message_id is None:
                raise ValueError("Message must have an 'id' field")
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid message format: {e}")

        # Create a future for this replay
        future = asyncio.Future()
        self._replay_futures[message_id] = future

        try:
            # Ensure message ends with newline
            if not message_data.endswith("\n"):
                message_data += "\n"

            # Send the message
            start_time = time.time()
            self.pool_writer.write(message_data.encode())
            await self.pool_writer.drain()

            # Wait for the response (intercepted by relay task)
            response_dict = await asyncio.wait_for(future, timeout=10.0)

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            return response_dict, latency_ms

        except asyncio.TimeoutError:
            # Clean up the future on timeout
            self._replay_futures.pop(message_id, None)
            raise
        except Exception:
            # Clean up the future on error
            self._replay_futures.pop(message_id, None)
            raise

    async def capture_replay_message(
        self,
        request_data: str,
        response_dict: dict,
        latency_ms: float,
        replay_index: int = 0
    ) -> str:
        """
        Capture a replay message for the message list.

        This creates a message with direction HASHSCOPE_TO_POOL showing
        the replayed request and its response.

        Args:
            request_data: The JSON request string that was replayed
            response_dict: The response from the pool
            latency_ms: The response latency
            replay_index: Index for auto-replay sequences (default 0)

        Returns:
            The message ID
        """
        from datetime import datetime

        ts_recv = datetime.utcnow()
        ts_fwd = datetime.utcnow()

        # Parse the request
        try:
            request_dict = json.loads(request_data)
        except json.JSONDecodeError:
            request_dict = {}

        # Create a unique message ID for the replay
        # Use UUID to ensure absolute uniqueness, especially for auto-replay sequences
        unique_id = str(uuid.uuid4())
        message_id = f"{self.session_id}-replay-{request_dict.get('id', 'unknown')}-{unique_id}"

        # Encode raw data
        import base64
        raw_request = base64.b64encode(request_data.encode()).decode()

        captured_message = CapturedMessage(
            id=message_id,
            ts_recv=ts_recv,
            ts_fwd=ts_fwd,
            direction=MessageDirection.HASHSCOPE_TO_POOL,
            session_id=self.session_id,
            peer=f"hashscope→{self.pool_peer or 'pool'}",
            raw=raw_request,
            decoded=request_dict,
            parse_error=None,
            size_bytes=len(request_data.encode()),
            jsonrpc_id=request_dict.get('id'),
            is_request=True,
            is_response=False,
            response=response_dict,
            response_ts_recv=ts_fwd,
            latency_ms=latency_ms,
        )

        # Store in capture storage WITH WebSocket notification
        # Since we're using UUIDs for message IDs, duplicates won't happen
        # WebSocket broadcast allows UI to see auto-replays in real-time
        logger.info(f"Storing replay message {message_id} (notify=True)")
        await self.storage.add_message(captured_message, notify=True)
        logger.info(f"Replay message {message_id} stored successfully")

        return message_id

    async def start(self) -> None:
        """Start the proxy session."""
        # Register session with storage (before pool connection attempt)
        await self.storage.register_session(
            session_id=self.session_id,
            peer=self.miner_peer,
            pool_host=self.pool_host,
            pool_port=self.pool_port,
        )
        if self.hashsplit_enabled:
            await self.storage.update_session_fields(
                self.session_id,
                hashsplit_enabled=True,
                hashsplit_mode="dual_upstream_timeslice",
                hashsplit_leg=self.active_leg,
            )

        try:
            # Connect to customer / primary upstream
            self.pool_reader, self.pool_writer = await asyncio.open_connection(
                self.pool_host, self.pool_port
            )

            peer_info = self.pool_writer.get_extra_info('peername')
            self.pool_peer = f"{peer_info[0]}:{peer_info[1]}" if peer_info else "unknown"

            # Update pool connection status
            await self.storage.update_session_pool_status(
                session_id=self.session_id,
                connected=True,
                pool_peer=self.pool_peer,
            )

            logger.info(
                f"Session {self.session_id}: Connected to pool {self.pool_host}:{self.pool_port}"
            )

            if self.hashsplit_enabled and self.settings:
                self.fee_pool_host = self.settings.get_fee_pool_hostname()
                self.fee_pool_port = self.settings.get_fee_pool_port()
                self.fee_reader, self.fee_writer = await asyncio.open_connection(
                    self.fee_pool_host, self.fee_pool_port
                )
                fee_peer = self.fee_writer.get_extra_info('peername')
                self.fee_peer = f"{fee_peer[0]}:{fee_peer[1]}" if fee_peer else "unknown"
                # Start on customer leg; switcher will alternate for fee_percent
                self.active_leg = LEG_CUSTOMER
                logger.info(
                    f"Session {self.session_id}: Hashsplit fee leg connected "
                    f"{self.fee_pool_host}:{self.fee_pool_port} peer={self.fee_peer} "
                    f"fee_pct={self.settings.hashsplit_fee_percent} "
                    f"switch_s={self.settings.hashsplit_switch_seconds}"
                )

            self._running = True

            tasks = [
                self._relay_miner_to_pool(),
                self._relay_pool_to_miner(LEG_CUSTOMER),
            ]
            if self.hashsplit_enabled:
                tasks.append(self._relay_pool_to_miner(LEG_FEE))
                tasks.append(self._hashsplit_switch_loop())

            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Session {self.session_id} error: {e}", exc_info=True)
            # Update pool connection status to failed
            await self.storage.update_session_pool_status(
                session_id=self.session_id,
                connected=False,
            )
        finally:
            await self._cleanup()

    def _writer_for_leg(self, leg: str) -> Optional[asyncio.StreamWriter]:
        if leg == LEG_FEE:
            return self.fee_writer
        return self.pool_writer

    def _reader_for_leg(self, leg: str) -> Optional[asyncio.StreamReader]:
        if leg == LEG_FEE:
            return self.fee_reader
        return self.pool_reader

    def _peer_for_leg(self, leg: str) -> str:
        if leg == LEG_FEE:
            return self.fee_peer or "fee-pool"
        return self.pool_peer or "pool"

    async def _write_to_leg(self, leg: str, data: bytes) -> None:
        writer = self._writer_for_leg(leg)
        if writer:
            writer.write(data)
            await writer.drain()

    async def _relay_miner_to_pool(self) -> None:
        """Relay messages from miner to pool (single or dual-upstream hashsplit)."""
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

                # Publish ShareEvent to Nostr if enabled (Iteration 2)
                if parsed.success and parsed.message:
                    asyncio.create_task(
                        self._maybe_publish_share_event(parsed.message, ts_recv)
                    )

                if self.hashsplit_enabled:
                    await self._hashsplit_forward_miner_line(data, parsed)
                else:
                    # Forward to pool (byte-for-byte relay)
                    if self.pool_writer:
                        self.pool_writer.write(data)
                        await self.pool_writer.drain()

                # Auto-replay if enabled (load testing) — single-pool only
                if (
                    not self.hashsplit_enabled
                    and parsed.success
                    and parsed.message
                    and parsed.message.method == "mining.submit"
                ):
                    asyncio.create_task(
                        self._maybe_auto_replay(parsed.message, data.decode())
                    )

        except asyncio.IncompleteReadError:
            logger.info(f"Session {self.session_id}: Miner disconnected")
        except Exception as e:
            logger.error(f"Session {self.session_id} miner relay error: {e}", exc_info=True)
        finally:
            self._running = False

    async def _hashsplit_forward_miner_line(self, data: bytes, parsed) -> None:
        """Route a miner→pool line across dual upstreams."""
        msg: Optional[dict] = None
        if parsed.success and parsed.message:
            if hasattr(parsed.message, "model_dump"):
                msg = parsed.message.model_dump(exclude_none=True)
            else:
                try:
                    msg = json.loads(data.decode("utf-8", errors="replace").strip())
                except json.JSONDecodeError:
                    msg = None
        else:
            try:
                msg = json.loads(data.decode("utf-8", errors="replace").strip())
            except json.JSONDecodeError:
                msg = None

        method = (msg or {}).get("method")

        # Handshake-ish: fan out to both legs
        if method in ("mining.subscribe", "mining.configure", "mining.extranonce.subscribe"):
            await self._write_to_leg(LEG_CUSTOMER, data)
            await self._write_to_leg(LEG_FEE, data)
            return

        if method == "mining.authorize":
            params = (msg or {}).get("params") or []
            miner_user = str(params[0]) if isinstance(params, list) and params else "worker"
            # Upstream workers may both be rewritten (lab: proxy_test_A / proxy_test_B)
            if self.settings and self.settings.hashsplit_customer_user:
                self._customer_user = self.settings.hashsplit_customer_user
            else:
                self._customer_user = miner_user
            explicit = self.settings.hashsplit_fee_user if self.settings else None
            self._fee_user = derive_fee_user(miner_user, explicit)
            cust_pass = (
                self.settings.hashsplit_customer_password if self.settings else "x"
            )
            fee_pass = self.settings.hashsplit_fee_password if self.settings else "x"
            customer_line = rewrite_authorize_user(data, self._customer_user, cust_pass)
            fee_line = rewrite_authorize_user(data, self._fee_user, fee_pass)
            await self._write_to_leg(LEG_CUSTOMER, customer_line)
            await self._write_to_leg(LEG_FEE, fee_line)
            await self.storage.update_session_fields(
                self.session_id,
                miner_worker=miner_user,
                customer_worker=self._customer_user,
                fee_worker=self._fee_user,
                upstream_worker=(
                    self._fee_user if self.active_leg == LEG_FEE else self._customer_user
                ),
                hashsplit_leg=self.active_leg,
            )
            logger.info(
                f"Session {self.session_id}: hashsplit authorize "
                f"miner={miner_user!r} → customer={self._customer_user!r} fee={self._fee_user!r}"
            )
            return

        if method == "mining.submit":
            job_id = extract_submit_job_id(msg or {})
            leg_from_job, _raw = denamespace_job_id(job_id) if job_id else (None, "")
            leg = leg_from_job or (
                self._job_leg.get(job_id, self.active_leg) if job_id else self.active_leg
            )
            out = rewrite_submit_for_leg(
                data, leg, self._fee_user, customer_user=self._customer_user
            )
            await self._write_to_leg(leg, out)
            logger.info(
                f"Session {self.session_id}: submit namespaced_job={job_id} → leg={leg}"
            )
            return

        # Default: only active leg (e.g. mining.suggest_difficulty)
        await self._write_to_leg(self.active_leg, data)

    async def _relay_pool_to_miner(self, leg: str = LEG_CUSTOMER) -> None:
        """Relay messages from one pool leg to miner."""
        reader = self._reader_for_leg(leg)
        try:
            while self._running and reader:
                # Read until newline (Stratum messages are newline-delimited)
                data = await reader.readuntil(b'\n')

                if not data:
                    break

                ts_recv = datetime.utcnow()

                # Parse the message
                parsed = self.parser.parse(data)

                # Check if this is a response to a replay request
                is_replay_response = False
                if parsed.success and parsed.message:
                    message_id = parsed.message.id
                    if message_id is not None and message_id in self._replay_futures:
                        # This is a replay response - complete the future
                        future = self._replay_futures.pop(message_id)
                        if not future.done():
                            # Serialize the StratumMessage to dict
                            if hasattr(parsed.message, 'model_dump'):
                                result = parsed.message.model_dump()
                            elif hasattr(parsed.message, 'dict'):
                                result = parsed.message.dict()
                            else:
                                result = vars(parsed.message)
                            future.set_result(result)
                        is_replay_response = True
                        logger.info(f"Session {self.session_id}: Intercepted replay response for message ID {message_id} (not forwarding to miner)")

                # Capture the message ONLY if not a replay response
                # Replay messages are captured separately with HASHSCOPE_TO_POOL direction
                if not is_replay_response:
                    # Temporarily set pool_peer for capture attribution
                    saved_peer = self.pool_peer
                    if leg == LEG_FEE:
                        self.pool_peer = self.fee_peer
                    await self._capture_message(
                        data=data,
                        direction=MessageDirection.POOL_TO_MINER,
                        ts_recv=ts_recv,
                        parsed=parsed,
                    )
                    self.pool_peer = saved_peer

                if is_replay_response:
                    continue

                if self.hashsplit_enabled:
                    await self._hashsplit_handle_pool_line(leg, data, parsed)
                else:
                    self.miner_writer.write(data)
                    await self.miner_writer.drain()

        except asyncio.IncompleteReadError:
            logger.info(f"Session {self.session_id}: Pool disconnected ({leg})")
        except Exception as e:
            logger.error(f"Session {self.session_id} pool relay error ({leg}): {e}", exc_info=True)
        finally:
            self._running = False

    async def _hashsplit_handle_pool_line(self, leg: str, data: bytes, parsed) -> None:
        """Decide whether to forward a pool line to the miner under hashsplit."""
        msg: Optional[dict] = None
        try:
            if parsed.success and parsed.message and hasattr(parsed.message, "model_dump"):
                msg = parsed.message.model_dump(exclude_none=True)
            else:
                msg = json.loads(data.decode("utf-8", errors="replace").strip())
        except json.JSONDecodeError:
            msg = None

        if not msg:
            if leg == self.active_leg:
                self.miner_writer.write(data)
                await self.miner_writer.drain()
            return

        method = msg.get("method")

        # Track difficulty per leg
        if method == "mining.set_difficulty":
            params = msg.get("params") or []
            if params:
                try:
                    self._difficulty[leg] = float(params[0])
                except (TypeError, ValueError):
                    pass
            if leg == self.active_leg:
                self.miner_writer.write(data)
                await self.miner_writer.drain()
            return

        # Track jobs; only forward notifies from active leg.
        # Namespace job ids so dual upstreams never collide inside the miner.
        if method == "mining.notify":
            job_id = extract_notify_job_id(msg)
            if job_id:
                self._job_leg[job_id] = leg
                if len(self._job_leg) > 5000:
                    for k in list(self._job_leg.keys())[:1000]:
                        self._job_leg.pop(k, None)
            if leg == self.active_leg:
                out = rewrite_notify_job_id(data, leg)
                self.miner_writer.write(out)
                await self.miner_writer.drain()
            return

        # JSON-RPC responses (subscribe/authorize/submit results)
        if "id" in msg and msg.get("id") is not None and method is None:
            req_id = msg["id"]
            # Capture extranonce from subscribe results
            if "result" in msg and msg.get("result") is not None:
                en1, en2 = extract_subscribe_extranonce(msg.get("result"))
                if en1 is not None:
                    self._extranonce[leg] = (en1, en2)

            # Dedupe fan-out handshake responses: first wins to miner
            if req_id in self._seen_response_ids:
                # Still forward submit accept/reject from either leg (unique ids usually)
                # Only suppress exact duplicate of already-seen handshake ids if we
                # already forwarded that id. Submits get unique ids so they pass.
                return

            self._seen_response_ids.add(req_id)
            # Prefer customer-leg handshake responses when both race
            if leg != LEG_CUSTOMER and req_id in self._seen_response_ids:
                # already handled above; if customer hasn't answered yet, allow fee
                pass
            self.miner_writer.write(data)
            await self.miner_writer.drain()
            return

        # Other notifications: only active leg
        if leg == self.active_leg:
            self.miner_writer.write(data)
            await self.miner_writer.drain()

    async def _hashsplit_switch_loop(self) -> None:
        """Alternate active leg on a timer for target fee percent."""
        if not self.settings:
            return
        switch_s = max(5.0, float(self.settings.hashsplit_switch_seconds))
        fee_pct = max(0.0, min(100.0, float(self.settings.hashsplit_fee_percent)))
        # Equal slices when 50/50; otherwise weight fee slice length.
        # Cycle = customer_slice + fee_slice; fee_slice / cycle = fee_pct/100
        if fee_pct <= 0:
            customer_s, fee_s = switch_s, 0.0
        elif fee_pct >= 100:
            customer_s, fee_s = 0.0, switch_s
        else:
            # Use switch_seconds as the base slice for the larger leg
            if fee_pct <= 50:
                fee_s = switch_s
                customer_s = switch_s * (100.0 - fee_pct) / fee_pct
            else:
                customer_s = switch_s
                fee_s = switch_s * fee_pct / (100.0 - fee_pct)

        logger.info(
            f"Session {self.session_id}: hashsplit schedule "
            f"customer_s={customer_s:.1f} fee_s={fee_s:.1f} (fee_pct={fee_pct})"
        )

        try:
            while self._running:
                # Customer slice
                if customer_s > 0:
                    await self._switch_active_leg(LEG_CUSTOMER)
                    await asyncio.sleep(customer_s)
                if not self._running:
                    break
                # Fee slice
                if fee_s > 0:
                    await self._switch_active_leg(LEG_FEE)
                    await asyncio.sleep(fee_s)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Session {self.session_id}: switch loop error: {e}", exc_info=True)

    async def _switch_active_leg(self, leg: str) -> None:
        """Switch which upstream feeds jobs to the miner."""
        if leg == self.active_leg:
            return
        prev = self.active_leg
        prev_en1, prev_en2 = self._extranonce.get(prev, (None, None))
        self.active_leg = leg
        en1, en2 = self._extranonce.get(leg, (None, None))
        diff = self._difficulty.get(leg)
        upstream = (
            self._fee_user
            if leg == LEG_FEE
            else self._customer_user
        )

        logger.info(
            f"Session {self.session_id}: hashsplit switch {prev} → {leg} "
            f"extranonce1={en1} en2_size={en2} diff={diff}"
        )
        await self.storage.update_session_fields(
            self.session_id,
            hashsplit_leg=leg,
            upstream_worker=upstream,
        )

        try:
            # Only push set_extranonce when the extranonce actually changes —
            # unnecessary flips were hard on cgminer during the earlier spike.
            if en1 is not None and en2 is not None and (en1, en2) != (prev_en1, prev_en2):
                self.miner_writer.write(build_set_extranonce(en1, en2))
                await self.miner_writer.drain()
            if diff is not None:
                self.miner_writer.write(build_set_difficulty(diff))
                await self.miner_writer.drain()
        except Exception as e:
            logger.error(f"Session {self.session_id}: failed to signal leg switch: {e}")

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

    async def _maybe_publish_share_event(
        self,
        message,
        ts_recv: datetime,
    ) -> None:
        """
        Publish ShareEvent to Nostr if conditions are met.

        Conditions:
        - Nostr is enabled in settings
        - Nostr client is available and connected
        - Broadcast is enabled for this session
        - Message is a mining.submit

        Args:
            message: Parsed Stratum message
            ts_recv: Timestamp when message was received
        """
        try:
            # Check if Nostr is enabled
            if not self.settings or not self.settings.nostr_enabled:
                return

            # Check if Nostr client is available
            if not self.nostr_client or not self.nostr_client.connected:
                return

            # Check if broadcast is enabled for this session
            if not await self.storage.is_session_broadcast_enabled(self.session_id):
                return

            # Check if this is a mining.submit message
            if message.method != "mining.submit":
                return

            # Increment sequence number
            self._share_event_seq += 1

            # Get repeat count for this session
            repeat_count = await self.storage.get_session_repeat_count(self.session_id)

            # Create ShareEvent
            share_event = ShareEvent(
                run_id=self.settings.run_id,
                event_id=str(uuid.uuid4()),
                seq=self._share_event_seq,
                ts=ts_recv.isoformat() + "Z",
                pool=PoolInfo(host=self.pool_host, port=self.pool_port),
                stratum=StratumData(
                    method=message.method,
                    id=message.id,
                    params=message.params or [],
                ),
                repeat_count=repeat_count,
                context={
                    "session_id": self.session_id,
                    "miner_peer": self.miner_peer,
                },
            )

            # Publish to Nostr
            tags = [
                [TAG_KEY_T, TAG_HASHSCOPE],
                [TAG_KEY_RUN, self.settings.run_id],
                [TAG_KEY_TYPE, TAG_TYPE_SHARE],
                [TAG_KEY_SCHEMA, TAG_SCHEMA],
            ]

            content = share_event.model_dump_json()

            await self.nostr_client.publish_event(
                kind=self.settings.nostr_kind_share,
                content=content,
                tags=tags,
            )

            logger.debug(
                f"Published ShareEvent seq={self._share_event_seq} "
                f"for session {self.session_id}"
            )

        except Exception as e:
            # Never let publishing errors affect relaying
            logger.error(f"Error publishing ShareEvent: {e}", exc_info=True)

    async def _maybe_auto_replay(
        self,
        message,
        message_data: str,
    ) -> None:
        """
        Auto-replay a mining.submit message if enabled (load testing).

        Args:
            message: Parsed Stratum message
            message_data: The raw message string
        """
        try:
            # Check if auto-replay is enabled for this session
            if not await self.storage.is_session_auto_replay_enabled(self.session_id):
                return

            # Get the auto-replay count
            replay_count = await self.storage.get_session_auto_replay_count(self.session_id)

            logger.info(
                f"Auto-replaying mining.submit {replay_count}x for session {self.session_id}"
            )

            # Replay the message N times with random delays
            import random
            for i in range(replay_count):
                # Random delay between 1-5ms for high load testing
                delay = random.uniform(0.001, 0.005)
                await asyncio.sleep(delay)

                # Create the replay through the existing replay_message method
                try:
                    response_dict, latency_ms = await self.replay_message(message_data)

                    # Capture the replay message with index
                    replay_msg_id = await self.capture_replay_message(
                        request_data=message_data,
                        response_dict=response_dict,
                        latency_ms=latency_ms,
                        replay_index=i
                    )

                    logger.debug(
                        f"Auto-replay {i+1}/{replay_count} completed "
                        f"for session {self.session_id}, msg_id={replay_msg_id}, latency={latency_ms:.1f}ms"
                    )
                except Exception as e:
                    logger.error(f"Auto-replay {i+1}/{replay_count} failed: {e}")

        except Exception as e:
            # Never let auto-replay errors affect relaying
            logger.error(f"Error in auto-replay: {e}", exc_info=True)

    async def disconnect_from_pool(self) -> None:
        """
        Forcefully disconnect the session.

        This closes both the pool and miner connections, forcing the miner
        to completely reconnect and establish a fresh session.
        """
        logger.info(f"Session {self.session_id}: Force disconnecting session (pool + miner)")

        # Update pool connection status to disconnected
        await self.storage.update_session_pool_status(
            session_id=self.session_id,
            connected=False,
            pool_peer=None,
        )

        # Close the pool connection
        if self.pool_writer:
            try:
                self.pool_writer.close()
                await self.pool_writer.wait_closed()
                logger.info(f"Session {self.session_id}: Pool connection closed")
            except Exception as e:
                logger.error(f"Error force-closing pool connection: {e}")

        # Close the miner connection to force full reconnect
        if self.miner_writer:
            try:
                self.miner_writer.close()
                await self.miner_writer.wait_closed()
                logger.info(f"Session {self.session_id}: Miner connection closed")
            except Exception as e:
                logger.error(f"Error force-closing miner connection: {e}")

        # Set to None to ensure they're not used again
        self.pool_writer = None
        self.pool_reader = None
        self.miner_writer = None
        self.miner_reader = None

        # Mark session as not running to stop relay loops
        self._running = False

    async def _cleanup(self) -> None:
        """Clean up connections."""
        logger.info(f"Session {self.session_id}: Cleaning up")

        self._running = False

        if self._switch_task and not self._switch_task.done():
            self._switch_task.cancel()

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

        if self.fee_writer:
            try:
                self.fee_writer.close()
                await self.fee_writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing fee pool connection: {e}")

