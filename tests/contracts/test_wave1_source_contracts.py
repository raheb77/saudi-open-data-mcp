"""Contract tests for Wave 1 SAMA source surfaces and shared-locator assumptions."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.sama import SAMAConnector
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
)
from saudi_open_data_mcp.normalization.validators import TEXT_HTML_LIMITATION
from saudi_open_data_mcp.registry.bootstrap import (
    SAMA_SHARED_SOURCE_LOCATOR_GROUPS,
    WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS,
    WAVE_1_HOT_SET_TIER_A_DATASET_IDS,
    bootstrap_registry,
)
from saudi_open_data_mcp.registry.models import UpdateFrequency
from saudi_open_data_mcp.registry.repository import RegistryRepository

WAVE_1_TIER_A_EXPECTATIONS = {
    "sama-pos-weekly": (
        "/en-US/Indices/Pages/POS.aspx",
        UpdateFrequency.WEEKLY,
    ),
    "sama-money-supply-weekly": (
        "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        UpdateFrequency.WEEKLY,
    ),
    "sama-repo-rate": (
        "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        UpdateFrequency.AD_HOC,
    ),
    "sama-reverse-repo-rate": (
        "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        UpdateFrequency.AD_HOC,
    ),
    "sama-deposits-core": (
        "report.aspx?cid=55",
        UpdateFrequency.MONTHLY,
    ),
}

def _bootstrapped_descriptors(tmp_path: Path):
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    return bootstrap_registry(repository)


def _raw_payload(
    *,
    locator: str,
    content_type: str,
    body: object,
) -> RawPayload:
    if locator.startswith("/"):
        url = f"https://www.sama.gov.sa{locator}"
    else:
        url = f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{locator}"

    return RawPayload(
        source="sama",
        dataset_id=locator,
        content={
            "url": url,
            "status_code": 200,
            "content_type": content_type,
            "body": body,
        },
    )


def test_wave_one_tier_a_descriptor_contract_matches_expected_locators_and_frequencies(
    tmp_path: Path,
) -> None:
    descriptors_by_id = {
        descriptor.dataset_id: descriptor for descriptor in _bootstrapped_descriptors(tmp_path)
    }

    assert set(WAVE_1_HOT_SET_TIER_A_DATASET_IDS) == set(WAVE_1_TIER_A_EXPECTATIONS)
    for dataset_id, (source_locator, update_frequency) in WAVE_1_TIER_A_EXPECTATIONS.items():
        descriptor = descriptors_by_id[dataset_id]
        assert descriptor.source == "sama"
        assert descriptor.source_locator == source_locator
        assert descriptor.update_frequency is update_frequency


def test_sama_connector_approved_page_paths_match_bootstrapped_page_locators(
    tmp_path: Path,
) -> None:
    bootstrapped_page_locators = {
        descriptor.source_locator
        for descriptor in _bootstrapped_descriptors(tmp_path)
        if descriptor.source == "sama" and descriptor.source_locator.startswith("/")
    }

    assert bootstrapped_page_locators == SAMAConnector.approved_page_paths


def test_shared_source_locator_groups_are_explicit_and_limited(tmp_path: Path) -> None:
    grouped_dataset_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    for descriptor in _bootstrapped_descriptors(tmp_path):
        grouped_dataset_ids[(descriptor.source, descriptor.source_locator)].add(
            descriptor.dataset_id
        )

    shared_groups = {
        key: dataset_ids
        for key, dataset_ids in grouped_dataset_ids.items()
        if len(dataset_ids) > 1
    }

    assert shared_groups == {
        key: set(dataset_ids) for key, dataset_ids in SAMA_SHARED_SOURCE_LOCATOR_GROUPS.items()
    }


@pytest.mark.parametrize(
    (
        "dataset_id",
        "locator",
        "content_type",
        "body",
        "expected_status",
        "expected_record_count",
        "expected_limitations",
    ),
    [
        (
            "sama-pos-weekly",
            "/en-US/Indices/Pages/POS.aspx",
            "text/html",
            "<html><body>official weekly pos page</body></html>",
            NormalizationPipelineStatus.LIMITED,
            0,
            (TEXT_HTML_LIMITATION,),
        ),
        (
            "sama-money-supply-weekly",
            "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
            "text/html",
            "<html><body>official weekly money supply page</body></html>",
            NormalizationPipelineStatus.LIMITED,
            0,
            (TEXT_HTML_LIMITATION,),
        ),
        (
            "sama-repo-rate",
            "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
            "text/html",
            "<html><body>official repo rate page</body></html>",
            NormalizationPipelineStatus.LIMITED,
            0,
            (TEXT_HTML_LIMITATION,),
        ),
        (
            "sama-reverse-repo-rate",
            "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
            "text/html",
            "<html><body>official reverse repo rate page</body></html>",
            NormalizationPipelineStatus.LIMITED,
            0,
            (TEXT_HTML_LIMITATION,),
        ),
        (
            "sama-deposits-core",
            "report.aspx?cid=55",
            "application/json",
            {"rows": [{"series": "deposits", "value": 1}]},
            NormalizationPipelineStatus.RECORD_DERIVABLE,
            1,
            (),
        ),
        (
            "sama-pos-by-city",
            "/en-US/Indices/Pages/POS.aspx",
            "text/html",
            "<html><body>official weekly pos page</body></html>",
            NormalizationPipelineStatus.LIMITED,
            0,
            (TEXT_HTML_LIMITATION,),
        ),
    ],
)
def test_wave_one_fixture_shapes_normalize_as_expected(
    dataset_id: str,
    locator: str,
    content_type: str,
    body: object,
    expected_status: NormalizationPipelineStatus,
    expected_record_count: int,
    expected_limitations: tuple[str, ...],
) -> None:
    assert dataset_id in WAVE_1_HOT_SET_TIER_A_DATASET_IDS + WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS

    result = NormalizationPipeline().normalize(
        _raw_payload(locator=locator, content_type=content_type, body=body)
    )

    assert result.dataset_id == locator
    assert result.status is expected_status
    assert len(result.records) == expected_record_count
    assert result.validation_result is not None
    assert result.validation_result.limitations == expected_limitations
