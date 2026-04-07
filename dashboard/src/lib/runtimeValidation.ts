import type {
  CanonicalRecord,
  DatasetCatalogSummary,
  DatasetHealthLookupResult,
  DatasetPreviewResult,
  DatasetQueryResult,
  DatasetCatalogEntry,
  DatasetHealthStatus,
  MaterializationSummary,
  ObservabilityCounterGroup,
  ObservabilitySummary,
  PreviewFailureStage,
  PreviewResolutionOutcome,
  PreviewStatus,
  QueryFailureStage,
  ReadinessReport,
  ResultDataOrigin,
  ResultDegradationReason,
  SnapshotFreshnessResult,
  SnapshotFreshnessStatus,
  SourceName,
  UpdateFrequency,
} from "../types/core";

function fail(context: string, message: string): never {
  throw new Error(`Invalid ${context} payload: ${message}`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function expectRecord(value: unknown, context: string): Record<string, unknown> {
  if (!isRecord(value)) {
    fail(context, "expected object");
  }
  return value;
}

function expectString(value: unknown, context: string): string {
  if (typeof value !== "string") {
    fail(context, "expected string");
  }
  return value;
}

function expectNullableString(value: unknown, context: string): string | null {
  if (value === null) return null;
  return expectString(value, context);
}

function expectNumber(value: unknown, context: string): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    fail(context, "expected number");
  }
  return value;
}

function expectNullableNumber(value: unknown, context: string): number | null {
  if (value === null) return null;
  return expectNumber(value, context);
}

function expectBoolean(value: unknown, context: string): boolean {
  if (typeof value !== "boolean") {
    fail(context, "expected boolean");
  }
  return value;
}

function expectNullableRecord(
  value: unknown,
  context: string,
): Record<string, unknown> | null {
  if (value === null) return null;
  return expectRecord(value, context);
}

function expectStringArray(value: unknown, context: string): string[] {
  if (!Array.isArray(value) || !value.every((entry) => typeof entry === "string")) {
    fail(context, "expected string[]");
  }
  return value;
}

function expectOneOf<T extends string>(
  value: unknown,
  allowed: readonly T[],
  context: string,
): T {
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    fail(context, `expected one of: ${allowed.join(", ")}`);
  }
  return value as T;
}

function expectNullableOneOf<T extends string>(
  value: unknown,
  allowed: readonly T[],
  context: string,
): T | null {
  if (value === null) return null;
  return expectOneOf(value, allowed, context);
}

function parseCanonicalRecord(value: unknown): CanonicalRecord {
  const record = expectRecord(value, "CanonicalRecord");
  const rawFields = expectRecord(record.fields, "CanonicalRecord.fields");
  for (const [key, entry] of Object.entries(rawFields)) {
    const valid =
      typeof entry === "string" ||
      typeof entry === "number" ||
      typeof entry === "boolean" ||
      entry === null;
    if (!valid) {
      fail(`CanonicalRecord.fields.${key}`, "expected scalar field value");
    }
  }
  return {
    dataset_id: expectString(record.dataset_id, "CanonicalRecord.dataset_id"),
    source: expectOneOf(
      record.source,
      ["sama", "stats-gov-sa", "mof", "data-gov-sa"] as const,
      "CanonicalRecord.source",
    ),
    record_index: expectNumber(record.record_index, "CanonicalRecord.record_index"),
    fields: rawFields as CanonicalRecord["fields"],
  };
}

