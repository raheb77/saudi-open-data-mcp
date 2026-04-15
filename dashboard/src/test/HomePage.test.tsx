import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FEATURED_DATASET_IDS } from "../lib/catalogPresentation";
import { DashboardApiError } from "../lib/mcpClient";
import {
  getDatasetHealthResult,
  getDatasetPreviewResult,
  listDatasets,
} from "../lib/liveData";
import { HomePage } from "../pages/HomePage";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  DatasetPreviewResult,
  SourceName,
} from "../types/core";

vi.mock("../lib/liveData", () => ({
  listDatasets: vi.fn(),
  getDatasetPreviewResult: vi.fn(),
  getDatasetHealthResult: vi.fn(),
}));

const listDatasetsMock = vi.mocked(listDatasets);
const getDatasetPreviewResultMock = vi.mocked(getDatasetPreviewResult);
const getDatasetHealthResultMock = vi.mocked(getDatasetHealthResult);

const FEATURED_DATASETS: DatasetCatalogEntry[] = [
  {
    dataset_id: FEATURED_DATASET_IDS[0],
    source: "sama",
    title: "نقاط البيع الأسبوعية",
    update_frequency: "weekly",
    health_status: "healthy",
    coverage_status: "queryable",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[1],
    source: "sama",
    title: "أسعار الصرف الحالية",
    update_frequency: "daily",
    health_status: "healthy",
    coverage_status: "queryable",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[2],
    source: "sama",
    title: "سعر إعادة الشراء الرسمي",
    update_frequency: "daily",
    health_status: "healthy",
    coverage_status: "queryable",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[3],
    source: "stats-gov-sa",
    title: "التضخم العام لمؤشر أسعار المستهلك شهريًا",
    update_frequency: "monthly",
    health_status: "healthy",
    coverage_status: "queryable",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[4],
    source: "stats-gov-sa",
    title: "نمو الناتج المحلي الحقيقي فصليًا",
    update_frequency: "quarterly",
    health_status: "healthy",
    coverage_status: "queryable",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[5],
    source: "mof",
    title: "الرصيد المالي الفصلي",
    update_frequency: "quarterly",
    health_status: "healthy",
    coverage_status: "queryable",
  },
  {
    dataset_id: "sama-pos-by-city",
    source: "sama",
    title: "نقاط البيع حسب المدينة",
    update_frequency: "weekly",
    health_status: "healthy",
    coverage_status: "limited",
  },
  {
    dataset_id: "data-gov-sa-census-marital-status",
    source: "data-gov-sa",
    title: "الحالة الاجتماعية في التعداد",
    update_frequency: "annual",
    health_status: "unknown",
    coverage_status: "catalog_only",
  },
];

function makePreviewResult(
  datasetId: string,
  source: SourceName,
  coverageStatus: DatasetCatalogEntry["coverage_status"] = "queryable",
): DatasetPreviewResult {
  return {
    dataset_id: datasetId,
    status: coverageStatus === "queryable" ? "record_derivable" : "limited",
    coverage_status: coverageStatus,
    resolution_outcome: "serve_local",
    data_origin: "local_snapshot",
    freshness_status: "fresh",
    failure_stage: coverageStatus === "queryable" ? null : "normalization",
    degradation_reason:
      coverageStatus === "queryable" ? null : "normalization_limited",
    snapshot_modified_at: "2026-04-08T07:00:00Z",
    resolution_notice: null,
    records:
      coverageStatus === "queryable"
        ? [
            {
              dataset_id: datasetId,
              source,
              record_index: 1,
              fields: { observation_quarter: "2025-Q4", value: 120.3 },
            },
          ]
        : [],
    limitations:
      coverageStatus === "limited"
        ? ["sama_pos_by_city_json_requires_supported_city_table_report_bundle"]
        : coverageStatus === "catalog_only"
          ? [
              "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
            ]
          : [],
    failure: null,
  };
}

function makeHealthResult(
  datasetId: string,
  source: SourceName,
  coverageStatus: DatasetCatalogEntry["coverage_status"] = "queryable",
): DatasetHealthLookupResult {
  return {
    dataset_id: datasetId,
    status: "found",
    source,
    health_status: "healthy",
    coverage_status: coverageStatus,
    schema_version: "1.0.0",
    caveats: [],
    known_issues: [],
    freshness: {
      source,
      dataset_id: datasetId,
      status: "fresh",
      reason: "within_expected_window",
      artifact_present: true,
      reference_time: "2026-04-08T08:00:00Z",
      snapshot_modified_at: "2026-04-08T07:00:00Z",
      snapshot_age_seconds: 3600,
      update_frequency: "daily",
    },
  };
}

function renderHomePage() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
}

