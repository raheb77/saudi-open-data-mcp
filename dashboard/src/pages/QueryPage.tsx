import { useEffect, useMemo, useState } from "react";
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
import { MOCK_DATASETS } from "../mocks/datasets";
import { findHealthById } from "../mocks/health";
import {
  buildMockQueryResult,
  type QueryScenarioName,
} from "../mocks/queryResults";

interface QueryPageProps {
  role: "viewer" | "operator" | "admin";
}

const SCENARIOS: ReadonlyArray<{
  value: QueryScenarioName;
  labelKey: keyof typeof ar.query.scenarios;
}> = [
  { value: "success", labelKey: "success" },
  { value: "limited", labelKey: "limited" },
  { value: "stale", labelKey: "stale" },
  { value: "failed", labelKey: "failed" },
  { value: "missing", labelKey: "missing" },
  { value: "snapshot_missing", labelKey: "snapshotMissing" },
  { value: "unauthorized", labelKey: "unauthorized" },
  { value: "loading", labelKey: "loading" },
];

export function QueryPage({ role }: QueryPageProps) {
  const [searchParams] = useSearchParams();
  const initialDataset =
    searchParams.get("dataset") ?? MOCK_DATASETS[0].dataset_id;

  const [datasetId, setDatasetId] = useState<string>(initialDataset);
  const [filters, setFilters] = useState<FilterRow[]>([]);
  const [limit, setLimit] = useState<string>("100");
  const [scenario, setScenario] = useState<QueryScenarioName>("success");
  const [exportFormat, setExportFormat] = useState<ExportArtifactFormat>("json");
  const [appliedSignal, setAppliedSignal] = useState(0);

  useEffect(() => {
    const fromUrl = searchParams.get("dataset");
    if (fromUrl && fromUrl !== datasetId) {
      setDatasetId(fromUrl);
    }
    // We intentionally only react to url changes, not to local edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const result = useMemo(() => {
    const parsedLimit = Number(limit);
    const effectiveLimit =
      Number.isFinite(parsedLimit) && parsedLimit > 0 ? parsedLimit : null;
    return buildMockQueryResult(
      datasetId,
      scenario,
      filterRowsToFilters(filters),
      effectiveLimit,
    );
    // appliedSignal forces recomputation on "Apply" so that edits stay
    // local until the user presses the button — matching the CLI feel.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, scenario, appliedSignal]);

  const health = findHealthById(datasetId);
  const freshness = health?.freshness ?? null;

  const isUnauthorized = scenario === "unauthorized";
  const isLoading = scenario === "loading";

  function handleApply() {
    setAppliedSignal((v) => v + 1);
  }

  function handleReset() {
    setFilters([]);
    setLimit("100");
    setScenario("success");
    setAppliedSignal((v) => v + 1);
  }

  function handleExport() {
    if (isLoading || isUnauthorized) return;

    downloadQueryExportArtifact({
      format: exportFormat,
      result,
      freshnessStatus: freshness?.status ?? null,
    });
  }

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

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col gap-4">
          <DatasetSelector value={datasetId} onChange={setDatasetId} />

          <div className="flex flex-col gap-1">
            <label
              htmlFor="scenario-selector"
              className="text-sm font-medium text-ink-700"
            >
              {ar.query.scenarioLabel}
            </label>
            <select
              id="scenario-selector"
              value={scenario}
              onChange={(event) =>
                setScenario(event.target.value as QueryScenarioName)
              }
              className="w-full rounded-md border border-ink-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-ink-700 focus:outline-none focus:ring-1 focus:ring-ink-700"
            >
              {SCENARIOS.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {ar.query.scenarios[entry.labelKey]}
                </option>
              ))}
            </select>
            <span className="id-mono text-[0.75rem] text-ink-500">
              {scenario}
            </span>
          </div>

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
          <MetadataStrip
            dataset_id={result.dataset_id}
            source={result.source}
            status={result.status}
            data_origin={result.data_origin}
            freshness_status={freshness?.status ?? null}
            degradation_reason={result.degradation_reason}
            schema_version={health?.schema_version ?? null}
            snapshot_age_label={
              freshness?.snapshot_age_seconds != null
                ? formatAge(freshness.snapshot_age_seconds)
                : null
            }
          />

          <ResultPanel
            result={result}
            isLoading={isLoading}
            isUnauthorized={isUnauthorized}
          />

          <div className="flex flex-wrap items-center gap-3 text-xs text-ink-700">
            {result.total_records_before_filter != null && (
              <span>
                {ar.query.totalBeforeFilter}:{" "}
                <span className="num-latn">
                  {formatNumber(result.total_records_before_filter)}
                </span>
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
          </div>
        </div>
      </section>
    </div>
  );
}

interface ResultPanelProps {
  result: ReturnType<typeof buildMockQueryResult>;
  isLoading: boolean;
  isUnauthorized: boolean;
}

function ResultPanel({
  result,
  isLoading,
  isUnauthorized,
}: ResultPanelProps) {
  if (isLoading) return <LoadingState />;
  if (isUnauthorized) return <UnauthorizedState />;

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
          {result.degradation_reason ===
            "stale_fallback_after_refresh_failure" && <StaleState />}
          <ResultTable records={result.matched_records} />
        </div>
      );
    default:
      return <EmptyState />;
  }
}
