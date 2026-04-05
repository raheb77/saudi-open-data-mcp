# Ministry of Finance Source Reality Check

Checked against currently visible official surfaces on April 5, 2026.

## Purpose

This note is a pre-expansion source reality check for the first public-finance
families under consideration:

- public debt
- headline budget balance
- total revenue
- total expenditure

It is intentionally read-only and discovery-oriented. It does not add datasets,
contracts, or new source abstractions.

## Direct vs mediated vs platform-view surfaces

### Direct official Ministry of Finance surfaces

These are the clearest official fiscal publication surfaces currently visible for
budget balance, total revenue, and total expenditure:

- quarterly budget performance reports index:
  `https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx`
- annual budget statement news example:
  `https://www.mof.gov.sa/en/MediaCenter/news/Pages/News_02122025.aspx`
- pre-budget statement news example:
  `https://www.mof.gov.sa/en/MediaCenter/news/Pages/News_3092025.aspx`
- mid-year economic and fiscal performance report PDF example:
  `https://www.mof.gov.sa/en/financialreport/2025/Documents/Mid-Bud-E2025.pdf`

Observed pattern:

- the Ministry of Finance publishes fiscal results through budget-statement news
  pages plus budget-performance report pages with attached report files
- the report index pages are stable and yearly, while the underlying report
  files are document assets
- the clearest recurring fiscal publication surface is the quarterly budget
  performance report set

### Direct official debt surfaces

Public debt is currently exposed most clearly through the National Debt
Management Center rather than the main Ministry of Finance portal:

- NDMC reports and statistics page:
  `https://www.ndmc.gov.sa/en/stats/Pages/default.aspx`
- NDMC about page:
  `https://www.ndmc.gov.sa/en/About/Pages/default.aspx`
- annual borrowing plan news example:
  `https://www.ndmc.gov.sa/en/mediacenter/news/Pages/news_01032026.aspx`

Observed pattern:

- NDMC is the direct operational debt-management publication surface
- the stats page exposes a structured debt table with annual history and some
  quarter-end debt points
- debt therefore looks like a real official family, but it is not a clean first
  `mof.gov.sa` ingestion anchor if the next source family is meant to stay
  strictly Ministry-of-Finance-portal-first

### `data.gov.sa` / `open.data.gov.sa` mediated publication surfaces

- the National Data Bank and Open Data Platform remain the mediated public-data
  channel:
  `https://data.gov.sa/en`
- during this phase, exact Ministry of Finance fiscal dataset routes on
  `open.data.gov.sa` were not verified
- multiple direct open-data dataset requests still resolved to request-rejected
  pages during verification

Current conclusion:

- the mediated platform clearly exists as a possible secondary distribution
  channel
- exact fiscal dataset routes for debt, budget balance, revenue, and expenditure
  still need manual validation before any ingestion design should depend on them

### Indicator / view-only surfaces

- `https://datasaudi.sa/en` exposes fiscal indicator views under
  `Public Finances`
- the visible public-finances view summarizes revenues, expenditures, and
  deficit/surplus at annual and quarterly levels

Current conclusion:

- `datasaudi.sa` is useful for discovery, indicator framing, and quick
  cross-checking
- it should not be the first ingestion anchor while official Ministry of
  Finance and NDMC publication surfaces already exist

## Likely ingestion shape by family

### Public debt

- best current direct surface: NDMC reports and statistics page
- likely shape: HTML table with annual debt history plus some quarter-end debt
  observations; supporting debt-management news and borrowing-plan documents
- cadence: at least annual on the long-history table, with some quarter-end
  updates visible
- temporal granularity: year, with limited quarter-end extension
- likely canonical direction:
  - one observation per `observation_period` + `debt_series_code`
  - measures such as `value_sar_bn` and optionally `ratio_to_gdp_percent`
- implementation risk:
  - lower for simple total-outstanding-debt extraction than the budget-report
    PDF path
  - but it is operationally an NDMC source, not a pure `mof.gov.sa` portal
    family

### Headline budget balance

- best current direct surface: Ministry of Finance quarterly budget performance
  reports plus annual/pre-budget statement pages
- likely shape: quarterly report PDF/Word files with headline fiscal tables or
  key-figure summaries
- cadence: quarterly, with annual budget and pre-budget statement context
- temporal granularity: quarter
- likely canonical direction:
  - one observation per `observation_quarter` + `fiscal_series_code`
  - measure such as `value_sar_bn`
  - likely stable series code for headline budget balance / deficit-surplus
- implementation risk:
  - moderate because the recurring surface appears document-oriented rather than
    an obvious stable HTML table
  - still narrow enough if limited to one top-line figure explicitly reported in
    the quarterly report

### Total revenue

- best current direct surface: Ministry of Finance quarterly budget performance
  reports and annual/pre-budget statement materials
- likely shape: top-line table values inside quarterly fiscal reports
- cadence: quarterly
- temporal granularity: quarter
- likely canonical direction:
  - one observation per `observation_quarter` + `fiscal_series_code`
  - measure such as `value_sar_bn`
- implementation risk:
  - moderate
  - top-line total revenue is likely explicit, but the surrounding reports also
    expose oil/non-oil splits that can quickly pressure the first contract to
    widen

### Total expenditure

- best current direct surface: Ministry of Finance quarterly budget performance
  reports and annual/pre-budget statement materials
- likely shape: top-line table values inside quarterly fiscal reports
- cadence: quarterly
- temporal granularity: quarter
- likely canonical direction:
  - one observation per `observation_quarter` + `fiscal_series_code`
  - measure such as `value_sar_bn`
- implementation risk:
  - moderate
  - top-line total expenditure is likely explicit, but the same reports also
    expose current/capital or sector breakdowns that can pressure the first
    contract to broaden too early

## Recommended first Ministry of Finance dataset

Recommendation: start with headline budget balance quarterly from the Ministry
of Finance quarterly budget performance reports.

Why it should come first:

- it keeps the next fiscal family anchored to the main official `mof.gov.sa`
  publication surface rather than switching immediately to NDMC
- it is a single top-line fiscal series, narrower than a broader revenue or
  expenditure package
- it has clear quarterly cadence, which matches the recurring budget
  performance-report publication model
- it provides strong analytical value with a simple canonical direction:
  one quarterly observation, one headline fiscal series, one amount measure
- it avoids early branching into oil/non-oil revenue splits, current/capital
  expenditure splits, or debt-stock sub-breakdowns

## Current decision

- Prefer direct `mof.gov.sa` quarterly budget performance reports as the first
  ingestion anchor for a Ministry of Finance fiscal dataset.
- Treat NDMC as the direct official debt surface, but as a separate practical
  source decision rather than the default first `mof.gov.sa` family.
- Treat `data.gov.sa` / `open.data.gov.sa` as a mediated publication channel
  requiring separate manual validation before use.
- Treat `datasaudi.sa` as a useful fiscal-indicator view layer, not the
  preferred first ingestion source.
