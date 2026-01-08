"""Stratum protocol client for connecting to mining pool."""

import asyncio
import json
import logging
import random
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class StratumPoolClient:
    """Async Stratum protocol client for mining pool connection."""

    def __init__(
        self,
        pool_host: str,
        pool_port: int,
        worker_name: str,
        worker_password: str = "",
    ):
        """
        Initialize pool client.

        Args:
            pool_host: Pool hostname (can include protocol prefix like stratum+tcp://)
            pool_port: Pool port
            worker_name: Worker/miner name
            worker_password: Worker password (optional)
        """
        # Strip protocol prefix if present
        self.pool_host = self._strip_protocol(pool_host)
        self.pool_port = pool_port

        # Generate unique worker name with random suffix
        # Format: {original_worker}.hashscope_agent{5_digit_random}
        random_suffix = random.randint(10000, 99999)
        self.worker_name = f"{worker_name}.hashscope_agent{random_suffix}"
        self.worker_password = worker_password

        logger.info(f"Agent worker name: {self.worker_name}")

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False

        self._message_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}

        # Mining session data
        self.session_id: Optional[str] = None
        self.extranonce1: Optional[str] = None
        self.extranonce2_size: Optional[int] = None
        self.difficulty: Optional[float] = None

        # Background tasks
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """
        Connect to pool and perform initial handshake.

        Returns:
            True if connected and subscribed successfully
        """
        try:
            logger.info(f"Connecting to pool {self.pool_host}:{self.pool_port}")
            self.reader, self.writer = await asyncio.open_connection(
                self.pool_host, self.pool_port
            )
            self.connected = True

            # Start reading responses
            self._read_task = asyncio.create_task(self._read_loop())

            # Perform Stratum handshake
            # 1. Subscribe
            subscribe_result = await self.subscribe()
            if not subscribe_result:
                logger.error("Failed to subscribe")
                return False

            # 2. Authorize
            auth_result = await self.authorize()
            if not auth_result:
                logger.error("Failed to authorize")
                return False

            logger.info(f"Successfully connected and authorized as {self.worker_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to pool: {e}", exc_info=True)
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from pool."""
        logger.info("Disconnecting from pool")
        self.connected = False

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

    async def subscribe(self) -> bool:
        """
        Send mining.subscribe request.

        Returns:
            True if successful
        """
        try:
            response = await self._send_request(
                "mining.subscribe",
                [f"hashscope_agent/{self.worker_name}"],
            )

            if response and "result" in response:
                result = response["result"]
                # Result format: [[["mining.set_difficulty", "subscription_id"], ...], extranonce1, extranonce2_size]
                if isinstance(result, list) and len(result) >= 3:
                    self.session_id = result[0][0][1] if result[0] else None
                    self.extranonce1 = result[1]
                    self.extranonce2_size = result[2]
                    logger.info(
                        f"Subscribed: extranonce1={self.extranonce1}, "
                        f"extranonce2_size={self.extranonce2_size}"
                    )
                    return True

            logger.error(f"Subscribe failed: {response}")
            return False

        except Exception as e:
            logger.error(f"Subscribe error: {e}", exc_info=True)
            return False

    async def authorize(self) -> bool:
        """
        Send mining.authorize request.

        Returns:
            True if successful
        """
        try:
            response = await self._send_request(
                "mining.authorize",
                [self.worker_name, self.worker_password],
            )

            if response and response.get("result") is True:
                logger.info(f"Authorized as {self.worker_name}")
                return True

            logger.error(f"Authorization failed: {response}")
            return False

        except Exception as e:
            logger.error(f"Authorization error: {e}", exc_info=True)
            return False

    async def submit(
        self,
        submit_params: list,
        msg_id: Optional[int | str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Submit a share to the pool.

        Args:
            submit_params: Submit parameters [job_id, extranonce2, ntime, nonce, ...optional extra params]
            msg_id: Message ID (from Nostr or auto-generated if None)

        Returns:
            Response dict or None if failed
        """
        try:
            # Prepend worker_name to the params
            # Format: [worker_name, job_id, extranonce2, ntime, nonce, ...optional]
            full_params = [self.worker_name] + submit_params

            # Extract job_id for logging (first param after worker_name)
            job_id = submit_params[0] if submit_params else "unknown"

            logger.debug(f"Submitting share with {len(full_params)} params: {full_params}")

            response = await self._send_request(
                "mining.submit",
                full_params,
                msg_id=msg_id,
            )

            if response:
                if "result" in response:
                    if response["result"] is True:
                        logger.debug(f"Share accepted for job {job_id}")
                    else:
                        logger.warning(f"Share rejected for job {job_id}: {response}")
                elif "error" in response:
                    logger.warning(f"Share error for job {job_id}: {response['error']}")

            return response

        except Exception as e:
            logger.error(f"Submit error: {e}", exc_info=True)
            return None

    async def _send_request(
        self,
        method: str,
        params: list,
        timeout: float = 10.0,
        msg_id: Optional[int | str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a JSON-RPC request and wait for response.

        Args:
            method: Method name
            params: Method parameters
            timeout: Response timeout in seconds
            msg_id: Message ID (optional, auto-generated if None)

        Returns:
            Response dict or None if failed
        """
        if not self.connected or not self.writer:
            return None

        # Use provided msg_id or auto-increment
        if msg_id is None:
            self._message_id += 1
            msg_id = self._message_id

        request = {
            "id": msg_id,
            "method": method,
            "params": params,
        }

        # Create future for response
        future = asyncio.Future()
        self._pending_requests[msg_id] = future

        try:
            # Send request
            message = json.dumps(request) + "\n"
            self.writer.write(message.encode())
            await self.writer.drain()

            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.error(f"Request timeout for {method}")
            return None
        except Exception as e:
            logger.error(f"Request error for {method}: {e}", exc_info=True)
            return None
        finally:
            # Clean up
            if msg_id in self._pending_requests:
                del self._pending_requests[msg_id]

    async def _read_loop(self):
        """Read and process messages from pool."""
        try:
            while self.connected and self.reader:
                line = await self.reader.readuntil(b'\n')
                if not line:
                    break

                try:
                    message = json.loads(line.decode().strip())
                    await self._handle_message(message)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}, data: {line}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)

        except asyncio.IncompleteReadError:
            logger.info("Pool disconnected")
        except Exception as e:
            logger.error(f"Read loop error: {e}", exc_info=True)
        finally:
            self.connected = False

    async def _handle_message(self, message: Dict[str, Any]):
        """
        Handle incoming message from pool.

        Args:
            message: Parsed JSON message
        """
        # Check if it's a response to a request
        if "id" in message and message["id"] is not None:
            msg_id = message["id"]
            if msg_id in self._pending_requests:
                future = self._pending_requests[msg_id]
                if not future.done():
                    future.set_result(message)
                return

        # Handle notifications (id is None)
        method = message.get("method")

        if method == "mining.set_difficulty":
            params = message.get("params", [])
            if params:
                self.difficulty = params[0]
                logger.debug(f"Difficulty set to {self.difficulty}")

        elif method == "mining.notify":
            # New work notification
            # We don't need to process work for this use case
            logger.debug("Received new work notification")

        else:
            logger.debug(f"Unhandled notification: {method}")

    @staticmethod
    def _strip_protocol(host: str) -> str:
        """
        Strip protocol prefix from hostname.

        Args:
            host: Hostname possibly with protocol (e.g., stratum+tcp://pool.example.com)

        Returns:
            Clean hostname without protocol
        """
        # Remove common protocol prefixes
        for prefix in ["stratum+tcp://", "stratum://", "tcp://", "http://", "https://"]:
            if host.startswith(prefix):
                host = host[len(prefix):]
                break

        # Remove any trailing slashes or paths
        if "/" in host:
            host = host.split("/")[0]

        return host

