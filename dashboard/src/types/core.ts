// Typed mirrors of the current saudi-open-data-mcp core response shapes.
//
// These types are intentionally narrow and aligned to the structured JSON
// payloads emitted by the existing MCP tools and resources. They are NOT a
// redefinition of core semantics — they are a TypeScript surface that lets
// the dashboard render core results without inventing fields.
//
// Source-of-truth references in the Python core:
//   - tools/query.py        → DatasetQueryResult
//   - tools/preview.py      → DatasetPreviewResult
//   - tools/health.py       → DatasetHealthLookupResult
//   - tools/result_metadata → ResultDataOrigin / ResultDegradationReason
//   - storage/freshness.py  → SnapshotFreshnessResult
//   - observability/summary → ObservabilitySummary

export type ResultDataOrigin =
  | "local_snapshot"
  | "live_refresh"
  | "stale_snapshot";

export type ResultDegradationReason =
  | "normalization_limited"
  | "stale_fallback_after_refresh_failure";

export type DatasetQueryStatus =
  | "missing"
  | "snapshot_missing"
  | "limited"
  | "failed"
  | "success";

export type PreviewStatus =
  | "missing"
  | "record_derivable"
  | "limited"
  | "failed";

export type QueryFailureStage = "snapshot_read" | "normalization";

export type PreviewFailureStage =
  | "lookup"
  | "fetch"
  | "snapshot"
  | "normalization";

export type PreviewResolutionOutcome =
  | "serve_local"
  | "refresh_then_serve"
  | "serve_stale_with_notice"
  | "fail_closed";

export type SnapshotFreshnessStatus = "missing" | "fresh" | "stale" | "unknown";

export type DatasetHealthStatus =
  | "healthy"
  | "degraded"
  | "unavailable"
  | "unknown";

export type UpdateFrequency =
  | "daily"
  | "weekly"
  | "monthly"
  | "quarterly"
  | "annual"
  | "ad_hoc"
  | "unspecified";

export type SourceName = "sama" | "stats-gov-sa" | "mof" | "data-gov-sa";

// ---------- Canonical record ----------

export interface CanonicalRecord {
  dataset_id: string;
  source: SourceName;
  record_index: number;
  fields: Record<string, string | number | boolean | null>;
}

// ---------- Query result ----------

export interface QueryFailure {
  stage: QueryFailureStage;
  error_type: string;
  message: string;
}

export type QueryFilterValue = string | number | boolean | null;

export interface DatasetQueryResult {
  dataset_id: string;
  status: DatasetQueryStatus;
  source: SourceName | null;
  data_origin: ResultDataOrigin | null;
  applied_filters: Record<string, QueryFilterValue>;
  limit: number | null;
  total_records_before_filter: number | null;
  failure_stage: QueryFailureStage | null;
  degradation_reason: ResultDegradationReason | null;
  matched_records: CanonicalRecord[];
  limitations: string[];
  failure: QueryFailure | null;
}

// ---------- Preview result ----------

export interface PreviewFailure {
  stage: PreviewFailureStage;
  error_type: string;
  message: string;
}

export interface DatasetPreviewResult {
  dataset_id: string;
  status: PreviewStatus;
  resolution_outcome: PreviewResolutionOutcome | null;
  data_origin: ResultDataOrigin | null;
  freshness_status: SnapshotFreshnessStatus | null;
  failure_stage: PreviewFailureStage | null;
  degradation_reason: ResultDegradationReason | null;
  snapshot_modified_at: string | null;
  resolution_notice: string | null;
  records: CanonicalRecord[];
  limitations: string[];
  failure: PreviewFailure | null;
}

// ---------- Freshness ----------

export interface SnapshotFreshnessResult {
  source: SourceName;
  dataset_id: string;
  status: SnapshotFreshnessStatus;
  reason:
    | "no_snapshot"
    | "within_expected_window"
    | "exceeded_expected_window"
    | "no_frequency_evidence";
  artifact_present: boolean;
  reference_time: string;
  snapshot_modified_at: string | null;
  snapshot_age_seconds: number | null;
  update_frequency: UpdateFrequency | null;
}

// ---------- Health lookup ----------

export interface DatasetHealthLookupResult {
  dataset_id: string;
  status: "found" | "missing";
  source: SourceName | null;
  health_status: DatasetHealthStatus | null;
  schema_version: string | null;
  caveats: string[];
  known_issues: string[];
  freshness: SnapshotFreshnessResult | null;
}

// ---------- Registry / catalog ----------

export interface DatasetCatalogEntry {
  dataset_id: string;
  source: SourceName;
  title: string;
  update_frequency: UpdateFrequency;
  health_status: DatasetHealthStatus;
}

// ---------- Observability ----------

export interface ObservabilityCounter {
  name: string;
  value: number;
}

export interface ObservabilityCounterGroup {
  name: string;
  summary: string;
  counters: ObservabilityCounter[];
  detail_counters: ObservabilityCounter[];
}

export interface ObservabilitySummary {
  process_local: boolean;
  groups: ObservabilityCounterGroup[];
  raw_counters: Record<string, number>;
  notes: string[];
}

// ---------- Materialization summary ----------

export interface MaterializationSummary {
  last_run_at: string;
  tier_a_success_count: number;
  tier_a_failure_count: number;
  tier_b_success_count: number;
  tier_b_failure_count: number;
}

// ---------- Readiness probe ----------

export interface ReadinessReport {
  status: "ok" | "degraded" | "unavailable";
  ready: boolean;
  scope: string;
  app_name: string;
  checks: Record<string, "ok" | "fail">;
}
