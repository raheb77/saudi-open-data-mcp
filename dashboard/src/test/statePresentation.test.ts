import { describe, expect, it } from "vitest";
import { getCoverageNarrative } from "../lib/statePresentation";

describe("getCoverageNarrative", () => {
  it("returns the supported-now narrative for queryable coverage", () => {
    expect(getCoverageNarrative("queryable")).toContain("يمكن الاستعلام");
  });

  it("returns the partial-support narrative for limited coverage", () => {
    expect(getCoverageNarrative("limited")).toContain("جزئي");
  });

  it("returns the catalog-only narrative for catalog coverage", () => {
    expect(getCoverageNarrative("catalog_only")).toContain("مسجلة في الفهرس");
  });

  it("returns the unavailable narrative for unresolved coverage", () => {
    expect(getCoverageNarrative("unavailable")).toContain("تعذّر تحديد");
  });
});
