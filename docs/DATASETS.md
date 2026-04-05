# Datasets

## Source Scope

- Current MVP source scope is SAMA plus one narrow `data.gov.sa` pilot dataset and
  three narrow `stats.gov.sa` macro datasets.
- Only approved official sources may be accessed.

## Current State

- Dataset fetching is implemented through typed source-specific connectors.
- Registry entries are bootstrapped and persisted in SQLite.
- Dataset descriptors and health metadata are owned by `registry/`.
- Canonical public dataset identity is `dataset_id`.
- Source-boundary identity is kept as `source_locator` in the registry and connector path.

## Contract Direction

- normalized outputs use typed Pydantic models
- normalization dispatches by raw payload source
- registry metadata remains the source of truth for descriptors, caveats, schema versions, and health metadata
- MCP tools continue to accept canonical `dataset_id` across both supported sources

## Wave 3 Canonical Contract Targets

These contracts define the intended enriched record shapes for the current
query-oriented macro datasets. They do not change the current local-only
`query_dataset` semantics or imply that every contract target has the same
source richness or hot-set status.

All Wave 3 canonical contracts currently start at schema version `1.0.0` and
use an additive-within-major evolution policy.

| dataset_id | record shape | temporal granularity | primary key | measures | intended analytical utility |
| --- | --- | --- | --- | --- | --- |
| `sama-pos-weekly` | time-series observation | weekly | `week_start_date`, `week_end_date` | `transaction_count`, `transaction_value_sar` | weekly POS spending momentum, average ticket size, week-over-week trend |
| `sama-money-supply-weekly` | time-series observation | weekly | `week_end_date`, `monetary_aggregate_code` | `amount_sar` | weekly liquidity tracking across monetary aggregates |
| `sama-deposits-core` | time-series observation | monthly | `observation_month`, `deposit_category_code` | `amount_sar` | bundled monthly deposit-component analysis with explicit M1/M2/M3 entry-level context |
| `sama-exchange-rates-current` | snapshot observation | daily | `as_of_date`, `currency_code` | `buy_rate_sar`, `sell_rate_sar` | daily SAR-quoted FX lookup and cross-currency spread comparison |
| `sama-repo-rate` | time-series observation | event | `effective_date` | `rate_percent` | policy-rate timeline and linkage to liquidity indicators |
| `sama-reverse-repo-rate` | time-series observation | event | `effective_date` | `rate_percent` | reverse-repo policy timeline and comparison to repo moves |
| `stats-gov-sa-cpi-headline-monthly` | time-series observation | monthly | `observation_month`, `inflation_series_code` | `yoy_rate_percent`, `mom_rate_percent` | monthly headline CPI inflation path from supported official release cards |
| `stats-gov-sa-unemployment-rate-total-quarterly` | time-series observation | quarterly | `observation_quarter`, `labor_series_code` | `value_percent` | quarterly total-population unemployment path from supported official labor-market release cards |
| `stats-gov-sa-real-gdp-growth-quarterly` | time-series observation | quarterly | `observation_quarter`, `gdp_series_code` | `value_percent` | quarterly headline real GDP growth path from supported official GDP release cards |

`sama-deposits-core` remains intentionally bundled for now. The current SAMA
monthly report surface publishes the core deposit components inside one shared
report payload, so the canonical Wave 3 direction is a bundled monthly dataset
with stable deposit-category fields rather than prematurely splitting it into
separate standalone deposit datasets.

`stats-gov-sa-cpi-headline-monthly` remains intentionally narrow. The current
contract is limited to supported headline CPI release cards on the official
`stats.gov.sa` inflation news surface; it does not yet claim full CPI tables,
index values, or category-level breakdowns.

`stats-gov-sa-unemployment-rate-total-quarterly` also remains intentionally
narrow. The current contract is limited to supported official labor-market
release cards on the `stats.gov.sa` unemployment news surface; it does not yet
claim the full labor-market publication tables, Saudi-only series, demographic
breakdowns, or broader labor database coverage.

`stats-gov-sa-real-gdp-growth-quarterly` also remains intentionally narrow. The
current contract is limited to supported official headline real GDP release
cards on the `stats.gov.sa` gdp news surface; it does not yet claim GDP levels,
activity or expenditure breakdowns, seasonally adjusted quarter-over-quarter
series, or broader national-accounts coverage.
