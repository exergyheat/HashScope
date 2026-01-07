"""FastAPI dependencies."""

from ..capture.storage import CaptureStorage

# Global storage instance
_storage: CaptureStorage = None


def init_storage(storage: CaptureStorage) -> None:
    """Initialize the global storage instance."""
    global _storage
    _storage = storage


def get_storage() -> CaptureStorage:
    """Get the global storage instance."""
    if _storage is None:
        raise RuntimeError("Storage not initialized")
    return _storage

