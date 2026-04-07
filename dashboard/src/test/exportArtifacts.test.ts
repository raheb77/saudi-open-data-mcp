import { describe, expect, it } from "vitest";
import { buildQueryExportArtifact } from "../lib/exportArtifacts";
import { buildMockQueryResult } from "../mocks/queryResults";

describe("buildQueryExportArtifact", () => {
  it("renders an Excel-compatible XML workbook with metadata and records", () => {
    const result = buildMockQueryResult("mof-budget-balance-quarterly", "success");
    const artifact = buildQueryExportArtifact({
      format: "excel",
      result,
      freshnessStatus: "fresh",
      exportedAt: "2026-04-07T08:30:00Z",
    });

    const xml = new TextDecoder().decode(artifact.bytes);

    expect(artifact.filename).toContain(".xml");
    expect(artifact.mimeType).toBe("application/vnd.ms-excel");
    expect(xml).toContain("<?mso-application progid=\"Excel.Sheet\"?>");
    expect(xml).toContain("mof-budget-balance-quarterly");
    expect(xml).toContain("headline_budget_balance");
    expect(xml).toContain("fresh");
  });

  it("renders a metadata-first PDF artifact for degraded results", () => {
    const result = buildMockQueryResult("stats-gov-sa-cpi-headline-monthly", "limited");
    const artifact = buildQueryExportArtifact({
      format: "pdf",
      result,
      freshnessStatus: "stale",
      exportedAt: "2026-04-07T08:30:00Z",
    });

    const pdf = new TextDecoder().decode(artifact.bytes);

    expect(artifact.filename).toContain(".pdf");
    expect(artifact.mimeType).toBe("application/pdf");
    expect(pdf.startsWith("%PDF-1.4")).toBe(true);
    expect(pdf).toContain("Dataset & Source");
    expect(pdf).toContain("Dataset ID: stats-gov-sa-cpi-headline-monthly");
    expect(pdf).toContain("Source: General Authority for Statistics");
    expect(pdf).toContain("GASTAT");
    expect(pdf).toContain("stats-gov-sa");
    expect(pdf).toContain("Result Status: limited");
    expect(pdf).toContain("Freshness Status: stale");
    expect(pdf).toContain("Applied Filters: none");
    expect(pdf).toContain("Notes / Limitations");
  });
});
