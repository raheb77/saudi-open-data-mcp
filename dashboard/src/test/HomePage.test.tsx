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
  },
  {
    dataset_id: FEATURED_DATASET_IDS[1],
    source: "sama",
    title: "أسعار الصرف الحالية",
    update_frequency: "daily",
    health_status: "healthy",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[2],
    source: "sama",
    title: "سعر إعادة الشراء الرسمي",
    update_frequency: "daily",
    health_status: "healthy",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[3],
    source: "stats-gov-sa",
    title: "التضخم العام لمؤشر أسعار المستهلك شهريًا",
    update_frequency: "monthly",
    health_status: "healthy",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[4],
    source: "stats-gov-sa",
    title: "نمو الناتج المحلي الحقيقي فصليًا",
    update_frequency: "quarterly",
    health_status: "healthy",
  },
  {
    dataset_id: FEATURED_DATASET_IDS[5],
    source: "mof",
    title: "الرصيد المالي الفصلي",
    update_frequency: "quarterly",
    health_status: "healthy",
  },
];

function makePreviewResult(
  datasetId: string,
  source: SourceName,
): DatasetPreviewResult {
  return {
    dataset_id: datasetId,
    status: "record_derivable",
    resolution_outcome: "serve_local",
    data_origin: "local_snapshot",
    freshness_status: "fresh",
    failure_stage: null,
    degradation_reason: null,
    snapshot_modified_at: "2026-04-08T07:00:00Z",
    resolution_notice: null,
    records: [
      {
        dataset_id: datasetId,
        source,
        record_index: 1,
        fields: { observation_quarter: "2025-Q4", value: 120.3 },
      },
    ],
    limitations: [],
    failure: null,
  };
}

function makeHealthResult(
  datasetId: string,
  source: SourceName,
): DatasetHealthLookupResult {
  return {
    dataset_id: datasetId,
    status: "found",
    source,
    health_status: "healthy",
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
      return makePreviewResult(datasetId, entry.source);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(datasetId, sourceFallback ?? "sama"),
    );

    renderHomePage();

    expect(await screen.findByText("نقاط البيع الأسبوعية")).toBeInTheDocument();
    expect(screen.getAllByText("قابلية الاستعلام").length).toBeGreaterThan(0);
    expect(screen.getAllByText("وقت اللقطة").length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("link", { name: "افتح في صفحة الاستعلام" }).length,
    ).toBeGreaterThan(0);
  });

  it("keeps limited preview queryability visually distinct from freshness", async () => {
    listDatasetsMock.mockResolvedValue(FEATURED_DATASETS);
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = FEATURED_DATASETS.find((item) => item.dataset_id === datasetId)!;
      if (datasetId === FEATURED_DATASET_IDS[0]) {
        return {
          dataset_id: datasetId,
          status: "limited",
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
      return makePreviewResult(datasetId, entry.source);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(datasetId, sourceFallback ?? "sama"),
    );

    renderHomePage();

    expect(await screen.findByText("نقاط البيع الأسبوعية")).toBeInTheDocument();
    expect(screen.getAllByText("قابلية الاستعلام").length).toBeGreaterThan(0);
    expect(screen.getAllByText("حالة اللقطة").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "توجد لقطة قابلة للقراءة، لكن لا توجد بعد سجلات معيارية جاهزة للاستعلام التحليلي.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("حديث").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /التفاصيل التقنية/i }));
    expect(
      screen.getByText(
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
      ),
    ).toBeInTheDocument();
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
      return makePreviewResult(datasetId, entry.source);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(datasetId, sourceFallback ?? "sama"),
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
      return makePreviewResult(datasetId, entry.source);
    });
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(datasetId, sourceFallback ?? "sama"),
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
