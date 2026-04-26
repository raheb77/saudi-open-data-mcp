"""Unit tests for the curated live upstream canary."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.observability import upstream_canary as canary_module
from saudi_open_data_mcp.observability.upstream_canary import (
    DATA_GOV_SA_NO_QUERYABLE_DATASET_REASON,
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
            source="mof",
            dataset_id=dataset_id,
            content={
                "url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
                "status_code": 200,
                "content_type": "application/json",
                "body": {
                    "reports_page_url": (
                        "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx"
                    ),
                    "reports": [
                        {
                            "report_url": (
                                "https://www.mof.gov.sa/en/financialreport/2025/Documents/"
                                "Q2E%202025-%20Final.pdf"
                            ),
                            "report_text": (
                                "Results of Surplus/(Deficit) and financing sources in "
                                "H1 of FY 2025 Item Q1 2025 Q2 2025 Total "
                                "Surplus/(Deficit) (58,701) (34,534) Financing Sources "
                                "Government Reserves 0 0"
                            ),
                        }
                    ],
                },
            },
        )


class _LimitedConnector:
    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        return RawPayload(
            source="mof",
            dataset_id=dataset_id,
            content={
                "url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
                "status_code": 200,
                "content_type": "application/json",
                "body": {"summary": {"count": 1}},
            },
        )


@pytest.mark.asyncio
async def test_upstream_canary_skips_data_gov_sa_when_no_queryable_dataset_registered(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_config = RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
        cache_dir=tmp_path / "cache",
    )
    caplog.set_level(logging.INFO, logger=canary_module.LOGGER.name)
    monkeypatch.setattr(
        canary_module,
        "build_default_connector_resolver",
        lambda source_config: _Resolver(_PassingConnector()),
    )

    summary = await run_upstream_canary(runtime_config)

    assert "data-gov-sa-census-marital-status" not in summary.dataset_ids_checked
    assert summary.skipped_sources[0].source == "data-gov-sa"
    assert summary.skipped_sources[0].reason == DATA_GOV_SA_NO_QUERYABLE_DATASET_REASON
    assert "canary: no queryable data.gov.sa dataset registered, skipping" in caplog.text


def test_upstream_canary_rejects_catalog_only_data_gov_sa_dataset_id() -> None:
    with pytest.raises(ValueError, match="upstream canary only supports"):
        canary_module._select_canary_definitions(
            ("data-gov-sa-census-marital-status",)
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
        dataset_ids=("mof-budget-balance-quarterly",),
    )

    assert summary.status is UpstreamCanaryStatus.PASSED
    assert summary.checked_dataset_count == 1
    assert summary.failed_dataset_count == 0
    assert summary.checks[0].status is UpstreamCanaryStatus.PASSED
    assert summary.checks[0].record_count == 1
    assert summary.checks[0].normalization_status == "record_derivable"
    descriptor = repository.get_dataset("mof-budget-balance-quarterly")
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
        dataset_ids=("mof-budget-balance-quarterly",),
    )

    assert summary.status is UpstreamCanaryStatus.FAILED
    assert summary.failed_dataset_count == 1
    assert summary.checks[0].status is UpstreamCanaryStatus.FAILED
    assert summary.checks[0].failure_stage is UpstreamCanaryFailureStage.NORMALIZATION
    assert summary.checks[0].error_type == "UnexpectedNormalizationStatus"
    descriptor = repository.get_dataset("mof-budget-balance-quarterly")
    assert descriptor is not None
    assert descriptor.health_status is DatasetHealthStatus.DEGRADED