describe("HomePage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the loading state while the live catalog is still pending", () => {
    listDatasetsMock.mockReturnValue(new Promise(() => {}));

    renderHomePage();

    expect(screen.getByTestId("state-loading")).toBeInTheDocument();
  });

  it("renders successful live dataset cards", async () => {
    listDatasetsMock.mockResolvedValue(FEATURED_DATASETS);
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)!;
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );

    renderHomePage();

    expect(await screen.findByText("المجموعات الجاهزة الآن")).toBeInTheDocument();
    expect(screen.getByTestId("home-dataset-section-queryable")).toBeInTheDocument();
    expect(screen.getByTestId("home-dataset-section-limited")).toBeInTheDocument();
    expect(
      screen.getByTestId("home-dataset-section-catalog_only"),
    ).toBeInTheDocument();
    expect(screen.getByText("نقاط البيع الأسبوعية")).toBeInTheDocument();
    // Coverage badges appear in the always-visible badges row; the coverage
    // signal section inside the collapsed accordion also contains them (DOM
    // present, visually hidden via grid-template-rows: 0fr).
    expect(screen.getAllByText("مدعومة الآن").length).toBeGreaterThan(0);
    expect(screen.getAllByText("متاح جزئياً").length).toBeGreaterThan(0);
    expect(screen.getAllByText("فهرس فقط").length).toBeGreaterThan(0);
    // Cards start collapsed — details hidden behind accordion.
    expect(
      screen.getAllByRole("button", { name: "عرض التفاصيل" }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("link", { name: "افتح في صفحة الاستعلام" }).length,
    ).toBeGreaterThan(0);
  });

  it("keeps limited preview queryability visually distinct from freshness", async () => {
    listDatasetsMock.mockResolvedValue(FEATURED_DATASETS);
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)!;
      if (datasetId === "sama-pos-by-city") {
        return {
          dataset_id: datasetId,
          status: "limited",
          coverage_status: "limited",
          resolution_outcome: "serve_local",
          data_origin: "local_snapshot",
          freshness_status: "fresh",
          failure_stage: "normalization",
          degradation_reason: "normalization_limited",
          snapshot_modified_at: "2026-04-08T07:00:00Z",
          resolution_notice: null,
          records: [],
          limitations: [
            "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
          ],
          failure: null,
        };
      }
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );

    renderHomePage();

    expect(await screen.findByTestId("home-dataset-section-limited")).toBeInTheDocument();
    expect(screen.getByText("نقاط البيع حسب المدينة")).toBeInTheDocument();
    expect(screen.getAllByText("فهرس فقط").length).toBeGreaterThan(0);

    // Expand the limited card's accordion to reveal inner detail sections.
    const limitedSection = screen.getByTestId("home-dataset-section-limited");
    const detailsButton = limitedSection.querySelector<HTMLButtonElement>(
      'button[aria-expanded="false"]',
    )!;
    fireEvent.click(detailsButton);

    expect(screen.getAllByText("التغطية الحالية").length).toBeGreaterThan(0);
    expect(screen.getAllByText("قابلية الاستعلام").length).toBeGreaterThan(0);
    expect(screen.getAllByText("حالة اللقطة").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(
        "توجد لقطة قابلة للقراءة، لكن لا توجد بعد سجلات معيارية جاهزة للاستعلام التحليلي.",
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("حديث").length).toBeGreaterThan(0);
    fireEvent.click(screen.getAllByRole("button", { name: /التفاصيل التقنية/i })[0]);
    expect(
      screen.getByText(
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
      ),
    ).toBeInTheDocument();
  });

  it("keeps supported datasets ahead of secondary catalog entries on the home surface", async () => {
    listDatasetsMock.mockResolvedValue(FEATURED_DATASETS);
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)!;
      if (datasetId === "sama-pos-by-city") {
        return {
          ...makePreviewResult(datasetId, entry.source, "limited"),
          status: "limited",
          coverage_status: "limited",
          records: [],
          limitations: ["sama_pos_by_city_json_requires_supported_city_table_report_bundle"],
          degradation_reason: "normalization_limited",
        };
      }
      if (datasetId === "data-gov-sa-census-marital-status") {
        return {
          ...makePreviewResult(datasetId, entry.source, "catalog_only"),
          status: "limited",
          coverage_status: "catalog_only",
          records: [],
          limitations: [
            "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
          ],
          degradation_reason: "normalization_limited",
        };
      }
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );

    renderHomePage();

    const queryableSection = await screen.findByTestId("home-dataset-section-queryable");
    const limitedSection = screen.getByTestId("home-dataset-section-limited");
    const catalogOnlySection = screen.getByTestId("home-dataset-section-catalog_only");

    expect(queryableSection).toHaveTextContent("نقاط البيع الأسبوعية");
    expect(queryableSection).not.toHaveTextContent("نقاط البيع حسب المدينة");
    expect(limitedSection).toHaveTextContent("نقاط البيع حسب المدينة");
    expect(catalogOnlySection).toHaveTextContent("الحالة الاجتماعية في التعداد");
  });

  it("isolates per-card preview failures without dropping healthy cards", async () => {
    listDatasetsMock.mockResolvedValue(FEATURED_DATASETS);
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      if (datasetId === "sama-exchange-rates-current") {
        throw new DashboardApiError(
          "validation",
          "home_preview",
          "تعذّر تحميل معاينة البطاقة.",
        );
      }
      const entry = FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)!;
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );

    renderHomePage();

    expect(await screen.findByText("نقاط البيع الأسبوعية")).toBeInTheDocument();
    expect(screen.getAllByText("وقت اللقطة").length).toBeGreaterThan(0);
    expect(screen.getByText("تعذّر تحميل معاينة البطاقة.")).toBeInTheDocument();
  });

  it("retries after a top-level live page failure", async () => {
    listDatasetsMock
      .mockRejectedValueOnce(
        new DashboardApiError(
          "validation",
          "catalog_validation",
          "تعذّر التحقق من بيانات الفهرس الحية.",
        ),
      )
      .mockResolvedValueOnce(FEATURED_DATASETS);
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)!;
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );

    renderHomePage();

    expect(await screen.findByTestId("state-failed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "أعد المحاولة" }));

    await waitFor(() =>
      expect(screen.getByText("نقاط البيع الأسبوعية")).toBeInTheDocument(),
    );
    expect(listDatasetsMock).toHaveBeenCalledTimes(2);
  });
});
