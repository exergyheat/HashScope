"""Application settings using Pydantic."""

import uuid
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Proxy settings
    listen_host: str = "0.0.0.0"
    listen_port: int = 3333
    pool_host: str
    pool_port: int = 3333

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Capture settings
    capture_max_messages: int = 50_000
    capture_max_per_session: int = 10_000

    # CORS settings
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Nostr settings (Iteration 2)
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nostr_relay_url: Optional[str] = None  # e.g., wss://relay.damus.io
    nostr_relay_url_secondary: Optional[str] = None
    nostr_sk: Optional[str] = None  # Hex-encoded secret key (auto-generated if not provided)
    nostr_kind_share: int = 30080
    nostr_kind_telemetry: int = 30079
    nostr_enabled: bool = False  # Feature flag

    def get_pool_hostname(self) -> str:
        """
        Extract hostname from pool_host, removing any protocol prefix.

        Handles URLs like:
        - stratum+tcp://pool.example.com -> pool.example.com
        - pool.example.com -> pool.example.com
        """
        host = self.pool_host

        # Remove common protocol prefixes
        for prefix in ["stratum+tcp://", "stratum://", "tcp://", "http://", "https://"]:
            if host.startswith(prefix):
                host = host[len(prefix):]
                break

        # Remove any trailing slashes or paths
        if "/" in host:
            host = host.split("/")[0]

        return host


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

