"""Shared test fixtures."""

from __future__ import annotations

import pytest

from saudi_open_data_mcp.observability import reset_metrics


@pytest.fixture(autouse=True)
def _reset_shared_metrics() -> None:
    reset_metrics()
    yield
    reset_metrics()
