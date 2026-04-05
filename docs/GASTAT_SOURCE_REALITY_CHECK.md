# GASTAT Source Reality Check

Checked against currently visible official surfaces on April 5, 2026.

## Purpose

This note is a pre-expansion source reality check for the first non-SAMA
macroeconomic families under consideration:

- inflation
- labor market / unemployment
- GDP

It is intentionally read-only and discovery-oriented. It does not add datasets,
contracts, or new source abstractions.

## Direct vs mediated vs platform-view surfaces

### `stats.gov.sa` direct source surfaces

These remain the primary authoritative source surfaces for the target families.

- Inflation:
  - survey/product page: `https://stats.gov.sa/en/w/cpi-1`
  - methodology page: `https://www.stats.gov.sa/en/w/methodology-and-quality-report-of-consumer-price-index`
  - current monthly news/release example: `https://stats.gov.sa/en/w/news/155`
- Labor market / unemployment:
  - survey/product page: `https://www.stats.gov.sa/en/w/lfs-1`
  - methodology page: `https://www.stats.gov.sa/w/methodology-and-quality-report-for-labor-market-statistics`
  - quarterly release example: `https://stats.gov.sa/en/w/news/93`
- GDP:
  - quarterly methodology page: `https://www.stats.gov.sa/en/w/methodology-and-quality-report-for-quarterly-gdp-statistics`
  - annual national accounts page: `https://www.stats.gov.sa/en/w/annual-national-accounts`
  - quarterly release example: `https://www.stats.gov.sa/en/w/news/71`
  - direct publication/PDF example:
    `https://www.stats.gov.sa/documents/20117/2435259/GDP+FQ12025E_v3.pdf/54ea3129-6610-97cb-d187-0cd498474508`

Observed pattern:

- `stats.gov.sa` exposes product/methodology pages, news releases, and
  publication documents.
- Methodology pages consistently state that results are also published in the
  GASTAT statistical database.
- Direct publication document URLs appear to be versioned and unstable, so they
  should not be treated as the canonical long-term locator when a stable product
  or methodology page exists.

### `data.gov.sa` / `open.data.gov.sa` mediated surfaces

- The National Data Bank homepage confirms that the public Open Data Platform is
  the mediated publication surface for public datasets:
  `https://data.gov.sa/en`
- During this phase, direct browsing to `https://open.data.gov.sa/en` was
  rejected, so exact inflation / labor / GDP dataset pages were not verified.
- Current conclusion:
  - the open-data platform clearly exists as a mediated publication channel
  - exact GASTAT dataset routes for the three target families still need manual
    validation before any ingestion design should depend on them

This means the open-data platform should currently be treated as a possible
secondary distribution surface, not the primary ingestion anchor.

### `datasaudi.sa` platform views

- `https://datasaudi.sa/en` clearly exposes all three target families as
  interactive indicator views:
  - GDP
  - CPI / inflation
  - unemployment / labor indicators
- The site presents cross-source analytical views and current indicators rather
  than acting like the primary publication surface.
- Current conclusion:
  - `datasaudi.sa` is useful for discovery and indicator framing
  - it is not the preferred first ingestion surface when authoritative GASTAT
    publication pages already exist

## Likely ingestion shape by family

### Inflation

- best current source surface: `stats.gov.sa` CPI product/release pages
- likely shape: monthly table/publication with category and region cuts
- cadence: monthly
- temporal granularity: month
- likely canonical direction:
  - one monthly observation per `observation_month` + `series_code`
  - measures such as `index_value`, `yoy_rate_percent`, `mom_rate_percent`
  - optional dimensions such as `expenditure_category_code` and `region_code`
- implementation risk:
  - lower than GDP and labor because the core series is simpler and the cadence
    is regular

### Labor market / unemployment

- best current source surface: `stats.gov.sa` labor market publication backed by
  Labor Force Survey plus administrative records
- likely shape: quarterly bulletin/publication with many cuts
- cadence: quarterly
- temporal granularity: quarter
- likely canonical direction:
  - one quarterly observation per `observation_quarter` + `indicator_code` +
    demographic cut
  - measures such as `rate_percent`, `population_count`, `participation_rate_percent`
- implementation risk:
  - materially higher because the publication mixes survey and administrative
    concepts, and the number of valid cuts is much larger

### GDP

- best current source surface: `stats.gov.sa` quarterly GDP publication plus
  annual national accounts
- likely shape: quarterly and annual publication tables, flash estimates, and
  versioned PDF/publication assets
- cadence: quarterly for the first likely implementation path
- temporal granularity: quarter
- likely canonical direction:
  - one quarterly observation per `observation_quarter` + `gdp_measure_code` +
    `breakdown_code`
  - measures such as `value_sar_mn`, `yoy_growth_percent`, `qoq_growth_percent`
- implementation risk:
  - highest of the three because of flash vs final releases, revision policy,
    real vs nominal vs seasonally adjusted measures, and activity vs expenditure
    breakdowns

## Recommended first GASTAT family

Recommendation: start with inflation.

Why inflation should come first:

- the direct official source surface is clearer and more regular
- monthly cadence gives faster feedback on freshness and hybrid behavior
- the likely canonical model is narrower and easier to review than labor or GDP
- it offers immediate analytical value with limited semantic branching
- it avoids the flash/final revision complexity of GDP and the high-dimensional
  demographic branching of labor statistics

## Current decision

- Prefer `stats.gov.sa` direct publication surfaces as the first ingestion anchor
  for the target GASTAT macro families.
- Treat `data.gov.sa` / `open.data.gov.sa` as a mediated publication channel
  requiring separate manual validation before use.
- Treat `datasaudi.sa` as a useful analytical/view layer, not the preferred
  first ingestion source.
