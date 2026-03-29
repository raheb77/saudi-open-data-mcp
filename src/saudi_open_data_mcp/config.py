"""Runtime configuration for the scaffold."""

from __future__ import annotations

from os import getenv
from pathlib import Path

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL_DIR = PROJECT_ROOT / ".local"
DEFAULT_REGISTRY_PATH = DEFAULT_LOCAL_DIR / "registry.sqlite"
DEFAULT_SNAPSHOT_DIR = DEFAULT_LOCAL_DIR / "snapshots"
DEFAULT_CACHE_DIR = DEFAULT_LOCAL_DIR / "cache"


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
    registry_path: Path = DEFAULT_REGISTRY_PATH
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR
    cache_dir: Path = DEFAULT_CACHE_DIR
    log_level: str = "INFO"
    transport: TransportConfig = Field(default_factory=TransportConfig)


def _path_from_env(name: str, default: Path) -> Path:
    """Return a path override when configured, else the stable project default."""

    configured = getenv(name)
    return Path(configured) if configured else default


def load_config() -> RuntimeConfig:
    """Load deterministic runtime settings from the environment."""

    return RuntimeConfig(
        source=SourceConfig(base_url=getenv("SAMA_BASE_URL", "https://www.sama.gov.sa")),
        registry_path=_path_from_env("REGISTRY_PATH", DEFAULT_REGISTRY_PATH),
        snapshot_dir=_path_from_env("SNAPSHOT_DIR", DEFAULT_SNAPSHOT_DIR),
        cache_dir=_path_from_env("CACHE_DIR", DEFAULT_CACHE_DIR),
        log_level=getenv("LOG_LEVEL", "INFO"),
        transport=TransportConfig(
            http_host=getenv("HTTP_HOST", "0.0.0.0"),
            http_port=int(getenv("HTTP_PORT", "8000")),
        ),
    )
