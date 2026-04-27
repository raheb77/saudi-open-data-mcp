"""Shared MCP-visible tool input annotations."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from saudi_open_data_mcp.tools.query import QueryFilterValue

DatasetIdInput = Annotated[
    str,
    Field(
        description=(
            "Exact canonical dataset_id from the registry. Examples: "
            "'sama-pos-weekly', 'stats-gov-sa-cpi-headline-monthly'."
        ),
    ),
]
IncludeOptionalInput = Annotated[
    bool,
    Field(
        description=(
            "Whether to include optional Tier B hot-set datasets during materialization. "
            "Use false for the default Tier A set; true also includes datasets such as "
            "'sama-pos-by-city'."
        ),
    ),
]
QueryFiltersInput = Annotated[
    dict[str, QueryFilterValue] | None,
    Field(
        description=(
            "Optional exact-match filters keyed by canonical record field. Example: "
            "{'currency_code': 'USD'} or {'observation_month': '2026-01'}."
        ),
    ),
]
QueryLimitInput = Annotated[
    int | None,
    Field(
        ge=1,
        description=(
            "Optional maximum number of matching records to return. Example: 10."
        ),
    ),
]
SearchQueryInput = Annotated[
    str,
    Field(
        description=(
            "Case-insensitive substring to match against dataset metadata. Use an "
            "empty string to list all datasets; examples: 'pos', 'inflation'."
        ),
    ),
]
