"""FastAPI application factory."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..capture.storage import CaptureStorage
from ..config.settings import Settings, get_settings
from ..proxy.server import ProxyServer
from . import dependencies
from .routes import messages, sessions, websocket

logger = logging.getLogger(__name__)


# Global proxy task
proxy_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global proxy_task

    settings = get_settings()

    # Initialize storage
    storage = CaptureStorage(
        max_total=settings.capture_max_messages,
        max_per_session=settings.capture_max_per_session,
    )
    dependencies.init_storage(storage)

    # Start proxy server in background
    proxy_server = ProxyServer(settings, storage)
    proxy_task = asyncio.create_task(proxy_server.start())

    logger.info("Application started")

    yield

    # Cleanup
    logger.info("Shutting down")
    await proxy_server.stop()

    if proxy_task:
        proxy_task.cancel()
        try:
            await proxy_task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="HashScope API",
        description="Bitcoin Mining MITM Proxy API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(messages.router, prefix="/api", tags=["messages"])
    app.include_router(sessions.router, prefix="/api", tags=["sessions"])
    app.include_router(websocket.router, prefix="/api", tags=["websocket"])

    @app.get("/")
    async def root():
        return {
            "name": "HashScope API",
            "version": "0.1.0",
            "docs": "/docs",
        }

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app

