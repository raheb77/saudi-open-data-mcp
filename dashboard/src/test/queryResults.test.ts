import { describe, expect, it } from "vitest";
import { buildMockQueryResult } from "../mocks/queryResults";

describe("buildMockQueryResult", () => {
  it("returns a success result with records for sama-pos-weekly", () => {
    const result = buildMockQueryResult("sama-pos-weekly", "success", {}, 2);
    expect(result.status).toBe("success");
    expect(result.source).toBe("sama");
    expect(result.data_origin).toBe("local_snapshot");
    expect(result.matched_records.length).toBeLessThanOrEqual(2);
    expect(result.failure).toBeNull();
  });

  it("returns a missing status with cleared source for unknown datasets", () => {
    const result = buildMockQueryResult("unknown-id", "missing");
    expect(result.status).toBe("missing");
    expect(result.source).toBeNull();
    expect(result.data_origin).toBeNull();
    expect(result.matched_records).toEqual([]);
  });

  it("returns limited status with declared limitations and no records", () => {
    const result = buildMockQueryResult(
      "stats-gov-sa-cpi-headline-monthly",
      "limited",
    );
    expect(result.status).toBe("limited");
    expect(result.degradation_reason).toBe("normalization_limited");
    expect(result.limitations.length).toBeGreaterThan(0);
    expect(result.matched_records).toEqual([]);
  });

  it("returns a failed status with a structured failure payload", () => {
    const result = buildMockQueryResult(
      "mof-budget-balance-quarterly",
      "failed",
    );
    expect(result.status).toBe("failed");
    expect(result.failure).not.toBeNull();
    expect(result.failure?.stage).toBe("normalization");
    expect(result.failure?.error_type).toBe("InvalidSourceResponseError");
  });
});
