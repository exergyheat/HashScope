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

    # Hashsplit (Exergy): job-band routing (DATUM-style weighting, applied to
    # job selection instead of per-share worker rewriting). Two real,
    # separately-authorized upstream connections (customer + fee leg); which
    # one's mining.notify feeds the miner is re-rolled on every notify using
    # weighted 16-bit bands. A share is only valid against the extranonce1 of
    # the connection it was mined against, so this can't be done per-share on
    # one socket — see git history (share_band mode) for why that failed.
    hashsplit_enabled: bool = False
    hashsplit_fee_percent: float = 50.0  # target % of job time on fee leg
    hashsplit_customer_user: Optional[str] = None  # full worker (else miner user)
    hashsplit_customer_password: str = "x"
    hashsplit_fee_user: Optional[str] = None  # full worker for fee leg (or derived)
    hashsplit_fee_password: str = "x"
    # Fee leg upstream; defaults to the same pool as the customer leg (lab:
    # both legs point at 256foundation, just authorized as separate workers).
    hashsplit_fee_pool_host: Optional[str] = None
    hashsplit_fee_pool_port: Optional[int] = None
    hashsplit_switch_seconds: float = 30.0  # unused in job-band mode (re-rolled per notify, not on a timer)

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

    def get_fee_pool_hostname(self) -> str:
        """Hostname for the fee-leg upstream (defaults to customer pool host)."""
        if self.hashsplit_fee_pool_host:
            host = self.hashsplit_fee_pool_host
            for prefix in ["stratum+tcp://", "stratum://", "tcp://", "http://", "https://"]:
                if host.startswith(prefix):
                    host = host[len(prefix):]
                    break
            if "/" in host:
                host = host.split("/")[0]
            return host
        return self.get_pool_hostname()

    def get_fee_pool_port(self) -> int:
        """Port for the fee-leg upstream (defaults to customer pool port)."""
        if self.hashsplit_fee_pool_port is not None:
            return self.hashsplit_fee_pool_port
        return self.pool_port


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

