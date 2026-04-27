# Source Licensing Audit

Status: internal alpha readiness note, not legal advice.

Reviewed for v0.4.0 institutional readiness on 2026-04-27.

This project caches approved public source responses to support MCP/AI access
and deterministic local querying. It does not present itself as the publisher of
the source data, does not remove source attribution, and does not operate a
public republication portal.

## Source Summary

| Source | Published terms URL | Redistribution summary | Project stance |
| --- | --- | --- | --- |
| SAMA | https://www.sama.gov.sa/en-us/pages/termsofuse.aspx | SAMA reserves copyright and allows limited copying, downloading, printing, and brief translated summaries with source reference. The terms prohibit use for personal or commercial gain. | Interpretation pending for redistribution beyond internal operational caching. The project caches SAMA public data for authenticated AI access and must keep source attribution. |
| data.gov.sa | https://data.gov.sa/en/policies/terms | The National Data Platform terms prohibit unlawful, political, malicious, excessive-load, and policy-violating uses. The terms page reviewed here does not by itself state a full redistribution grant. | Interpretation pending. The project treats data.gov.sa as a public open-data source, but does not claim a verified redistribution license beyond internal caching for AI access. |
| GASTAT | https://www.stats.gov.sa/en/web/guest/use-policy | GASTAT states that official statistics and data may be copied, distributed, reused, built upon, derived from, edited, and used commercially or non-commercially when GASTAT is cited as the source. | Internal caching and MCP access are consistent with reuse if attribution is preserved and outputs do not imply GASTAT endorsement. |
| Ministry of Finance | https://www.mof.gov.sa/en/generalservcies/open-data/Pages/Policies.aspx | MoF describes open data as freely available for use and republication, with responsibilities not to distort the data/source, not to use it for prohibited political or illegal purposes, and to cite the MoF portal/source link. The page also includes non-profit-oriented wording, so commercial republication needs review. | Interpretation pending for commercial redistribution. The project caches MoF public data for authenticated AI access, not public republication, and must preserve source context. |

## Operating Constraints

- Keep source names, source locators, and source URLs attached to normalized
  records wherever the current schema supports them.
- Do not imply official endorsement by SAMA, data.gov.sa, GASTAT, MoF, SDAIA, or
  any Saudi government entity.
- Do not use cached data for unlawful, political, discriminatory, or culturally
  prohibited purposes under the relevant source terms.
- Do not make production or public redistribution claims while any source remains
  marked "interpretation pending."
- If the project becomes a public republication service, rerun this audit before
  launch and obtain legal review for every source.
