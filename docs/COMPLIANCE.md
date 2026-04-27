# Compliance Stance: PDPL and Public Open Data

Status: internal alpha readiness note, not legal advice.

Reviewed for v0.4.0 institutional readiness on 2026-04-27.

## Data Scope

`saudi-open-data-mcp` is designed for public Saudi government open data only.
The approved source scope is SAMA, data.gov.sa, GASTAT, and Ministry of
Finance public/open data surfaces. The runtime stores:

- source snapshots from approved public URLs
- normalized public statistical/economic records
- registry metadata, coverage metadata, health metadata, and freshness evidence
- structured audit events for important MCP operations

The project does not intentionally collect, solicit, normalize, enrich, or
profile personal data. It does not require end-user names, national IDs, phone
numbers, addresses, account data, health data, credit data, biometrics, or other
PDPL-regulated personal data as source input.

If an upstream public dataset unexpectedly contains identifiable personal data,
that dataset is outside the intended project contract and must not be promoted
as supported without a separate legal and privacy review.

## PDPL Articles Relevant to This Project

Primary source: Saudi Data & AI Authority Personal Data Protection Law page:
https://dgp.sdaia.gov.sa/wps/portal/pdp/knowledgecenter/details/PDPL/

- Article 1 defines Personal Data, Processing, Collection, Disclosure, Transfer,
  Publishing, Sensitive Data, Health Data, Credit Data, Controller, and Processor.
  This project is positioned to avoid Personal Data and Sensitive Data entirely.
- Article 2 defines the PDPL scope for processing Personal Data related to
  individuals. The current project scope is public open data, not identifiable
  individual records.
- Article 4 defines data subject rights, including the right to know the legal
  basis and purpose of personal data collection, access, portability, correction,
  and destruction. These rights become relevant if a future feature collects or
  processes personal data.
- Article 10 addresses collection from sources other than the data subject,
  including publicly available sources, subject to the Law and Regulations. The
  project still treats "publicly available" as insufficient by itself for adding
  identifiable records to the supported dataset catalog.
- Article 11 requires collection purpose alignment, lawful and secure collection
  methods, minimization, and destruction when personal data is no longer needed.
  The project minimizes by accepting only approved public dataset surfaces and
  public operational metadata.
- Articles 12 and 13 require transparency about personal data collection and
  disclosure when collecting personal data directly from data subjects. The MCP
  tools do not collect personal data directly from users.
- Article 15 covers disclosure of Personal Data, including cases involving
  publicly available sources, subject to the Law and Regulations. The project
  does not disclose personal data as an MCP product feature.
- Article 18 covers destruction or retention after the purpose of collection
  ends. Runtime state is limited to public snapshots and operational metadata;
  any future personal data path would need a retention and deletion rule before
  launch.
- Article 19 requires organizational, administrative, and technical measures to
  protect Personal Data, including during transfer. Even though the current
  project avoids personal data, it applies bearer auth for HTTP transport and
  avoids MCP-visible filesystem path leakage.
- Article 20 covers breach notification duties for personal data breaches. The
  current audit posture is designed not to log personal data or bearer tokens,
  but any future personal data handling would need incident response procedures.
- Article 27 permits certain scientific, research, or statistical processing
  without consent when the data does not identify the data subject or identity is
  destroyed before disclosure, subject to controls. The current catalog exposes
  public aggregate statistical/economic data, not individual-level records.
- Article 29 governs transfer or disclosure of Personal Data outside the Kingdom.
  The project does not transfer personal data. Deployments outside Saudi Arabia
  should still treat any future personal-data support as requiring a separate
  cross-border transfer assessment.

## What The Project Does Not Do

- No PII collection from MCP users.
- No PII ingestion as a supported dataset contract.
- No profiling, scoring, segmentation, or behavioral inference about people.
- No advertising, marketing, or personal communication workflows.
- No joining across sources to identify individuals.
- No cross-border transfer of personal data. Public open data may be fetched,
  cached, and served according to source terms and deployment policy.
- No claim that source licensing approval has been granted where terms are
  unclear.

## Audit Logging Posture

Audit logging is structured and operation-scoped. It is intended to help an
operator answer what internal MCP operation ran, against which dataset, under
which authenticated role/capability context, and with what outcome.

Audit logs may capture:

- operation name and result status
- dataset_id, source, coverage status, freshness status, and resolution outcome
- HTTP/MCP request context such as transport, path, request_id, and RPC request id
- actor type, actor role, actor capabilities, and a short bearer-token
  fingerprint
- error category or degradation reason for supported operations

Audit logs must not capture:

- raw bearer tokens
- raw upstream payload bodies
- normalized record payloads beyond high-level counts/statuses
- personal identifiers, contact details, or user-submitted personal data
- local filesystem paths exposed to MCP clients

The audit log is process-local structured logging, not a regulated evidence
archive. Operators remain responsible for log retention, access control, and
export policy in their deployment environment.
