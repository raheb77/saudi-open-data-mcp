# Datasets

## Source Scope

- Current MVP source scope is SAMA plus one narrow `data.gov.sa` pilot dataset and
  one narrow `stats.gov.sa` inflation dataset.
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

`sama-deposits-core` remains intentionally bundled for now. The current SAMA
monthly report surface publishes the core deposit components inside one shared
report payload, so the canonical Wave 3 direction is a bundled monthly dataset
with stable deposit-category fields rather than prematurely splitting it into
separate standalone deposit datasets.

`stats-gov-sa-cpi-headline-monthly` remains intentionally narrow. The current
contract is limited to supported headline CPI release cards on the official
`stats.gov.sa` inflation news surface; it does not yet claim full CPI tables,
index values, or category-level breakdowns.
