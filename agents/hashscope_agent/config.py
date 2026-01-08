"""Agent configuration."""

import platform
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Agent configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Pool connection
    pool_host: str
    pool_port: int = 3333
    worker_name: str
    worker_password: str = ""

    # Nostr
    run_id: str
    nostr_relay_url: str
    nostr_sk: str = ""  # Auto-generated if not provided
    agent_id: str = Field(default_factory=lambda: platform.node())

    # Telemetry
    telemetry_interval_sec: int = 5

    # Nostr event kinds
    nostr_kind_share: int = 30080
    nostr_kind_telemetry: int = 30079

