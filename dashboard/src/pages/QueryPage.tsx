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
  DegradedState,
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
import { FIELD_LABELS } from "../lib/fieldLabels";
import { formatAge, formatCellValue, formatNumber } from "../lib/format";
import {
  getDatasetHealthResult,
  getDatasetQueryResult,
  listDatasets,
} from "../lib/liveData";
import { DashboardApiError, asDashboardApiError } from "../lib/mcpClient";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  DatasetQueryResult,
  QueryFilterValue,
} from "../types/core";

type CatalogState =
  | { kind: "loading" }
  | { kind: "failed"; error: DashboardApiError }
  | { kind: "ready"; datasets: DatasetCatalogEntry[] };

type QueryState =
  | { kind: "loading" }
  | { kind: "failed"; error: DashboardApiError }
  | { kind: "ready"; result: DatasetQueryResult };

export function QueryPage() {
  const [searchParams] = useSearchParams();
  const [catalogState, setCatalogState] = useState<CatalogState>({
    kind: "loading",
  });
  const [datasetId, setDatasetId] = useState("");
  const [filters, setFilters] = useState<FilterRow[]>([]);
  const [limit, setLimit] = useState("100");
  const [exportFormat, setExportFormat] = useState<ExportArtifactFormat>("json");
  const [appliedFilters, setAppliedFilters] = useState<
    Record<string, QueryFilterValue>
  >({});
  const [appliedLimit, setAppliedLimit] = useState<number | null>(100);
  const [queryState, setQueryState] = useState<QueryState>({ kind: "loading" });
  const [health, setHealth] = useState<DatasetHealthLookupResult | null>(null);
  const [healthError, setHealthError] = useState<DashboardApiError | null>(null);
  const [catalogReloadToken, setCatalogReloadToken] = useState(0);

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
      setHealthError(null);
      return;
    }

    const controller = new AbortController();
    setHealth(null);
    setHealthError(null);
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
      } catch (error) {
        if (!controller.signal.aborted) {
          setHealth(null);
          setHealthError(
            new DashboardApiError(
              "validation",
              "query_health",
              "تعذّر تحميل سياق الصحة والحداثة لهذا الاستعلام.",
              { cause: error },
            ),
          );
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

  const freshness = health?.freshness ?? null;
  const showHealthDegradation =
    queryState.kind === "ready" &&
    queryState.result.status !== "failed" &&
    healthError;

  function handleExport() {
    if (queryState.kind !== "ready") {
      return;
    }
    downloadQueryExportArtifact({
      format: exportFormat,
      result: queryState.result,
      freshnessStatus: freshness?.status ?? null,
    });
  }

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

            {showHealthDegradation && (
              <DegradedState
                title={ar.query.auxiliaryContext.title}
                body={ar.query.auxiliaryContext.body}
                stage={healthError.stage}
                errorType={healthError.name}
                message={healthError.message}
                testId="query-health-degraded"
              />
            )}

            {queryState.kind === "ready" && (
              <QueryResultSummary
                result={queryState.result}
                exportFormat={exportFormat}
                onExportFormatChange={setExportFormat}
                onExport={handleExport}
              />
            )}

            <ResultPanel queryState={queryState} isStale={shouldShowStaleState} />
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
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-ink-900">
              {ar.query.table.heading}
            </h3>
            <p className="text-xs leading-relaxed text-ink-600">
              {ar.query.table.description}
            </p>
          </div>
          <ResultTable records={result.matched_records} />
        </div>
      );
  }
}

