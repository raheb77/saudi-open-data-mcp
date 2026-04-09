import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardApiError } from "../lib/mcpClient";
import {
  getDatasetHealthResult,
  getObservability,
  getReadiness,
  listDatasets,
} from "../lib/liveData";
import { SystemStatusPage } from "../pages/SystemStatusPage";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  ObservabilitySummary,
  ReadinessReport,
  SourceName,
} from "../types/core";

vi.mock("../lib/liveData", () => ({
  listDatasets: vi.fn(),
  getDatasetHealthResult: vi.fn(),
  getObservability: vi.fn(),
  getReadiness: vi.fn(),
}));

const listDatasetsMock = vi.mocked(listDatasets);
const getDatasetHealthResultMock = vi.mocked(getDatasetHealthResult);
const getObservabilityMock = vi.mocked(getObservability);
const getReadinessMock = vi.mocked(getReadiness);

const STATUS_DATASETS: DatasetCatalogEntry[] = [
  {
    dataset_id: "sama-pos-weekly",
    source: "sama",
    title: "نقاط البيع الأسبوعية",
    update_frequency: "weekly",
    health_status: "healthy",
  },
  {
    dataset_id: "stats-gov-sa-cpi-headline-monthly",
    source: "stats-gov-sa",
    title: "التضخم العام لمؤشر أسعار المستهلك شهريًا",
    update_frequency: "monthly",
    health_status: "healthy",
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
        name: "materialize",
        summary: "ملخص عدّادات التحديث المحلية.",
        counters: [
          { name: "materialize.requests", value: 3 },
          { name: "materialize.successes", value: 2 },
          { name: "materialize.failures", value: 1 },
        ],
        detail_counters: [],
      },
    ],
    raw_counters: {
      "materialize.requests": 3,
      "materialize.successes": 2,
      "materialize.failures": 1,
    },
    notes: ["عدادات محلية فقط"],
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
      update_frequency: "weekly",
    },
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

    render(<SystemStatusPage />);

    expect(screen.getByTestId("state-loading")).toBeInTheDocument();
  });

  it("renders the live success path with readiness, counters, and health cards", async () => {
    getReadinessMock.mockResolvedValue(makeReadinessReport());
    getObservabilityMock.mockResolvedValue(makeObservabilitySummary());
    listDatasetsMock.mockResolvedValue(STATUS_DATASETS);
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(datasetId, sourceFallback ?? "sama"),
    );

    render(<SystemStatusPage />);

    expect(await screen.findByText("الجاهزية")).toBeInTheDocument();
    expect(screen.getByText("جاهز")).toBeInTheDocument();
    expect(screen.getByText("ملخص عدّادات التحديث")).toBeInTheDocument();
    expect(screen.getAllByText("sama-pos-weekly").length).toBeGreaterThan(0);
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

    render(<SystemStatusPage />);

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
      makeHealthResult(datasetId, sourceFallback ?? "sama"),
    );

    render(<SystemStatusPage />);

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
});
