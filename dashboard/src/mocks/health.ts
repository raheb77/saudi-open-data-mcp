// Mock health and freshness payloads for the system status page.
// Shapes mirror DatasetHealthLookupResult and SnapshotFreshnessResult.

import type {
  DatasetHealthLookupResult,
  MaterializationSummary,
  ReadinessReport,
} from "../types/core";
import {
  parseDatasetHealthLookupResult,
  parseMaterializationSummary,
  parseReadinessReport,
} from "../lib/runtimeValidation";

const REFERENCE_TIME = "2026-04-05T08:00:00Z";

const MOCK_READINESS: ReadinessReport = {
  status: "ok",
  ready: true,
  scope: "process+config+wiring",
  app_name: "saudi-open-data-mcp",
  checks: {
    config_loaded: "ok",
    runtime_storage_prepared: "ok",
    registry_bootstrapped: "ok",
    fastmcp_app_wired: "ok",
  },
};

const MOCK_HEALTH: DatasetHealthLookupResult[] = [
  {
    dataset_id: "sama-pos-weekly",
    status: "found",
    source: "sama",
    health_status: "healthy",
    schema_version: "1.0.0",
    caveats: [
      "صفحة SAMA الأسبوعية تتغير عرضًا في أسماء الأعمدة بين الإصدارات.",
    ],
    known_issues: [],
    freshness: {
      source: "sama",
      dataset_id: "sama-pos-weekly",
      status: "fresh",
      reason: "within_expected_window",
      artifact_present: true,
      reference_time: REFERENCE_TIME,
      snapshot_modified_at: "2026-03-31T05:00:00Z",
      snapshot_age_seconds: 5 * 86_400,
      update_frequency: "weekly",
    },
  },
  {
    dataset_id: "sama-exchange-rates-current",
    status: "found",
    source: "sama",
    health_status: "healthy",
    schema_version: "1.0.0",
    caveats: [],
    known_issues: [],
    freshness: {
      source: "sama",
      dataset_id: "sama-exchange-rates-current",
      status: "fresh",
      reason: "within_expected_window",
      artifact_present: true,
      reference_time: REFERENCE_TIME,
      snapshot_modified_at: "2026-04-04T20:00:00Z",
      snapshot_age_seconds: 12 * 3600,
      update_frequency: "daily",
    },
  },
  {
    dataset_id: "sama-repo-rate",
    status: "found",
    source: "sama",
    health_status: "healthy",
    schema_version: "1.0.0",
    caveats: ["السعر يتغير فقط عند قرار رسمي."],
    known_issues: [],
    freshness: {
      source: "sama",
      dataset_id: "sama-repo-rate",
      status: "unknown",
      reason: "no_frequency_evidence",
      artifact_present: true,
      reference_time: REFERENCE_TIME,
      snapshot_modified_at: "2025-09-19T11:00:00Z",
      snapshot_age_seconds: 199 * 86_400,
      update_frequency: "ad_hoc",
    },
  },
  {
    dataset_id: "stats-gov-sa-cpi-headline-monthly",
    status: "found",
    source: "stats-gov-sa",
    health_status: "degraded",
    schema_version: "1.0.0",
    caveats: ["البطاقات الإخبارية تتغير في صياغة العنوان أحيانًا."],
    known_issues: [
      "بعض البطاقات الجزئية تُؤدي إلى استخراج محدود (limited).",
    ],
    freshness: {
      source: "stats-gov-sa",
      dataset_id: "stats-gov-sa-cpi-headline-monthly",
      status: "stale",
      reason: "exceeded_expected_window",
      artifact_present: true,
      reference_time: REFERENCE_TIME,
      snapshot_modified_at: "2026-02-12T08:00:00Z",
      snapshot_age_seconds: 53 * 86_400,
      update_frequency: "monthly",
    },
  },
  {
    dataset_id: "stats-gov-sa-real-gdp-growth-quarterly",
    status: "found",
    source: "stats-gov-sa",
    health_status: "healthy",
    schema_version: "1.0.0",
    caveats: [],
    known_issues: [],
    freshness: {
      source: "stats-gov-sa",
      dataset_id: "stats-gov-sa-real-gdp-growth-quarterly",
      status: "fresh",
      reason: "within_expected_window",
      artifact_present: true,
      reference_time: REFERENCE_TIME,
      snapshot_modified_at: "2026-03-15T09:00:00Z",
      snapshot_age_seconds: 21 * 86_400,
      update_frequency: "quarterly",
    },
  },
  {
    dataset_id: "mof-budget-balance-quarterly",
    status: "found",
    source: "mof",
    health_status: "healthy",
    schema_version: "1.0.0",
    caveats: [
      "هذا العقد يغطي الرصيد الإجمالي فقط، وليس بنود الإيرادات أو المصروفات.",
    ],
    known_issues: [],
    freshness: {
      source: "mof",
      dataset_id: "mof-budget-balance-quarterly",
      status: "fresh",
      reason: "within_expected_window",
      artifact_present: true,
      reference_time: REFERENCE_TIME,
      snapshot_modified_at: "2026-03-20T08:00:00Z",
      snapshot_age_seconds: 16 * 86_400,
      update_frequency: "quarterly",
    },
  },
];

const MOCK_MATERIALIZATION_SUMMARY: MaterializationSummary = {
  last_run_at: "2026-04-05T03:00:00Z",
  tier_a_success_count: 5,
  tier_a_failure_count: 0,
  tier_b_success_count: 0,
  tier_b_failure_count: 0,
};

export function getReadinessReport(): ReadinessReport {
  return parseReadinessReport(MOCK_READINESS);
}

export function getHealthEntries(): DatasetHealthLookupResult[] {
  return MOCK_HEALTH.map((entry) => parseDatasetHealthLookupResult(entry));
}

export function findHealthById(
  dataset_id: string,
): DatasetHealthLookupResult | undefined {
  const match = MOCK_HEALTH.find((entry) => entry.dataset_id === dataset_id);
  return match ? parseDatasetHealthLookupResult(match) : undefined;
}

export function getMaterializationSummary(): MaterializationSummary {
  return parseMaterializationSummary(MOCK_MATERIALIZATION_SUMMARY);
}