function QueryResultSummary({
  result,
  exportFormat,
  onExportFormatChange,
  onExport,
}: {
  result: DatasetQueryResult;
  exportFormat: ExportArtifactFormat;
  onExportFormatChange: (format: ExportArtifactFormat) => void;
  onExport: () => void;
}) {
  const appliedFilterEntries = Object.entries(result.applied_filters);
  const matchedCount =
    result.status === "success"
      ? formatNumber(result.matched_records.length)
      : "—";
  const totalBeforeFilter =
    result.total_records_before_filter != null
      ? formatNumber(result.total_records_before_filter)
      : "—";
  const limitApplied =
    result.limit != null ? formatNumber(result.limit) : ar.query.noLimitApplied;

  return (
    <section
      className="grid gap-4 rounded-xl border border-ink-200 bg-white p-4 shadow-sm xl:grid-cols-[minmax(0,1fr)_280px]"
      data-testid="query-result-summary"
    >
      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold text-ink-900">
            {ar.query.resultOverviewTitle}
          </h3>
          <p className="text-xs leading-relaxed text-ink-600">
            {ar.query.resultOverviewBody}
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryStatCard
            emphasized={result.status === "success"}
            label={ar.query.matchedCount}
            value={matchedCount}
          />
          <SummaryStatCard
            label={ar.query.totalBeforeFilter}
            value={totalBeforeFilter}
          />
          <SummaryStatCard
            label={ar.query.filterCount}
            value={formatNumber(appliedFilterEntries.length)}
          />
          <SummaryStatCard
            label={ar.query.limitApplied}
            value={limitApplied}
          />
        </div>

        <div className="flex flex-col gap-2 rounded-lg border border-ink-200 bg-ink-50 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold text-ink-800">
              {ar.query.appliedFilters}
            </p>
            <span className="num-latn text-xs text-ink-500">
              {formatNumber(appliedFilterEntries.length)}
            </span>
          </div>
          {appliedFilterEntries.length === 0 ? (
            <p className="text-xs text-ink-500">{ar.query.noAppliedFilters}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {appliedFilterEntries.map(([fieldName, value]) => (
                <span
                  key={fieldName}
                  className="flex flex-wrap items-center gap-2 rounded-full border border-ink-300 bg-white px-3 py-1.5 text-xs text-ink-700"
                >
                  <span className="font-medium text-ink-900">
                    {FIELD_LABELS[fieldName] ?? fieldName}
                  </span>
                  <span
                    className="id-mono text-[0.7rem] text-ink-500"
                    dir="ltr"
                  >
                    {fieldName}
                  </span>
                  <span className="num-latn rounded-full bg-ink-100 px-2 py-0.5 text-ink-900">
                    {formatCellValue(value)}
                  </span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div
        className="flex h-full flex-col gap-3 rounded-lg border border-ink-200 bg-ink-50 px-4 py-4"
        data-testid="query-export-controls"
      >
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold text-ink-900">
            {ar.query.exportCurrentTitle}
          </h3>
          <p className="text-xs leading-relaxed text-ink-600">
            {ar.query.exportCurrentBody}
          </p>
        </div>

        <label
          htmlFor="query-export-format"
          className="text-xs font-medium text-ink-700"
        >
          {ar.query.exportFormatLabel}
        </label>
        <select
          id="query-export-format"
          value={exportFormat}
          onChange={(event) =>
            onExportFormatChange(event.target.value as ExportArtifactFormat)
          }
          className="rounded-md border border-ink-300 bg-white px-3 py-2 text-sm text-ink-700 shadow-sm focus:border-ink-700 focus:outline-none focus:ring-1 focus:ring-ink-700"
        >
          <option value="json">{ar.query.exportFormats.json}</option>
          <option value="excel">{ar.query.exportFormats.excel}</option>
          <option value="pdf">{ar.query.exportFormats.pdf}</option>
        </select>
        <button
          type="button"
          onClick={onExport}
          className="rounded-md border border-ink-900 bg-ink-900 px-3 py-2 text-sm font-medium text-white hover:bg-ink-700"
        >
          {ar.query.export}
        </button>
        <p className="text-[0.72rem] leading-5 text-ink-500">
          {ar.query.exportCurrentHint}
        </p>
      </div>
    </section>
  );
}

function SummaryStatCard({
  emphasized = false,
  label,
  value,
}: {
  emphasized?: boolean;
  label: string;
  value: string;
}) {
  return (
    <div
      className={[
        "flex flex-col gap-1 rounded-lg border px-3 py-3",
        emphasized
          ? "border-ink-900 bg-ink-900 text-white"
          : "border-ink-200 bg-ink-50 text-ink-900",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span
        className={[
          "text-[0.72rem] font-medium",
          emphasized ? "text-white/80" : "text-ink-600",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {label}
      </span>
      <span className="num-latn text-lg font-semibold">{value}</span>
    </div>
  );
}
