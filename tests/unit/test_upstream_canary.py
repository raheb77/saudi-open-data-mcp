"""Unit tests for the curated live upstream canary."""

from __future__ import annotations

from pathlib import Path

import pytest

from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.observability import upstream_canary as canary_module
from saudi_open_data_mcp.observability.upstream_canary import (
    UpstreamCanaryFailureStage,
    UpstreamCanaryStatus,
    run_upstream_canary,
)
from saudi_open_data_mcp.registry.models import DatasetHealthStatus
from saudi_open_data_mcp.registry.repository import RegistryRepository


class _Resolver:
    def __init__(self, connector) -> None:
        self._connector = connector

    def resolve(self, _source: str):
        return self._connector


class _PassingConnector:
    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        return RawPayload(
            source="data-gov-sa",
            dataset_id=dataset_id,
            content={
                "url": (
                    "https://open.data.gov.sa/ar/datasets/view/"
                    "104380ce-60b6-46bc-ba0a-6d5e10ac46cb/preview/parsed/"
                    "Census%20Marital%20Status%20CSV.json"
                ),
                "status_code": 200,
                "content_type": "application/json",
                "body": {"rows": [{"status": "single", "count": 10}]},
            },
        )


class _LimitedConnector:
    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        return RawPayload(
            source="data-gov-sa",
            dataset_id=dataset_id,
            content={
                "url": (
                    "https://open.data.gov.sa/ar/datasets/view/"
                    "104380ce-60b6-46bc-ba0a-6d5e10ac46cb/preview/parsed/"
                    "Census%20Marital%20Status%20CSV.json"
                ),
                "status_code": 200,
                "content_type": "application/json",
                "body": {"summary": {"count": 1}},
            },
        )


@pytest.mark.asyncio
async def test_upstream_canary_reports_pass_when_curated_live_check_is_record_derivable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_config = RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
        cache_dir=tmp_path / "cache",
    )
    repository = RegistryRepository(runtime_config.registry_path)
    monkeypatch.setattr(
        canary_module,
        "build_default_connector_resolver",
        lambda source_config: _Resolver(_PassingConnector()),
    )

    summary = await run_upstream_canary(
        runtime_config,
        dataset_ids=("data-gov-sa-census-marital-status",),
    )

    assert summary.status is UpstreamCanaryStatus.PASSED
    assert summary.checked_dataset_count == 1
    assert summary.failed_dataset_count == 0
    assert summary.checks[0].status is UpstreamCanaryStatus.PASSED
    assert summary.checks[0].record_count == 1
    assert summary.checks[0].normalization_status == "record_derivable"
    descriptor = repository.get_dataset("data-gov-sa-census-marital-status")
    assert descriptor is not None
    assert descriptor.health_status is DatasetHealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_upstream_canary_reports_failure_when_live_payload_is_not_record_derivable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_config = RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
        cache_dir=tmp_path / "cache",
    )
    repository = RegistryRepository(runtime_config.registry_path)
    monkeypatch.setattr(
        canary_module,
        "build_default_connector_resolver",
        lambda source_config: _Resolver(_LimitedConnector()),
    )

    summary = await run_upstream_canary(
        runtime_config,
        dataset_ids=("data-gov-sa-census-marital-status",),
    )

    assert summary.status is UpstreamCanaryStatus.FAILED
    assert summary.failed_dataset_count == 1
    assert summary.checks[0].status is UpstreamCanaryStatus.FAILED
    assert summary.checks[0].failure_stage is UpstreamCanaryFailureStage.NORMALIZATION
    assert summary.checks[0].error_type == "UnexpectedNormalizationStatus"
    descriptor = repository.get_dataset("data-gov-sa-census-marital-status")
    assert descriptor is not None
    assert descriptor.health_status is DatasetHealthStatus.DEGRADED