export function parseDatasetQueryResult(value: unknown): DatasetQueryResult {
  const result = expectRecord(value, "DatasetQueryResult");
  const appliedFilters = expectRecord(
    result.applied_filters,
    "DatasetQueryResult.applied_filters",
  );
  const matchedRecords = result.matched_records;
  if (!Array.isArray(matchedRecords)) {
    fail("DatasetQueryResult.matched_records", "expected CanonicalRecord[]");
  }
  const failure = expectNullableRecord(result.failure, "DatasetQueryResult.failure");
  return {
    dataset_id: expectString(result.dataset_id, "DatasetQueryResult.dataset_id"),
    status: expectOneOf(
      result.status,
      ["missing", "snapshot_missing", "limited", "failed", "success"] as const,
      "DatasetQueryResult.status",
    ),
    source: expectNullableOneOf(
      result.source,
      ["sama", "stats-gov-sa", "mof", "data-gov-sa"] as const,
      "DatasetQueryResult.source",
    ),
    data_origin: expectNullableOneOf(
      result.data_origin,
      ["local_snapshot", "live_refresh", "stale_snapshot"] as const,
      "DatasetQueryResult.data_origin",
    ),
    applied_filters: appliedFilters as DatasetQueryResult["applied_filters"],
    limit: expectNullableNumber(result.limit, "DatasetQueryResult.limit"),
    total_records_before_filter: expectNullableNumber(
      result.total_records_before_filter,
      "DatasetQueryResult.total_records_before_filter",
    ),
    failure_stage: expectNullableOneOf(
      result.failure_stage,
      ["snapshot_read", "normalization"] as const,
      "DatasetQueryResult.failure_stage",
    ) as QueryFailureStage | null,
    degradation_reason: expectNullableOneOf(
      result.degradation_reason,
      ["normalization_limited", "stale_fallback_after_refresh_failure"] as const,
      "DatasetQueryResult.degradation_reason",
    ) as ResultDegradationReason | null,
    matched_records: matchedRecords.map(parseCanonicalRecord),
    limitations: expectStringArray(
      result.limitations,
      "DatasetQueryResult.limitations",
    ),
    failure: failure
      ? {
          stage: expectOneOf(
            failure.stage,
            ["snapshot_read", "normalization"] as const,
            "DatasetQueryResult.failure.stage",
          ) as QueryFailureStage,
          error_type: expectString(
            failure.error_type,
            "DatasetQueryResult.failure.error_type",
          ),
          message: expectString(
            failure.message,
            "DatasetQueryResult.failure.message",
          ),
        }
      : null,
  };
}

export function parseDatasetPreviewResult(value: unknown): DatasetPreviewResult {
  const result = expectRecord(value, "DatasetPreviewResult");
  const records = result.records;
  if (!Array.isArray(records)) {
    fail("DatasetPreviewResult.records", "expected CanonicalRecord[]");
  }
  const failure = expectNullableRecord(result.failure, "DatasetPreviewResult.failure");
  return {
    dataset_id: expectString(result.dataset_id, "DatasetPreviewResult.dataset_id"),
    status: expectOneOf(
      result.status,
      ["missing", "record_derivable", "limited", "failed"] as const,
      "DatasetPreviewResult.status",
    ) as PreviewStatus,
    resolution_outcome: expectNullableOneOf(
      result.resolution_outcome,
      [
        "serve_local",
        "refresh_then_serve",
        "serve_stale_with_notice",
        "fail_closed",
      ] as const,
      "DatasetPreviewResult.resolution_outcome",
    ) as PreviewResolutionOutcome | null,
    data_origin: expectNullableOneOf(
      result.data_origin,
      ["local_snapshot", "live_refresh", "stale_snapshot"] as const,
      "DatasetPreviewResult.data_origin",
    ) as ResultDataOrigin | null,
    freshness_status: expectNullableOneOf(
      result.freshness_status,
      ["missing", "fresh", "stale", "unknown"] as const,
      "DatasetPreviewResult.freshness_status",
    ) as SnapshotFreshnessStatus | null,
    failure_stage: expectNullableOneOf(
      result.failure_stage,
      ["lookup", "fetch", "snapshot", "normalization"] as const,
      "DatasetPreviewResult.failure_stage",
    ) as PreviewFailureStage | null,
    degradation_reason: expectNullableOneOf(
      result.degradation_reason,
      ["normalization_limited", "stale_fallback_after_refresh_failure"] as const,
      "DatasetPreviewResult.degradation_reason",
    ) as ResultDegradationReason | null,
    snapshot_modified_at: expectNullableString(
      result.snapshot_modified_at,
      "DatasetPreviewResult.snapshot_modified_at",
    ),
    resolution_notice: expectNullableString(
      result.resolution_notice,
      "DatasetPreviewResult.resolution_notice",
    ),
    records: records.map(parseCanonicalRecord),
    limitations: expectStringArray(
      result.limitations,
      "DatasetPreviewResult.limitations",
    ),
    failure: failure
      ? {
          stage: expectOneOf(
            failure.stage,
            ["lookup", "fetch", "snapshot", "normalization"] as const,
            "DatasetPreviewResult.failure.stage",
          ) as PreviewFailureStage,
          error_type: expectString(
            failure.error_type,
            "DatasetPreviewResult.failure.error_type",
          ),
          message: expectString(
            failure.message,
            "DatasetPreviewResult.failure.message",
          ),
        }
      : null,
  };
}

export function parseDatasetCatalogSummary(value: unknown): DatasetCatalogSummary {
  const summary = expectRecord(value, "DatasetCatalogSummary");
  const datasets = summary.datasets;
  if (!Array.isArray(datasets)) {
    fail("DatasetCatalogSummary.datasets", "expected DatasetCatalogEntry[]");
  }
  const parsedDatasets = datasets.map((entry, index) =>
    parseDatasetCatalogEntry(entry, `DatasetCatalogSummary.datasets.${index}`),
  );
  const datasetCount = expectNumber(
    summary.dataset_count,
    "DatasetCatalogSummary.dataset_count",
  );
  if (datasetCount !== parsedDatasets.length) {
    fail(
      "DatasetCatalogSummary.dataset_count",
      "must match datasets length",
    );
  }
  return {
    dataset_count: datasetCount,
    datasets: parsedDatasets,
  };
}

