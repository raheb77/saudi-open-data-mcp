import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardApiError } from "../lib/mcpClient";
import {
  getDatasetHealthResult,
  getDatasetPreviewResult,
  getObservability,
  getReadiness,
  listDatasets,
} from "../lib/liveData";
import { SystemStatusPage } from "../pages/SystemStatusPage";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  DatasetPreviewResult,
  ObservabilitySummary,
  ReadinessReport,
  SourceName,
} from "../types/core";

vi.mock("../lib/liveData", () => ({
  listDatasets: vi.fn(),
  getDatasetHealthResult: vi.fn(),
  getDatasetPreviewResult: vi.fn(),
  getObservability: vi.fn(),
  getReadiness: vi.fn(),
}));

const listDatasetsMock = vi.mocked(listDatasets);
const getDatasetHealthResultMock = vi.mocked(getDatasetHealthResult);
const getDatasetPreviewResultMock = vi.mocked(getDatasetPreviewResult);
const getObservabilityMock = vi.mocked(getObservability);
const getReadinessMock = vi.mocked(getReadiness);

const STATUS_DATASETS: DatasetCatalogEntry[] = [
  {
    dataset_id: "sama-pos-weekly",
    source: "sama",
    title: "نقاط البيع الأسبوعية",
    update_frequency: "weekly",
    health_status: "healthy",
    coverage_status: "queryable",
  },
  {
    dataset_id: "stats-gov-sa-cpi-headline-monthly",
    source: "stats-gov-sa",
    title: "التضخم العام لمؤشر أسعار المستهلك شهريًا",
    update_frequency: "monthly",
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

function makeReadinessReport(): ReadinessReport {
  return {
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
  };
}

function makeObservabilitySummary(): ObservabilitySummary {
  return {
    process_local: true,
    groups: [
      {
        name: "startup",
        summary:
          "Process-local server construction counters. Attempts, ready, and failures count startup lifecycle outcomes, not request traffic.",
        counters: [
          { name: "server.startup.attempts", value: 1 },
          { name: "server.startup.ready", value: 1 },
          { name: "server.startup.failures", value: 0 },
        ],
        detail_counters: [],
      },
      {
        name: "auth",
        summary:
          "HTTP auth counters for the run-http serving path only. Accepted and rejected counts are outcomes within http.auth.requests. http.authz.* counters track 403 capability denials plus fail-closed coverage errors after token validation.",
        counters: [
          { name: "http.auth.requests", value: 5 },
          { name: "http.auth.accepted", value: 4 },
          { name: "http.auth.rejected", value: 1 },
          { name: "http.auth.rejected.invalid", value: 1 },
        ],
        detail_counters: [],
      },
      {
        name: "connectors",
        summary:
          "Top-level connector retry/failure totals. Per-source connector.request_* detail counters remain available below for source-specific inspection.",
        counters: [
          { name: "connector.retries", value: 2 },
          { name: "connector.failures", value: 1 },
        ],
        detail_counters: [
          { name: "connector.request_attempts.sama", value: 8 },
        ],
      },
      {
        name: "materialization",
        summary:
          "Hot-set materialization counters. materialize.requests counts top-level runs; successes and failures count per-dataset outcomes, including Tier A background refresh runs.",
        counters: [
          { name: "materialize.requests", value: 3 },
          { name: "materialize.successes", value: 2 },
          { name: "materialize.failures", value: 1 },
        ],
        detail_counters: [],
      },
    ],
    raw_counters: {
      "server.startup.attempts": 1,
      "server.startup.ready": 1,
      "server.startup.failures": 0,
      "http.auth.requests": 5,
      "http.auth.accepted": 4,
      "http.auth.rejected": 1,
      "http.auth.rejected.invalid": 1,
      "connector.retries": 2,
      "connector.failures": 1,
      "connector.request_attempts.sama": 8,
      "materialize.requests": 3,
      "materialize.successes": 2,
      "materialize.failures": 1,
    },
    notes: [
      "Counters are process-local and reset on process restart.",
      "Request counters and outcome counters are not interchangeable; see each group summary.",
    ],
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
      update_frequency: "weekly",
    },
  };
}

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
              fields: { observation_date: "2026-04-08", value: 1 },
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

describe("SystemStatusPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the loading state while live status surfaces are still pending", () => {
    getReadinessMock.mockReturnValue(new Promise(() => {}));
    getObservabilityMock.mockReturnValue(new Promise(() => {}));
    listDatasetsMock.mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter>
        <SystemStatusPage />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("state-loading")).toBeInTheDocument();
  });

  it("renders the live success path with readiness, counters, and health cards", async () => {
    getReadinessMock.mockResolvedValue(makeReadinessReport());
    getObservabilityMock.mockResolvedValue(makeObservabilitySummary());
    listDatasetsMock.mockResolvedValue(STATUS_DATASETS);
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        STATUS_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = STATUS_DATASETS.find((item) => item.dataset_id === datasetId)!;
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });

    render(
      <MemoryRouter>
        <SystemStatusPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("الجاهزية")).toBeInTheDocument();
    expect(screen.getByText("جاهز")).toBeInTheDocument();
    expect(screen.getByText("ملخص عدّادات التحديث")).toBeInTheDocument();
    expect(screen.getByText("جاهزية التشغيل الداخلية")).toBeInTheDocument();
    expect(screen.getByText("العملية تعمل")).toBeInTheDocument();
    expect(screen.getByText("بدء التشغيل")).toBeInTheDocument();
    expect(screen.getByText("المصادقة")).toBeInTheDocument();
    expect(screen.getByText("الموصّلات")).toBeInTheDocument();
    expect(screen.getByText("محاولات البدء")).toBeInTheDocument();
    expect(screen.getByText("طلبات المصادقة")).toBeInTheDocument();
    expect(screen.getByText("طلبات ساما")).toBeInTheDocument();
    expect(
      screen.getByText("تُعاد العدّادات إلى الصفر عند إعادة تشغيل العملية."),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("status-dataset-section-queryable"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("status-dataset-section-limited")).toBeInTheDocument();
    expect(
      screen.getByTestId("status-dataset-section-catalog_only"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("التغطية الحالية").length).toBeGreaterThan(0);
    expect(screen.getAllByText("مدعومة الآن").length).toBeGreaterThan(0);
    expect(screen.getByText("متاح جزئياً")).toBeInTheDocument();
    expect(screen.getByText("فهرس فقط")).toBeInTheDocument();
    expect(screen.getAllByText("قابلية الاستعلام").length).toBeGreaterThan(0);
    expect(screen.getAllByText("وقت اللقطة").length).toBeGreaterThan(0);
    expect(screen.getAllByText("sama-pos-weekly").length).toBeGreaterThan(0);
    expect(
      screen.queryByText("server.startup.attempts"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("http.auth.requests")).not.toBeInTheDocument();
    expect(screen.queryByText("connector.request_attempts.sama")).not.toBeInTheDocument();
  });

  it("keeps healthy sections visible when one live status section fails", async () => {
    getReadinessMock.mockRejectedValue(
      new DashboardApiError(
        "validation",
        "readiness_validation",
        "تعذّر التحقق من حمولة الجاهزية الحية.",
      ),
    );
    getObservabilityMock.mockResolvedValue(makeObservabilitySummary());
    listDatasetsMock.mockResolvedValue(STATUS_DATASETS);
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = STATUS_DATASETS.find((item) => item.dataset_id === datasetId)!;
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });

    render(
      <MemoryRouter>
        <SystemStatusPage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId("status-page-degraded")).toBeInTheDocument();
    expect(screen.getByText("تعذّر التحقق من حمولة الجاهزية الحية.")).toBeInTheDocument();
    expect(screen.getByText("ملخص عدّادات التحديث")).toBeInTheDocument();
    expect(screen.getAllByText("sama-pos-weekly").length).toBeGreaterThan(0);
  });

  it("retries after a section-level status failure", async () => {
    getReadinessMock
      .mockRejectedValueOnce(
        new DashboardApiError(
          "validation",
          "readiness_validation",
          "تعذّر التحقق من حمولة الجاهزية الحية.",
        ),
      )
      .mockResolvedValueOnce(makeReadinessReport());
    getObservabilityMock.mockResolvedValue(makeObservabilitySummary());
    listDatasetsMock.mockResolvedValue(STATUS_DATASETS);
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        STATUS_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = STATUS_DATASETS.find((item) => item.dataset_id === datasetId)!;
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });

    render(
      <MemoryRouter>
        <SystemStatusPage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId("status-page-degraded")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "أعد المحاولة" }));

    await waitFor(() =>
      expect(screen.getAllByText("sama-pos-weekly").length).toBeGreaterThan(0),
    );
    await waitFor(() =>
      expect(
        screen.queryByTestId("status-page-degraded"),
      ).not.toBeInTheDocument(),
    );
    expect(getReadinessMock).toHaveBeenCalledTimes(2);
  });

  it("shows limited queryability separately from fresh snapshot state on status cards", async () => {
    getReadinessMock.mockResolvedValue(makeReadinessReport());
    getObservabilityMock.mockResolvedValue(makeObservabilitySummary());
    listDatasetsMock.mockResolvedValue(STATUS_DATASETS);
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        STATUS_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = STATUS_DATASETS.find((item) => item.dataset_id === datasetId)!;
      if (datasetId === "sama-pos-by-city") {
        return {
          ...makePreviewResult(datasetId, entry.source, "limited"),
          status: "limited",
          coverage_status: "limited",
          limitations: ["sama_pos_weekly_json_requires_supported_report_text_bundle"],
          degradation_reason: "normalization_limited",
        };
      }
      return makePreviewResult(datasetId, entry.source, entry.coverage_status);
    });

    render(
      <MemoryRouter>
        <SystemStatusPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("حالة المصادر ومجموعات البيانات")).toBeInTheDocument();
    expect(screen.getByTestId("status-dataset-section-limited")).toBeInTheDocument();
    expect(screen.getAllByText("التغطية الحالية").length).toBeGreaterThan(0);
    expect(screen.getByText("متاح جزئياً")).toBeInTheDocument();
    expect(
      screen.getByText(
        "هذه المجموعة ضمن النطاق الحالي، لكن استخدامها التحليلي ما زال جزئيًا بسبب قيود استخراج أو تطبيع مُعلنة.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("قابلية الاستعلام").length).toBeGreaterThan(0);
    expect(screen.getAllByText("حالة اللقطة").length).toBeGreaterThan(0);
    expect(screen.getAllByText("صحة المصدر").length).toBeGreaterThan(0);
    expect(screen.getAllByText("حديث").length).toBeGreaterThan(0);
    fireEvent.click(screen.getAllByRole("button", { name: /التفاصيل التقنية/i })[0]);
    expect(
      screen.getByText(
        "sama_pos_weekly_json_requires_supported_report_text_bundle",
      ),
    ).toBeInTheDocument();
  });

  it("keeps supported status cards ahead of partial and catalog-only cards", async () => {
    getReadinessMock.mockResolvedValue(makeReadinessReport());
    getObservabilityMock.mockResolvedValue(makeObservabilitySummary());
    listDatasetsMock.mockResolvedValue(STATUS_DATASETS);
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(
        datasetId,
        sourceFallback ?? "sama",
        STATUS_DATASETS.find((item) => item.dataset_id === datasetId)
          ?.coverage_status ?? "queryable",
      ),
    );
    getDatasetPreviewResultMock.mockImplementation(async (datasetId) => {
      const entry = STATUS_DATASETS.find((item) => item.dataset_id === datasetId)!;
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

    render(
      <MemoryRouter>
        <SystemStatusPage />
      </MemoryRouter>,
    );

    const queryableSection = await screen.findByTestId(
      "status-dataset-section-queryable",
    );
    const limitedSection = screen.getByTestId("status-dataset-section-limited");
    const catalogOnlySection = screen.getByTestId(
      "status-dataset-section-catalog_only",
    );

    expect(queryableSection).toHaveTextContent("نقاط البيع الأسبوعية");
    expect(queryableSection).not.toHaveTextContent("نقاط البيع حسب المدينة");
    expect(limitedSection).toHaveTextContent("نقاط البيع حسب المدينة");
    expect(catalogOnlySection).toHaveTextContent("الحالة الاجتماعية في التعداد");
  });
});
