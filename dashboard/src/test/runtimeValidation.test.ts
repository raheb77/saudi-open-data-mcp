import { describe, expect, it } from "vitest";
import {
  parseDatasetCatalogSummary,
  parseDatasetHealthLookupResult,
  parseDatasetPreviewResult,
  parseDatasetQueryResult,
  parseReadinessReport,
} from "../lib/runtimeValidation";

describe("runtimeValidation", () => {
  it("accepts a valid query result payload", () => {
    const result = parseDatasetQueryResult({
      dataset_id: "sama-pos-weekly",
      status: "success",
      source: "sama",
      data_origin: "local_snapshot",
      applied_filters: {},
      limit: 10,
      total_records_before_filter: 1,
      failure_stage: null,
      degradation_reason: null,
      matched_records: [],
      limitations: [],
      failure: null,
    });

    expect(result.status).toBe("success");
  });

  it("rejects a query result payload whose applied filters are not scalar values", () => {
    expect(() =>
      parseDatasetQueryResult({
        dataset_id: "sama-pos-weekly",
        status: "success",
        source: "sama",
        data_origin: "local_snapshot",
        applied_filters: {
          observation_quarter: { from: "2025-Q1" },
        },
        limit: 10,
        total_records_before_filter: 1,
        failure_stage: null,
        degradation_reason: null,
        matched_records: [],
        limitations: [],
        failure: null,
      }),
    ).toThrow(/Invalid DatasetQueryResult\.applied_filters\.observation_quarter payload/);
  });

  it("rejects an invalid preview payload", () => {
    expect(() =>
      parseDatasetPreviewResult({
        dataset_id: "stats-gov-sa-cpi-headline-monthly",
        status: "success",
        coverage_status: "queryable",
      }),
    ).toThrow(/Invalid DatasetPreviewResult/);
  });

  it("rejects an invalid health payload", () => {
    expect(() =>
      parseDatasetHealthLookupResult({
        dataset_id: "stats-gov-sa-cpi-headline-monthly",
        status: "found",
        health_status: "healthy",
        coverage_status: "queryable",
        schema_version: "1.0.0",
        caveats: [],
        known_issues: [],
        freshness: {
          source: "stats-gov-sa",
          dataset_id: "stats-gov-sa-cpi-headline-monthly",
          status: "fresh",
          reason: "within_expected_window",
          artifact_present: "yes",
          reference_time: "2026-04-05T08:00:00Z",
          snapshot_modified_at: null,
          snapshot_age: null,
          update_frequency: "monthly",
        },
      }, { sourceFallback: "stats-gov-sa" }),
    ).toThrow(/Invalid SnapshotFreshnessResult\.artifact_present payload/);
  });

  it("accepts a live health payload without a top-level source", () => {
    const result = parseDatasetHealthLookupResult(
      {
        dataset_id: "sama-pos-weekly",
        status: "found",
        health_status: "unknown",
        coverage_status: "queryable",
        schema_version: "0.1.0",
        caveats: [],
        known_issues: [],
        freshness: {
          source: "sama",
          dataset_id: "sama-pos-weekly",
          status: "stale",
          reason: "exceeded_expected_window",
          artifact_present: true,
          reference_time: "2026-04-07T10:00:00Z",
          snapshot_modified_at: "2026-04-01T10:00:00Z",
          snapshot_age: "P6DT2H",
          update_frequency: "weekly",
        },
      },
      { sourceFallback: "sama" },
    );

    expect(result.source).toBe("sama");
    expect(result.freshness?.snapshot_age_seconds).toBe(525600);
  });

  it("accepts the live readiness payload shape", () => {
    const report = parseReadinessReport({
      status: "ready",
      ready: true,
      scope: "internal_runtime_readiness",
      app_name: "saudi-open-data-mcp",
      checks: {
        process_running: true,
        startup_validated: true,
        runtime_storage_prepared: true,
        app_wiring_completed: true,
      },
    });

    expect(report.status).toBe("ready");
    expect(report.checks.process_running).toBe(true);
  });

  it("accepts a live catalog summary payload", () => {
    const catalog = parseDatasetCatalogSummary({
      dataset_count: 1,
      datasets: [
        {
          dataset_id: "mof-budget-balance-quarterly",
          source: "mof",
          title: "Budget Balance Quarterly",
          update_frequency: "quarterly",
          health_status: "unknown",
          coverage_status: "queryable",
        },
      ],
    });

    expect(catalog.dataset_count).toBe(1);
    expect(catalog.datasets[0].dataset_id).toBe("mof-budget-balance-quarterly");
  });
});
