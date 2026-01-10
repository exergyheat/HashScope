"""FastAPI dependencies."""

from typing import TYPE_CHECKING

from ..capture.storage import CaptureStorage
from ..capture.telemetry import TelemetryStorage

if TYPE_CHECKING:
    from ..proxy.server import ProxyServer

# Global storage instances
_storage: CaptureStorage = None
_telemetry_storage: TelemetryStorage = None
_proxy_server: "ProxyServer" = None


def init_storage(storage: CaptureStorage) -> None:
    """Initialize the global storage instance."""
    global _storage
    _storage = storage


def get_storage() -> CaptureStorage:
    """Get the global storage instance."""
    if _storage is None:
        raise RuntimeError("Storage not initialized")
    return _storage


def init_telemetry_storage(telemetry_storage: TelemetryStorage) -> None:
    """Initialize the global telemetry storage instance."""
    global _telemetry_storage
    _telemetry_storage = telemetry_storage


def get_telemetry_storage() -> TelemetryStorage:
    """Get the global telemetry storage instance."""
    if _telemetry_storage is None:
        raise RuntimeError("Telemetry storage not initialized")
    return _telemetry_storage


def init_proxy_server(proxy_server: "ProxyServer") -> None:
    """Initialize the global proxy server instance."""
    global _proxy_server
    _proxy_server = proxy_server


def get_proxy_server() -> "ProxyServer":
    """Get the global proxy server instance."""
    if _proxy_server is None:
        raise RuntimeError("Proxy server not initialized")
    return _proxy_server