function parseDatasetCatalogEntry(
  value: unknown,
  context: string,
): DatasetCatalogEntry {
  const entry = expectRecord(value, context);
  return {
    dataset_id: expectString(entry.dataset_id, `${context}.dataset_id`),
    source: expectOneOf(
      entry.source,
      ["sama", "stats-gov-sa", "mof", "data-gov-sa"] as const,
      `${context}.source`,
    ) as SourceName,
    title: expectString(entry.title, `${context}.title`),
    update_frequency: expectOneOf(
      entry.update_frequency,
      [
        "daily",
        "weekly",
        "monthly",
        "quarterly",
        "annual",
        "ad_hoc",
        "unspecified",
      ] as const,
      `${context}.update_frequency`,
    ) as UpdateFrequency,
    health_status: expectOneOf(
      entry.health_status,
      ["healthy", "degraded", "unavailable", "unknown"] as const,
      `${context}.health_status`,
    ) as DatasetHealthStatus,
  };
}

function parseIso8601DurationToSeconds(
  value: string | null,
  context: string,
): number | null {
  if (value === null) {
    return null;
  }
  const match = value.match(
    /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$/,
  );
  if (!match) {
    fail(context, "expected ISO-8601 duration like P5DT2H");
  }
  const days = Number(match[1] ?? 0);
  const hours = Number(match[2] ?? 0);
  const minutes = Number(match[3] ?? 0);
  const seconds = Number(match[4] ?? 0);
  return days * 86_400 + hours * 3600 + minutes * 60 + seconds;
}

function parseSnapshotFreshnessResult(value: unknown): SnapshotFreshnessResult {
  const freshness = expectRecord(value, "SnapshotFreshnessResult");
  const snapshotAgeValue =
    freshness.snapshot_age_seconds !== undefined
      ? expectNullableNumber(
          freshness.snapshot_age_seconds,
          "SnapshotFreshnessResult.snapshot_age_seconds",
        )
      : parseIso8601DurationToSeconds(
          expectNullableString(
            freshness.snapshot_age ?? null,
            "SnapshotFreshnessResult.snapshot_age",
          ),
          "SnapshotFreshnessResult.snapshot_age",
        );
  return {
    source: expectOneOf(
      freshness.source,
      ["sama", "stats-gov-sa", "mof", "data-gov-sa"] as const,
      "SnapshotFreshnessResult.source",
    ) as SourceName,
    dataset_id: expectString(
      freshness.dataset_id,
      "SnapshotFreshnessResult.dataset_id",
    ),
    status: expectOneOf(
      freshness.status,
      ["missing", "fresh", "stale", "unknown"] as const,
      "SnapshotFreshnessResult.status",
    ) as SnapshotFreshnessStatus,
    reason: expectOneOf(
      freshness.reason,
      [
        "no_snapshot",
        "within_expected_window",
        "exceeded_expected_window",
        "no_frequency_evidence",
      ] as const,
      "SnapshotFreshnessResult.reason",
    ),
    artifact_present: expectBoolean(
      freshness.artifact_present,
      "SnapshotFreshnessResult.artifact_present",
    ),
    reference_time: expectString(
      freshness.reference_time,
      "SnapshotFreshnessResult.reference_time",
    ),
    snapshot_modified_at: expectNullableString(
      freshness.snapshot_modified_at,
      "SnapshotFreshnessResult.snapshot_modified_at",
    ),
    snapshot_age_seconds: snapshotAgeValue,
    update_frequency: expectNullableOneOf(
      freshness.update_frequency,
      [
        "daily",
        "weekly",
        "monthly",
        "quarterly",
        "annual",
        "ad_hoc",
        "unspecified",
      ] as const,
      "SnapshotFreshnessResult.update_frequency",
    ) as UpdateFrequency | null,
  };
}

