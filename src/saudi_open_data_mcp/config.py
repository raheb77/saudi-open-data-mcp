"""Runtime configuration for the scaffold."""

from __future__ import annotations

from os import getenv
from pathlib import Path

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    """Approved source configuration."""

    name: str = "sama"
    base_url: str = "https://www.sama.gov.sa"
    approved_only: bool = True


class TransportConfig(BaseModel):
    """Transport configuration."""

    http_host: str = "0.0.0.0"
    http_port: int = 8000


class RuntimeConfig(BaseModel):
    """Application configuration."""

    app_name: str = "saudi-open-data-mcp"
    source: SourceConfig = Field(default_factory=SourceConfig)
    registry_path: Path = Path(".local/registry.sqlite")
    snapshot_dir: Path = Path(".local/snapshots")
    cache_dir: Path = Path(".local/cache")
    log_level: str = "INFO"
    transport: TransportConfig = Field(default_factory=TransportConfig)


def load_config() -> RuntimeConfig:
    """Load deterministic runtime settings from the environment."""

    return RuntimeConfig(
        source=SourceConfig(base_url=getenv("SAMA_BASE_URL", "https://www.sama.gov.sa")),
        registry_path=Path(getenv("REGISTRY_PATH", ".local/registry.sqlite")),
        snapshot_dir=Path(getenv("SNAPSHOT_DIR", ".local/snapshots")),
        cache_dir=Path(getenv("CACHE_DIR", ".local/cache")),
        log_level=getenv("LOG_LEVEL", "INFO"),
        transport=TransportConfig(
            http_host=getenv("HTTP_HOST", "0.0.0.0"),
            http_port=int(getenv("HTTP_PORT", "8000")),
        ),
    )
