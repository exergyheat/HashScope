"""Main entry point for the proxy server (standalone mode)."""

import asyncio
import logging
import sys

from ..capture.storage import CaptureStorage
from ..config.settings import get_settings
from .server import ProxyServer


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        stream=sys.stdout,
    )


async def main():
    """Main async entry point."""
    setup_logging()

    settings = get_settings()

    # Create storage
    storage = CaptureStorage(
        max_total=settings.capture_max_messages,
        max_per_session=settings.capture_max_per_session,
    )

    # Create and start proxy server
    server = ProxyServer(settings, storage)

    try:
        await server.start()
    except KeyboardInterrupt:
        logging.info("Received interrupt signal")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())