export function parseDatasetHealthLookupResult(
  value: unknown,
  options: {
    sourceFallback?: SourceName | null;
  } = {},
): DatasetHealthLookupResult {
  const health = expectRecord(value, "DatasetHealthLookupResult");
  const sourceValue =
    health.source === undefined ? options.sourceFallback ?? null : health.source;
  return {
    dataset_id: expectString(
      health.dataset_id,
      "DatasetHealthLookupResult.dataset_id",
    ),
    status: expectOneOf(
      health.status,
      ["found", "missing"] as const,
      "DatasetHealthLookupResult.status",
    ),
    source: expectNullableOneOf(
      sourceValue,
      ["sama", "stats-gov-sa", "mof", "data-gov-sa"] as const,
      "DatasetHealthLookupResult.source",
    ) as SourceName | null,
    health_status: expectNullableOneOf(
      health.health_status,
      ["healthy", "degraded", "unavailable", "unknown"] as const,
      "DatasetHealthLookupResult.health_status",
    ) as DatasetHealthStatus | null,
    schema_version: expectNullableString(
      health.schema_version,
      "DatasetHealthLookupResult.schema_version",
    ),
    caveats: expectStringArray(health.caveats, "DatasetHealthLookupResult.caveats"),
    known_issues: expectStringArray(
      health.known_issues,
      "DatasetHealthLookupResult.known_issues",
    ),
    freshness:
      health.freshness === null
        ? null
        : parseSnapshotFreshnessResult(health.freshness),
  };
}

export function parseReadinessReport(value: unknown): ReadinessReport {
  const report = expectRecord(value, "ReadinessReport");
  const checks = expectRecord(report.checks, "ReadinessReport.checks");
  for (const [key, entry] of Object.entries(checks)) {
    if (
      typeof entry !== "boolean" &&
      (typeof entry !== "string" || !["ok", "fail"].includes(entry))
    ) {
      fail(
        `ReadinessReport.checks.${key}`,
        "expected boolean or one of: ok, fail",
      );
    }
  }
  return {
    status: expectOneOf(
      report.status,
      ["ready", "ok", "degraded", "unavailable"] as const,
      "ReadinessReport.status",
    ),
    ready: expectBoolean(report.ready, "ReadinessReport.ready"),
    scope: expectString(report.scope, "ReadinessReport.scope"),
    app_name: expectString(report.app_name, "ReadinessReport.app_name"),
    checks: checks as ReadinessReport["checks"],
  };
}

function parseObservabilityCounterGroup(
  value: unknown,
  context: string,
): ObservabilityCounterGroup {
  const group = expectRecord(value, context);
  const counters = group.counters;
  const detailCounters = group.detail_counters;
  if (!Array.isArray(counters) || !Array.isArray(detailCounters)) {
    fail(context, "expected counters arrays");
  }
  const parseCounter = (entry: unknown, counterContext: string) => {
    const counter = expectRecord(entry, counterContext);
    return {
      name: expectString(counter.name, `${counterContext}.name`),
      value: expectNumber(counter.value, `${counterContext}.value`),
    };
  };
  return {
    name: expectString(group.name, `${context}.name`),
    summary: expectString(group.summary, `${context}.summary`),
    counters: counters.map((entry, index) =>
      parseCounter(entry, `${context}.counters.${index}`),
    ),
    detail_counters: detailCounters.map((entry, index) =>
      parseCounter(entry, `${context}.detail_counters.${index}`),
    ),
  };
}

export function parseObservabilitySummary(value: unknown): ObservabilitySummary {
  const summary = expectRecord(value, "ObservabilitySummary");
  const groups = summary.groups;
  const rawCounters = expectRecord(
    summary.raw_counters,
    "ObservabilitySummary.raw_counters",
  );
  if (!Array.isArray(groups)) {
    fail("ObservabilitySummary.groups", "expected group[]");
  }
  return {
    process_local: expectBoolean(
      summary.process_local,
      "ObservabilitySummary.process_local",
    ),
    groups: groups.map((entry, index) =>
      parseObservabilityCounterGroup(entry, `ObservabilitySummary.groups.${index}`),
    ),
    raw_counters: rawCounters as ObservabilitySummary["raw_counters"],
    notes: expectStringArray(summary.notes, "ObservabilitySummary.notes"),
  };
}

export function parseMaterializationSummary(
  value: unknown,
): MaterializationSummary {
  const summary = expectRecord(value, "MaterializationSummary");
  return {
    last_run_at: expectString(
      summary.last_run_at,
      "MaterializationSummary.last_run_at",
    ),
    tier_a_success_count: expectNumber(
      summary.tier_a_success_count,
      "MaterializationSummary.tier_a_success_count",
    ),
    tier_a_failure_count: expectNumber(
      summary.tier_a_failure_count,
      "MaterializationSummary.tier_a_failure_count",
    ),
    tier_b_success_count: expectNumber(
      summary.tier_b_success_count,
      "MaterializationSummary.tier_b_success_count",
    ),
    tier_b_failure_count: expectNumber(
      summary.tier_b_failure_count,
      "MaterializationSummary.tier_b_failure_count",
    ),
  };
}
