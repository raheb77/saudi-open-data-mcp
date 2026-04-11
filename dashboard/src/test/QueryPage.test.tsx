import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ar } from "../i18n/ar";
import {
  DashboardApiError,
} from "../lib/mcpClient";
import {
  getDatasetHealthResult,
  getDatasetQueryResult,
  listDatasets,
} from "../lib/liveData";
import { QueryPage } from "../pages/QueryPage";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  DatasetQueryResult,
  QueryFailure,
  SourceName,
} from "../types/core";

vi.mock("../lib/liveData", () => ({
  listDatasets: vi.fn(),
  getDatasetHealthResult: vi.fn(),
  getDatasetQueryResult: vi.fn(),
}));

vi.mock("../lib/exportArtifacts", () => ({
  downloadQueryExportArtifact: vi.fn(),
}));

const listDatasetsMock = vi.mocked(listDatasets);
const getDatasetHealthResultMock = vi.mocked(getDatasetHealthResult);
const getDatasetQueryResultMock = vi.mocked(getDatasetQueryResult);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

function makeCatalogEntry(
  datasetId: string,
  source: SourceName,
  title: string,
): DatasetCatalogEntry {
  return {
    dataset_id: datasetId,
    source,
    title,
    update_frequency: "weekly",
    health_status: "healthy",
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

function makeQueryResult(
  datasetId: string,
  source: SourceName,
  status: DatasetQueryResult["status"] = "success",
  failure: QueryFailure | null = null,
): DatasetQueryResult {
  return {
    dataset_id: datasetId,
    status,
    source,
    data_origin: "local_snapshot",
    applied_filters: {},
    limit: 100,
    total_records_before_filter: status === "success" ? 1 : null,
    failure_stage: failure?.stage ?? null,
    degradation_reason: null,
    matched_records:
      status === "success"
        ? [
            {
              dataset_id: datasetId,
              source,
              record_index: 1,
              fields: {
                observation_quarter: "2025-Q4",
                value: 120.3,
              },
            },
          ]
        : [],
    limitations: status === "limited" ? ["normalization_limited"] : [],
    failure,
  };
}

function renderQueryPage(initialEntry = "/query") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/query" element={<QueryPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("QueryPage", () => {
  const datasets = [
    makeCatalogEntry("sama-pos-weekly", "sama", "نقاط البيع الأسبوعية"),
    makeCatalogEntry(
      "mof-budget-balance-quarterly",
      "mof",
      "الرصيد المالي الفصلي",
    ),
  ];

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the live success path and reloads the result on dataset change", async () => {
    listDatasetsMock.mockResolvedValue(datasets);
    getDatasetHealthResultMock.mockImplementation(async (datasetId, sourceFallback) =>
      makeHealthResult(datasetId, sourceFallback ?? "sama"),
    );
    getDatasetQueryResultMock.mockImplementation(async (datasetId) =>
      datasetId === "mof-budget-balance-quarterly"
        ? makeQueryResult(datasetId, "mof")
        : makeQueryResult(datasetId, "sama"),
    );

    renderQueryPage("/query");

    expect(await screen.findByTestId("result-table")).toBeInTheDocument();
    expect(screen.getByText("2025-Q4")).toBeInTheDocument();
    expect(getDatasetQueryResultMock).toHaveBeenCalledWith(
      "sama-pos-weekly",
      {},
      100,
      expect.any(AbortSignal),
    );

    fireEvent.change(screen.getByLabelText(ar.query.datasetSelectorLabel), {
      target: { value: "mof-budget-balance-quarterly" },
    });

    await waitFor(() =>
      expect(getDatasetQueryResultMock).toHaveBeenCalledWith(
        "mof-budget-balance-quarterly",
        {},
        100,
        expect.any(AbortSignal),
      ),
    );
  });

  it("renders the unauthorized state when the live query call is rejected as unauthorized", async () => {
    listDatasetsMock.mockResolvedValue([datasets[0]]);
    getDatasetHealthResultMock.mockResolvedValue(
      makeHealthResult("sama-pos-weekly", "sama"),
    );
    getDatasetQueryResultMock.mockRejectedValue(
      new DashboardApiError(
        "unauthorized",
        "query_page",
        "الواجهة غير مخوّلة للوصول إلى مسار MCP الحي.",
      ),
    );

    renderQueryPage("/query?dataset=sama-pos-weekly");

    expect(await screen.findByTestId("state-unauthorized")).toBeInTheDocument();
  });

  it("renders a failed query result returned by the live core", async () => {
    listDatasetsMock.mockResolvedValue([datasets[1]]);
    getDatasetHealthResultMock.mockResolvedValue(
      makeHealthResult("mof-budget-balance-quarterly", "mof"),
    );
    getDatasetQueryResultMock.mockResolvedValue(
      makeQueryResult("mof-budget-balance-quarterly", "mof", "failed", {
        stage: "normalization",
        error_type: "InvalidSourceResponseError",
        message: "فشل تطبيع النتيجة الحية.",
      }),
    );

    renderQueryPage("/query?dataset=mof-budget-balance-quarterly");

    expect(await screen.findByTestId("state-failed")).toBeInTheDocument();
    expect(screen.getByText("فشل تطبيع النتيجة الحية.")).toBeInTheDocument();
    expect(screen.getByText("normalization")).toBeInTheDocument();
    expect(screen.getByText("InvalidSourceResponseError")).toBeInTheDocument();
  });

  it("keeps the query result visible when the auxiliary health fetch fails", async () => {
    listDatasetsMock.mockResolvedValue([datasets[0]]);
    getDatasetHealthResultMock.mockRejectedValue(new Error("health failed"));
    getDatasetQueryResultMock.mockResolvedValue(
      makeQueryResult("sama-pos-weekly", "sama"),
    );

    renderQueryPage("/query?dataset=sama-pos-weekly");

    expect(await screen.findByTestId("result-table")).toBeInTheDocument();
    expect(screen.getByTestId("metadata-strip")).toBeInTheDocument();
    expect(screen.getByTestId("query-health-degraded")).toBeInTheDocument();
    expect(
      screen.getByText("تعذّر تحميل سياق الصحة والحداثة لهذا الاستعلام."),
    ).toBeInTheDocument();
    expect(screen.queryByText(ar.meta.schemaVersion)).not.toBeInTheDocument();
    expect(screen.queryByText(ar.meta.snapshotAge)).not.toBeInTheDocument();
  });

  it("surfaces analyst-facing result context with compact stats, filters, and export controls", async () => {
    listDatasetsMock.mockResolvedValue([
      makeCatalogEntry(
        "stats-gov-sa-cpi-headline-monthly",
        "stats-gov-sa",
        "مؤشر أسعار المستهلك",
      ),
    ]);
    getDatasetHealthResultMock.mockResolvedValue(
      makeHealthResult("stats-gov-sa-cpi-headline-monthly", "stats-gov-sa"),
    );
    getDatasetQueryResultMock.mockResolvedValue({
      ...makeQueryResult(
        "stats-gov-sa-cpi-headline-monthly",
        "stats-gov-sa",
      ),
      applied_filters: {
        observation_month: "2025-12",
        inflation_series_code: "headline_cpi_all_items",
      },
      total_records_before_filter: 42,
      limit: 25,
      matched_records: [
        {
          dataset_id: "stats-gov-sa-cpi-headline-monthly",
          source: "stats-gov-sa",
          record_index: 1,
          fields: {
            observation_month: "2025-12",
            inflation_series_code: "headline_cpi_all_items",
            inflation_series_name: "Headline CPI",
            yoy_rate_percent: 2.1,
            mom_rate_percent: 0.1,
            release_date: "2026-01-15",
          },
        },
      ],
    });

    renderQueryPage("/query?dataset=stats-gov-sa-cpi-headline-monthly");

    const summary = await screen.findByTestId("query-result-summary");
    const exportControls = screen.getByTestId("query-export-controls");

    expect(within(summary).getByText(ar.query.resultOverviewTitle)).toBeInTheDocument();
    expect(within(summary).getByText("42")).toBeInTheDocument();
    expect(within(summary).getByText("25")).toBeInTheDocument();
    expect(within(summary).getByText(ar.query.appliedFilters)).toBeInTheDocument();
    expect(within(summary).getByText("observation_month")).toBeInTheDocument();
    expect(within(summary).getByText("headline_cpi_all_items")).toBeInTheDocument();
    expect(
      within(exportControls).getByText(ar.query.exportCurrentTitle),
    ).toBeInTheDocument();
    expect(
      within(exportControls).getByRole("button", { name: ar.query.export }),
    ).toBeInTheDocument();
  });

  it("surfaces a validation-stage query failure as an explicit page error state", async () => {
    listDatasetsMock.mockResolvedValue([datasets[0]]);
    getDatasetHealthResultMock.mockResolvedValue(
      makeHealthResult("sama-pos-weekly", "sama"),
    );
    getDatasetQueryResultMock.mockRejectedValue(
      new DashboardApiError(
        "validation",
        "query_validation",
        "تعذّر التحقق من نتيجة الاستعلام الحية.",
      ),
    );

    renderQueryPage("/query?dataset=sama-pos-weekly");

    expect(await screen.findByTestId("state-failed")).toBeInTheDocument();
    expect(screen.getByText("تعذّر التحقق من نتيجة الاستعلام الحية.")).toBeInTheDocument();
    expect(screen.getByText("query_validation")).toBeInTheDocument();
  });

  it("aborts slow live requests cleanly when the page unmounts before they resolve", async () => {
    const slowHealth = deferred<DatasetHealthLookupResult>();
    const slowQuery = deferred<DatasetQueryResult>();
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    let healthSignal: AbortSignal | undefined;
    let querySignal: AbortSignal | undefined;

    listDatasetsMock.mockResolvedValue([datasets[0]]);
    getDatasetHealthResultMock.mockImplementation(
      (_datasetId, _sourceFallback, signal) => {
        healthSignal = signal;
        return slowHealth.promise;
      },
    );
    getDatasetQueryResultMock.mockImplementation(
      (_datasetId, _filters, _limit, signal) => {
        querySignal = signal;
        return slowQuery.promise;
      },
    );

    const view = renderQueryPage("/query?dataset=sama-pos-weekly");

    await waitFor(() => {
      expect(getDatasetHealthResultMock).toHaveBeenCalledTimes(1);
      expect(getDatasetQueryResultMock).toHaveBeenCalledTimes(1);
    });

    view.unmount();

    expect(healthSignal?.aborted).toBe(true);
    expect(querySignal?.aborted).toBe(true);

    slowHealth.resolve(makeHealthResult("sama-pos-weekly", "sama"));
    slowQuery.resolve(makeQueryResult("sama-pos-weekly", "sama"));

    await Promise.resolve();
    await Promise.resolve();

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });
});
