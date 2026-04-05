"""Runtime configuration for the current internal serving baseline."""

from __future__ import annotations

from logging import getLevelNamesMapping
from os import getenv
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator, model_validator

from saudi_open_data_mcp.security.http_auth import (
    ALL_HTTP_AUTH_CAPABILITIES,
    HTTPAuthCapability,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL_DIR = PROJECT_ROOT / ".local"
DEFAULT_REGISTRY_PATH = DEFAULT_LOCAL_DIR / "registry.sqlite"
DEFAULT_SNAPSHOT_DIR = DEFAULT_LOCAL_DIR / "snapshots"
DEFAULT_CACHE_DIR = DEFAULT_LOCAL_DIR / "cache"
TRUE_ENV_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_ENV_VALUES = frozenset({"0", "false", "no", "off"})
VALID_LOG_LEVELS = frozenset(
    name for name in getLevelNamesMapping() if isinstance(name, str) and name.isalpha()
)


class RuntimeConfigurationError(ValueError):
    """Operator-facing runtime configuration error."""


class SourceConfig(BaseModel):
    """Current approved source endpoint configuration.

    The fields remain explicitly source-specific so future source expansion does
    not inherit hidden assumptions from the current SAMA-first baseline.
    """

    sama_base_url: str = "https://www.sama.gov.sa"
    data_gov_sa_base_url: str = "https://open.data.gov.sa"


class TransportConfig(BaseModel):
    """Transport configuration."""

    http_host: str = Field(default="127.0.0.1", min_length=1)
    http_port: int = Field(default=8000, ge=1, le=65535)
    http_auth_token: SecretStr | None = None
    http_auth_capabilities: frozenset[HTTPAuthCapability] = Field(
        default_factory=lambda: ALL_HTTP_AUTH_CAPABILITIES
    )

    @field_validator("http_host")
    @classmethod
    def _validate_http_host(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("HTTP_HOST must not be empty")
        return normalized

    @field_validator("http_auth_capabilities")
    @classmethod
    def _validate_http_auth_capabilities(
        cls,
        value: frozenset[HTTPAuthCapability],
    ) -> frozenset[HTTPAuthCapability]:
        if not value:
            raise ValueError("HTTP_AUTH_CAPABILITIES must include at least one capability")
        return value


class TierARefreshConfig(BaseModel):
    """Optional Tier A background refresh configuration."""

    enabled: bool = False
    interval_seconds: int = Field(default=3600, gt=0)


class RuntimeConfig(BaseModel):
    """Application configuration."""

    app_name: str = "saudi-open-data-mcp"
    source: SourceConfig = Field(default_factory=SourceConfig)
    registry_path: Path = DEFAULT_REGISTRY_PATH
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR
    cache_dir: Path = DEFAULT_CACHE_DIR
    log_level: str = "INFO"
    transport: TransportConfig = Field(default_factory=TransportConfig)
    tier_a_refresh: TierARefreshConfig = Field(default_factory=TierARefreshConfig)

    @field_validator("registry_path", "snapshot_dir", "cache_dir", mode="before")
    @classmethod
    def _normalize_paths(cls, value: Path | str) -> Path:
        return Path(value).expanduser()

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in VALID_LOG_LEVELS:
            allowed_levels = ", ".join(sorted(VALID_LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL must be one of: {allowed_levels}")
        return normalized

    @model_validator(mode="after")
    def _validate_storage_paths(self) -> Self:
        if self.registry_path == self.snapshot_dir:
            raise ValueError("REGISTRY_PATH and SNAPSHOT_DIR must not point to the same path")
        if self.registry_path == self.cache_dir:
            raise ValueError("REGISTRY_PATH and CACHE_DIR must not point to the same path")
        if self.snapshot_dir == self.cache_dir:
            raise ValueError("SNAPSHOT_DIR and CACHE_DIR must not point to the same path")
        return self


def _path_from_env(name: str, default: Path) -> Path:
    """Return a path override when configured, else the stable project default."""

    configured = getenv(name)
    return Path(configured) if configured else default


def _bool_from_env(name: str, default: bool = False) -> bool:
    """Return a deterministic boolean environment override."""

    configured = getenv(name)
    if configured is None:
        return default

    normalized = configured.strip().lower()
    if normalized in TRUE_ENV_VALUES:
        return True
    if normalized in FALSE_ENV_VALUES:
        return False

    raise RuntimeConfigurationError(
        f"{name} must be one of: 1, true, yes, on, 0, false, no, off"
    )


def _int_from_env(name: str, default: int) -> int:
    """Return a deterministic integer environment override."""

    configured = getenv(name)
    if configured is None:
        return default

    try:
        return int(configured.strip())
    except ValueError as exc:
        raise RuntimeConfigurationError(f"{name} must be an integer") from exc


def _capabilities_from_env(
    name: str,
    default: frozenset[HTTPAuthCapability],
) -> frozenset[HTTPAuthCapability]:
    """Return a deterministic capability set override."""

    configured = getenv(name)
    if configured is None:
        return default

    raw_values = [part.strip().lower() for part in configured.split(",")]
    if not raw_values or any(not value for value in raw_values):
        raise RuntimeConfigurationError(
            f"{name} must be a comma-separated list of: "
            + ", ".join(capability.value for capability in HTTPAuthCapability)
        )

    try:
        return frozenset(HTTPAuthCapability(value) for value in raw_values)
    except ValueError as exc:
        raise RuntimeConfigurationError(
            f"{name} must be a comma-separated list of: "
            + ", ".join(capability.value for capability in HTTPAuthCapability)
        ) from exc


def prepare_runtime_storage(config: RuntimeConfig) -> None:
    """Prepare and validate the configured runtime storage paths."""

    _prepare_registry_parent(config.registry_path)
    _prepare_directory(config.snapshot_dir, env_name="SNAPSHOT_DIR")
    _prepare_directory(config.cache_dir, env_name="CACHE_DIR")


def load_config() -> RuntimeConfig:
    """Load deterministic runtime settings from the environment."""

    try:
        return RuntimeConfig(
            source=SourceConfig(
                sama_base_url=getenv("SAMA_BASE_URL", "https://www.sama.gov.sa"),
                data_gov_sa_base_url=getenv(
                    "DATA_GOV_SA_BASE_URL",
                    "https://open.data.gov.sa",
                ),
            ),
            registry_path=_path_from_env("REGISTRY_PATH", DEFAULT_REGISTRY_PATH),
            snapshot_dir=_path_from_env("SNAPSHOT_DIR", DEFAULT_SNAPSHOT_DIR),
            cache_dir=_path_from_env("CACHE_DIR", DEFAULT_CACHE_DIR),
            log_level=getenv("LOG_LEVEL", "INFO"),
            transport=TransportConfig(
                http_host=getenv("HTTP_HOST", "127.0.0.1"),
                http_port=_int_from_env("HTTP_PORT", 8000),
                http_auth_token=(
                    SecretStr(token) if (token := getenv("HTTP_AUTH_TOKEN")) else None
                ),
                http_auth_capabilities=_capabilities_from_env(
                    "HTTP_AUTH_CAPABILITIES",
                    ALL_HTTP_AUTH_CAPABILITIES,
                ),
            ),
            tier_a_refresh=TierARefreshConfig(
                enabled=_bool_from_env("TIER_A_REFRESH_ENABLED", False),
                interval_seconds=_int_from_env(
                    "TIER_A_REFRESH_INTERVAL_SECONDS",
                    3600,
                ),
            ),
        )
    except ValidationError as exc:
        raise RuntimeConfigurationError(_format_validation_error(exc)) from exc


def _prepare_registry_parent(registry_path: Path) -> None:
    """Validate the registry file path and ensure its parent directory exists."""

    if registry_path.exists() and not registry_path.is_file():
        raise RuntimeConfigurationError(
            f"REGISTRY_PATH must point to a file path, not an existing directory: {registry_path}"
        )

    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeConfigurationError(
            "unable to prepare REGISTRY_PATH parent directory "
            f"'{registry_path.parent}': {exc}"
        ) from exc


def _prepare_directory(path: Path, *, env_name: str) -> None:
    """Validate a configured runtime directory and ensure it exists."""

    if path.exists() and not path.is_dir():
        raise RuntimeConfigurationError(
            f"{env_name} must point to a directory path, not an existing file: {path}"
        )

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeConfigurationError(
            f"unable to prepare {env_name} directory '{path}': {exc}"
        ) from exc


def _format_validation_error(exc: ValidationError) -> str:
    """Format a compact operator-facing configuration validation message."""

    parts = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        parts.append(f"{location}: {error['msg']}")
    return "invalid runtime configuration: " + "; ".join(parts)
