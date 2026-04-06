import { describe, expect, it } from "vitest";
import {
  parseDatasetHealthLookupResult,
  parseDatasetPreviewResult,
  parseDatasetQueryResult,
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

  it("rejects an invalid preview payload", () => {
    expect(() =>
      parseDatasetPreviewResult({
        dataset_id: "stats-gov-sa-cpi-headline-monthly",
        status: "success",
      }),
    ).toThrow(/Invalid DatasetPreviewResult/);
  });

  it("rejects an invalid health payload", () => {
    expect(() =>
      parseDatasetHealthLookupResult({
        dataset_id: "stats-gov-sa-cpi-headline-monthly",
        status: "found",
        source: "stats-gov-sa",
        health_status: "healthy",
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
          snapshot_age_seconds: null,
          update_frequency: "monthly",
        },
      }),
    ).toThrow(/Invalid SnapshotFreshnessResult\.artifact_present payload/);
  });
});
