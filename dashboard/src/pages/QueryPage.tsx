import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DatasetSelector } from "../components/DatasetSelector";
import {
  FilterForm,
  filterRowsToFilters,
  type FilterRow,
} from "../components/FilterForm";
import { MetadataStrip } from "../components/MetadataStrip";
import { ResultTable } from "../components/ResultTable";
import {
  EmptyState,
  ErrorState,
  LimitedState,
  LoadingState,
  MissingState,
  SnapshotMissingState,
  StaleState,
  UnauthorizedState,
} from "../components/StateBlocks";
import { ar } from "../i18n/ar";
import {
  downloadQueryExportArtifact,
  type ExportArtifactFormat,
} from "../lib/exportArtifacts";
import { formatAge, formatNumber } from "../lib/format";
import {
  getDatasetHealthResult,
  getDatasetQueryResult,
  listDatasets,
} from "../lib/liveData";
import { DashboardApiError, asDashboardApiError } from "../lib/mcpClient";
import type {
  DashboardRole,
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  DatasetQueryResult,
  QueryFilterValue,
} from "../types/core";

interface QueryPageProps {
  role: DashboardRole | null;
}

type CatalogState =
  | { kind: "loading" }
  | { kind: "failed"; error: DashboardApiError }
  | { kind: "ready"; datasets: DatasetCatalogEntry[] };

type QueryState =
  | { kind: "loading" }
  | { kind: "failed"; error: DashboardApiError }
  | { kind: "ready"; result: DatasetQueryResult };

