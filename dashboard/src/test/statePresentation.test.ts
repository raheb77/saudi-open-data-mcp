import { describe, expect, it } from "vitest";
import { getDatasetCoverageStatus } from "../lib/statePresentation";

describe("getDatasetCoverageStatus", () => {
  it("classifies record-derivable previews as queryable coverage", () => {
    expect(
      getDatasetCoverageStatus({
        previewStatus: "record_derivable",
      }),
    ).toBe("queryable");
  });

  it("classifies generic extraction limitations as catalog-only coverage", () => {
    expect(
      getDatasetCoverageStatus({
        previewStatus: "limited",
        previewLimitations: [
          "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        ],
      }),
    ).toBe("catalog_only");
  });

  it("classifies source-specific limitations as partial support", () => {
    expect(
      getDatasetCoverageStatus({
        previewStatus: "limited",
        previewLimitations: [
          "sama_pos_weekly_json_requires_supported_report_text_bundle",
        ],
      }),
    ).toBe("limited");
  });

  it("treats preview failures as coverage unavailable", () => {
    expect(
      getDatasetCoverageStatus({
        previewStatus: "failed",
        previewErrorMessage: "preview failed",
      }),
    ).toBe("unavailable");
  });
});
