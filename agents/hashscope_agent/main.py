"""Main agent entrypoint."""

import asyncio
import logging
import sys
import signal
import random
from datetime import datetime
from collections import deque
from typing import Optional

from .config import AgentSettings
from .pool_client import StratumPoolClient
from .nostr_client import AgentNostrClient
from .stats import AgentStats

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


class HashScopeAgent:
    """Main agent orchestrator."""

    def __init__(self, settings: AgentSettings):
        """
        Initialize agent.

        Args:
            settings: Agent configuration
        """
        self.settings = settings
        self.stats = AgentStats()
        self.errors = deque(maxlen=10)  # Keep last 10 errors

        # Generate Nostr private key if not provided
        nostr_sk = settings.nostr_sk
        if not nostr_sk:
            # Import here to avoid circular import
            from coincurve import PrivateKey
            key = PrivateKey()
            nostr_sk = key.secret.hex()
            logger.info(f"Generated new Nostr private key: {nostr_sk}")
            logger.info(f"Save this key to reuse: export AGENT_NOSTR_SK={nostr_sk}")

        # Clients
        self.pool_client = StratumPoolClient(
            pool_host=settings.pool_host,
            pool_port=settings.pool_port,
            worker_name=settings.worker_name,
            worker_password=settings.worker_password,
        )

        self.nostr_client = AgentNostrClient(
            relay_url=settings.nostr_relay_url,
            private_key_hex=nostr_sk,
            run_id=settings.run_id,
            kind_share=settings.nostr_kind_share,
            kind_telemetry=settings.nostr_kind_telemetry,
        )

        self.running = False
        self._telemetry_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the agent."""
        logger.info(f"Starting HashScope Agent {self.settings.agent_id}")
        logger.info(f"Run ID: {self.settings.run_id}")
        logger.info(f"Pool: {self.settings.pool_host}:{self.settings.pool_port}")
        logger.info(f"Worker: {self.pool_client.worker_name}")

        self.running = True

        try:
            # 1. Connect to pool
            logger.info("Connecting to pool...")
            pool_connected = await self.pool_client.connect()
            if not pool_connected:
                logger.error("Failed to connect to pool")
                self._record_error("Failed to connect to pool")
                return

            # 2. Connect to Nostr relay
            logger.info("Connecting to Nostr relay...")
            nostr_connected = await self.nostr_client.connect()
            if not nostr_connected:
                logger.error("Failed to connect to Nostr relay")
                self._record_error("Failed to connect to Nostr relay")
                return

            # 3. Subscribe to ShareEvents
            logger.info("Subscribing to ShareEvents...")
            await self.nostr_client.subscribe_to_share_events(
                handler=self._handle_share_event
            )

            # 4. Start telemetry publishing task
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())

            logger.info("Agent is running and waiting for share events...")

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            self._record_error(f"Agent error: {str(e)}")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the agent."""
        logger.info("Stopping agent...")
        self.running = False

        # Stop telemetry task
        if self._telemetry_task:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass

        # Disconnect clients
        await self.pool_client.disconnect()
        await self.nostr_client.disconnect()

        logger.info("Agent stopped")

    def _handle_share_event(self, share_event: dict):
        """
        Handle incoming ShareEvent from Nostr.

        Args:
            share_event: ShareEvent dict
        """
        try:
            # Record that we received a share event
            self.stats.record_share_event_received()

            # Extract stratum data
            stratum = share_event.get("stratum", {})
            params = stratum.get("params", [])
            msg_id = stratum.get("id")  # Original message ID from miner
            repeat_count = share_event.get("repeat_count", 1)  # Number of times to submit

            if not params or len(params) < 5:
                logger.warning(f"Invalid share event params: {params}")
                return

            # params format: [worker_name, job_id, extranonce2, ntime, nonce, ...optional extra params]
            # We'll forward ALL parameters except worker_name (index 0)
            job_id = params[1]
            submit_params = params[1:]  # All params after worker_name

            logger.info(
                f"Received share event seq={share_event.get('seq')}, "
                f"msg_id={msg_id}, job_id={job_id}, param_count={len(submit_params)}, "
                f"repeat_count={repeat_count}"
            )

            # Submit to pool multiple times if repeat_count > 1 (load testing)
            asyncio.create_task(
                self._submit_share_repeated(submit_params, msg_id, repeat_count)
            )

        except Exception as e:
            logger.error(f"Error handling share event: {e}", exc_info=True)
            self._record_error(f"Error handling share event: {str(e)}")

    async def _submit_share_repeated(
        self,
        submit_params: list,
        msg_id: Optional[int | str] = None,
        repeat_count: int = 1,
    ):
        """
        Submit a share to the pool multiple times (for load testing).

        Args:
            submit_params: List of submit parameters [job_id, extranonce2, ntime, nonce, ...optional]
            msg_id: Original message ID from Nostr (optional)
            repeat_count: Number of times to submit (1-1000)
        """
        for i in range(repeat_count):
            # Submit the share
            await self._submit_share(submit_params, msg_id)

            # Add random delay between submissions (except after last one)
            if i < repeat_count - 1:
                delay_ms = random.randint(10, 100)  # Random delay 10-100ms
                await asyncio.sleep(delay_ms / 1000.0)

    async def _submit_share(
        self,
        submit_params: list,
        msg_id: Optional[int | str] = None,
    ):
        """
        Submit a share to the pool.

        Args:
            submit_params: List of submit parameters [job_id, extranonce2, ntime, nonce, ...optional]
            msg_id: Original message ID from Nostr (optional)
        """
        try:
            self.stats.record_submit_attempted()

            # Extract job_id for logging (first param)
            job_id = submit_params[0] if submit_params else "unknown"

            response = await self.pool_client.submit(submit_params, msg_id)

            if response:
                if response.get("result") is True:
                    self.stats.record_submit_accepted()
                    logger.info(f"Share accepted for job {job_id}")
                else:
                    self.stats.record_submit_rejected()
                    error = response.get("error")
                    logger.warning(f"Share rejected for job {job_id}: {error}")
                    if error:
                        self._record_error(f"Share rejected: {error}")
            else:
                self.stats.record_submit_rejected()
                logger.error(f"No response for share submission job {job_id}")
                self._record_error("No response for share submission")

        except Exception as e:
            self.stats.record_submit_rejected()
            logger.error(f"Error submitting share: {e}", exc_info=True)
            self._record_error(f"Error submitting share: {str(e)}")

    async def _telemetry_loop(self):
        """Periodically publish telemetry events."""
        try:
            while self.running:
                await asyncio.sleep(self.settings.telemetry_interval_sec)

                # Determine connection state
                if self.pool_client.connected and self.nostr_client.connected:
                    conn_state = "connected"
                elif not self.pool_client.connected:
                    conn_state = "error"
                    self._record_error("Pool connection lost")
                elif not self.nostr_client.connected:
                    conn_state = "error"
                    self._record_error("Nostr connection lost")
                else:
                    conn_state = "reconnecting"

                # Build telemetry event
                telemetry = {
                    "schema": "hashscope.v1",
                    "run_id": self.settings.run_id,
                    "agent_id": self.settings.agent_id,
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "pool_target": {
                        "host": self.settings.pool_host,
                        "port": self.settings.pool_port,
                    },
                    "conn_state": conn_state,
                    "stats": self.stats.to_dict(),
                    "errors": list(self.errors),
                }

                # Publish telemetry
                import json
                content = json.dumps(telemetry)
                await self.nostr_client.publish_telemetry(content)

                # Get current rates
                rate_1min = self.stats.get_submit_rate_per_second(60)
                rate_10sec = self.stats.get_submit_rate_per_second(10)

                logger.info(
                    f"📊 Telemetry: state={conn_state}, "
                    f"received={self.stats.share_events_received_total}, "
                    f"submitted={self.stats.submits_attempted_total}, "
                    f"accepted={self.stats.submits_accepted_total}, "
                    f"rejected={self.stats.submits_rejected_total}, "
                    f"rate_1m={rate_1min:.2f}/s, "
                    f"rate_10s={rate_10sec:.2f}/s"
                )

        except asyncio.CancelledError:
            logger.info("Telemetry loop cancelled")
        except Exception as e:
            logger.error(f"Error in telemetry loop: {e}", exc_info=True)

    def _record_error(self, error: str):
        """
        Record an error.

        Args:
            error: Error message
        """
        self.errors.append(error)


async def main():
    """Main entry point."""
    # Load settings
    try:
        settings = AgentSettings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        sys.exit(1)

    # Create and start agent
    agent = HashScopeAgent(settings)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(agent.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Start agent
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