export function QueryPage({ role }: QueryPageProps) {
  const [searchParams] = useSearchParams();
  const [catalogState, setCatalogState] = useState<CatalogState>({
    kind: "loading",
  });
  const [datasetId, setDatasetId] = useState("");
  const [filters, setFilters] = useState<FilterRow[]>([]);
<<<<<<< HEAD
  const [limit, setLimit] = useState<string>("100");
  const [scenario, setScenario] = useState<QueryScenarioName>("success");
  const [exportFormat, setExportFormat] = useState<ExportArtifactFormat>("json");
  const [appliedSignal, setAppliedSignal] = useState(0);
=======
  const [limit, setLimit] = useState("100");
  const [appliedFilters, setAppliedFilters] = useState<
    Record<string, QueryFilterValue>
  >({});
  const [appliedLimit, setAppliedLimit] = useState<number | null>(100);
  const [queryState, setQueryState] = useState<QueryState>({ kind: "loading" });
  const [health, setHealth] = useState<DatasetHealthLookupResult | null>(null);
  const [catalogReloadToken, setCatalogReloadToken] = useState(0);
>>>>>>> feat/dashboard-codex-alt

  useEffect(() => {
    const controller = new AbortController();
    setCatalogState({ kind: "loading" });

    void (async () => {
      try {
        const datasets = await listDatasets(controller.signal);
        if (controller.signal.aborted) {
          return;
        }
        setCatalogState({ kind: "ready", datasets });
      } catch (error) {
        if (!controller.signal.aborted) {
          setCatalogState({
            kind: "failed",
            error: asDashboardApiError(
              error,
              "query_catalog",
              "تعذّر تحميل قائمة المجموعات الحية.",
            ),
          });
        }
      }
    })();

    return () => controller.abort();
  }, [catalogReloadToken]);

  const datasets =
    catalogState.kind === "ready" ? catalogState.datasets : ([] as DatasetCatalogEntry[]);
  const selectedCatalogEntry = datasets.find(
    (entry) => entry.dataset_id === datasetId,
  );

  useEffect(() => {
    if (catalogState.kind !== "ready" || catalogState.datasets.length === 0) {
      return;
    }
    const fromUrl = searchParams.get("dataset");
    const preferredDatasetId =
      fromUrl &&
      catalogState.datasets.some((entry) => entry.dataset_id === fromUrl)
        ? fromUrl
        : catalogState.datasets[0].dataset_id;

    if (datasetId !== preferredDatasetId) {
      setDatasetId(preferredDatasetId);
    }
  }, [catalogState, datasetId, searchParams]);

  useEffect(() => {
    if (!datasetId || !selectedCatalogEntry) {
      setHealth(null);
      return;
    }

    const controller = new AbortController();
    setHealth(null);
    void (async () => {
      try {
        const nextHealth = await getDatasetHealthResult(
          datasetId,
          selectedCatalogEntry.source,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          setHealth(nextHealth);
        }
      } catch {
        if (!controller.signal.aborted) {
          setHealth(null);
        }
      }
    })();

    return () => controller.abort();
  }, [datasetId, selectedCatalogEntry]);

  useEffect(() => {
    if (!datasetId) {
      return;
    }

    const controller = new AbortController();
    setQueryState({ kind: "loading" });
    void (async () => {
      try {
        const result = await getDatasetQueryResult(
          datasetId,
          appliedFilters,
          appliedLimit,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          setQueryState({ kind: "ready", result });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setQueryState({
            kind: "failed",
            error: asDashboardApiError(
              error,
              "query_page",
              "تعذّر تنفيذ الاستعلام الحي.",
            ),
          });
        }
      }
    })();

    return () => controller.abort();
  }, [appliedFilters, appliedLimit, datasetId]);

  function handleApply() {
    const parsedLimit = Number(limit);
    setAppliedFilters(filterRowsToFilters(filters));
    setAppliedLimit(
      Number.isFinite(parsedLimit) && parsedLimit > 0 ? parsedLimit : null,
    );
  }

  function handleReset() {
    setFilters([]);
    setLimit("100");
    setAppliedFilters({});
    setAppliedLimit(100);
  }

  function handleExport() {
<<<<<<< HEAD
    if (isLoading || isUnauthorized) return;

    downloadQueryExportArtifact({
      format: exportFormat,
      result,
      freshnessStatus: freshness?.status ?? null,
=======
    if (queryState.kind !== "ready") {
      return;
    }
    const blob = new Blob([JSON.stringify(queryState.result, null, 2)], {
      type: "application/json",
>>>>>>> feat/dashboard-codex-alt
    });
  }

  const freshness = health?.freshness ?? null;
  const shouldShowStaleState =
    queryState.kind === "ready" &&
    queryState.result.status === "success" &&
    freshness?.status === "stale";

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold text-ink-900">
          {ar.query.heading}
        </h2>
        <p className="max-w-3xl text-sm leading-relaxed text-ink-700">
          {ar.query.description}
        </p>
      </section>

      {catalogState.kind === "loading" && <LoadingState />}

      {catalogState.kind === "failed" && (
        <section className="flex flex-col gap-3">
          {catalogState.error.kind === "unauthorized" ? (
            <UnauthorizedState />
          ) : (
            <ErrorState
              stage={catalogState.error.stage}
              errorType={catalogState.error.name}
              message={catalogState.error.message}
            />
          )}
          <button
            type="button"
            onClick={() => setCatalogReloadToken((value) => value + 1)}
            className="self-start rounded-md border border-ink-300 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
          >
            {ar.app.retry}
          </button>
        </section>
      )}

      {catalogState.kind === "ready" && datasets.length > 0 && datasetId && (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
          <div className="flex flex-col gap-4">
            <DatasetSelector
              datasets={datasets}
              value={datasetId}
              onChange={setDatasetId}
            />

            <FilterForm
              filters={filters}
              onFiltersChange={setFilters}
              limit={limit}
              onLimitChange={setLimit}
              onApply={handleApply}
              onReset={handleReset}
            />
          </div>

          <div className="flex flex-col gap-4">
            {queryState.kind === "ready" && (
              <MetadataStrip
                dataset_id={queryState.result.dataset_id}
                source={queryState.result.source}
                status_kind="query"
                status={queryState.result.status}
                data_origin={queryState.result.data_origin}
                freshness_status={freshness?.status ?? null}
                degradation_reason={queryState.result.degradation_reason}
                schema_version={health?.schema_version ?? null}
                snapshot_age_label={
                  freshness?.snapshot_age_seconds != null
                    ? formatAge(freshness.snapshot_age_seconds)
                    : null
                }
              />
            )}

            <ResultPanel
              queryState={queryState}
              isStale={shouldShowStaleState}
            />

            <div className="flex flex-wrap items-center gap-3 text-xs text-ink-700">
              {queryState.kind === "ready" &&
                queryState.result.total_records_before_filter != null && (
                  <span>
                    {ar.query.totalBeforeFilter}:{" "}
                    <span className="num-latn">
                      {formatNumber(queryState.result.total_records_before_filter)}
                    </span>
                  </span>
                )}
              {queryState.kind === "ready" &&
                queryState.result.status === "success" && (
                  <span>
                    {ar.query.matchedCount}:{" "}
                    <span className="num-latn">
                      {formatNumber(queryState.result.matched_records.length)}
                    </span>
                  </span>
                )}
              {queryState.kind === "ready" && queryState.result.limit != null && (
                <span>
                  {ar.query.limitApplied}:{" "}
                  <span className="num-latn">
                    {formatNumber(queryState.result.limit)}
                  </span>
                </span>
<<<<<<< HEAD
              </span>
            )}
            {result.status === "success" && (
              <span>
                {ar.query.matchedCount}:{" "}
                <span className="num-latn">
                  {formatNumber(result.matched_records.length)}
                </span>
              </span>
            )}
            {result.limit != null && (
              <span>
                {ar.query.limitApplied}:{" "}
                <span className="num-latn">{formatNumber(result.limit)}</span>
              </span>
            )}
            <label
              htmlFor="query-export-format"
              className="text-xs font-medium text-ink-700"
            >
              {ar.query.exportFormatLabel}
            </label>
            <select
              id="query-export-format"
              value={exportFormat}
              disabled={isLoading || isUnauthorized}
              onChange={(event) =>
                setExportFormat(event.target.value as ExportArtifactFormat)
              }
              className="rounded-md border border-ink-300 bg-white px-2 py-1.5 text-xs text-ink-700 shadow-sm focus:border-ink-700 focus:outline-none focus:ring-1 focus:ring-ink-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="json">{ar.query.exportFormats.json}</option>
              <option value="excel">{ar.query.exportFormats.excel}</option>
              <option value="pdf">{ar.query.exportFormats.pdf}</option>
            </select>
            <button
              type="button"
              onClick={handleExport}
              disabled={isLoading || isUnauthorized}
              className="rounded-md border border-ink-300 bg-white px-3 py-1.5 font-medium text-ink-700 hover:bg-ink-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {ar.query.export}
            </button>
            <span className="id-mono text-ink-500">role={role}</span>
=======
              )}
              <button
                type="button"
                onClick={handleExport}
                disabled={queryState.kind !== "ready"}
                className="rounded-md border border-ink-300 bg-white px-3 py-1.5 font-medium text-ink-700 hover:bg-ink-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {ar.query.export}
              </button>
              {role && <span className="id-mono text-ink-500">role={role}</span>}
            </div>
>>>>>>> feat/dashboard-codex-alt
          </div>
        </section>
      )}
    </div>
  );
}

function ResultPanel({
  queryState,
  isStale,
}: {
  queryState: QueryState;
  isStale: boolean;
}) {
  if (queryState.kind === "loading") {
    return <LoadingState />;
  }

  if (queryState.kind === "failed") {
    if (queryState.error.kind === "unauthorized") {
      return <UnauthorizedState />;
    }
    return (
      <ErrorState
        stage={queryState.error.stage}
        errorType={queryState.error.name}
        message={queryState.error.message}
      />
    );
  }

  const result = queryState.result;
  switch (result.status) {
    case "missing":
      return <MissingState />;
    case "snapshot_missing":
      return <SnapshotMissingState />;
    case "limited":
      return <LimitedState limitations={result.limitations} />;
    case "failed":
      return (
        <ErrorState
          stage={result.failure?.stage ?? result.failure_stage}
          errorType={result.failure?.error_type}
          message={result.failure?.message}
        />
      );
    case "success":
      if (result.matched_records.length === 0) {
        return <EmptyState />;
      }
      return (
        <div className="flex flex-col gap-2">
          {isStale && <StaleState />}
          <ResultTable records={result.matched_records} />
        </div>
      );
  }
}
