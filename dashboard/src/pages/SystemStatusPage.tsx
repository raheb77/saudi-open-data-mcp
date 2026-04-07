import { useEffect, useState } from "react";
import { HealthCard } from "../components/HealthCard";
import {
  ErrorState,
  LoadingState,
  MissingState,
  UnauthorizedState,
} from "../components/StateBlocks";
import { ar } from "../i18n/ar";
import { SOURCE_LABELS } from "../lib/catalogPresentation";
import { formatNumber } from "../lib/format";
import {
  getDatasetHealthResult,
  getObservability,
  getReadiness,
  listDatasets,
} from "../lib/liveData";
import { DashboardApiError, asDashboardApiError } from "../lib/mcpClient";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  ObservabilitySummary,
  ReadinessReport,
} from "../types/core";

interface SourceHealthCardData {
  catalog: DatasetCatalogEntry;
  health: DatasetHealthLookupResult | null;
  error: DashboardApiError | null;
}

type StatusPageState =
  | { kind: "loading" }
  | { kind: "failed"; error: DashboardApiError }
  | {
      kind: "ready";
      readiness: ReadinessReport;
      observability: ObservabilitySummary;
      healthCards: SourceHealthCardData[];
    };

export function SystemStatusPage() {
  const [state, setState] = useState<StatusPageState>({ kind: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });

    void (async () => {
      try {
        const [readiness, observability, datasets] = await Promise.all([
          getReadiness(controller.signal),
          getObservability(controller.signal),
          listDatasets(controller.signal),
        ]);

        const healthCards = await Promise.all(
          datasets.map(async (catalog) => {
            try {
              return {
                catalog,
                health: await getDatasetHealthResult(
                  catalog.dataset_id,
                  catalog.source,
                  controller.signal,
                ),
                error: null,
              } satisfies SourceHealthCardData;
            } catch (error) {
              return {
                catalog,
                health: null,
                error: asDashboardApiError(
                  error,
                  "status_health",
                  "تعذّر تحميل حالة هذه المجموعة.",
                ),
              } satisfies SourceHealthCardData;
            }
          }),
        );

        if (!controller.signal.aborted) {
          setState({
            kind: "ready",
            readiness,
            observability,
            healthCards,
          });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setState({
            kind: "failed",
            error: asDashboardApiError(
              error,
              "status_page",
              "تعذّر تحميل صفحة حالة النظام من النواة الحية.",
            ),
          });
        }
      }
    })();

    return () => controller.abort();
  }, [reloadToken]);

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold text-ink-900">
          {ar.status.heading}
        </h2>
        <p className="max-w-3xl text-sm leading-relaxed text-ink-700">
          {ar.status.description}
        </p>
      </section>

      {state.kind === "loading" && <LoadingState />}

      {state.kind === "failed" && (
        <section className="flex flex-col gap-3">
          {state.error.kind === "unauthorized" ? (
            <UnauthorizedState />
          ) : (
            <ErrorState
              stage={state.error.stage}
              errorType={state.error.name}
              message={state.error.message}
            />
          )}
          <button
            type="button"
            onClick={() => setReloadToken((value) => value + 1)}
            className="self-start rounded-md border border-ink-300 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
          >
            {ar.app.retry}
          </button>
        </section>
      )}

      {state.kind === "ready" && (
        <>
          <ReadinessPanel report={state.readiness} />
          <MaterializationPanel observability={state.observability} />
          <SourcesPanel cards={state.healthCards} />
          <CountersPanel observability={state.observability} />
        </>
      )}
    </div>
  );
}

function ReadinessPanel({ report }: { report: ReadinessReport }) {
  return (
    <section
      className="rounded-xl border border-ink-300 bg-white p-4 shadow-sm"
      aria-labelledby="readiness-heading"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="readiness-heading" className="text-sm font-semibold text-ink-900">
          {ar.status.readiness.title}
        </h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            report.ready
              ? "bg-emerald-100 text-emerald-900"
              : "bg-rose-100 text-rose-900"
          }`}
        >
          {report.ready
            ? ar.status.readiness.ready
            : ar.status.readiness.notReady}
        </span>
      </header>
      <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <InfoRow label={ar.status.readiness.appName}>
          <span className="id-mono">{report.app_name}</span>
        </InfoRow>
        <InfoRow label={ar.status.readiness.scope}>
          <span className="id-mono">{report.scope}</span>
        </InfoRow>
      </dl>
      <div className="mt-3">
        <p className="text-xs font-medium text-ink-500">
          {ar.status.readiness.checks}
        </p>
        <ul className="mt-1 space-y-1 text-xs">
          {Object.entries(report.checks).map(([name, status]) => {
            const isOk = status === true || status === "ok";
            return (
              <li
                key={name}
                className="flex items-center justify-between rounded border border-ink-100 bg-ink-50 px-2 py-1"
              >
                <span className="id-mono text-ink-700">{name}</span>
                <span className={isOk ? "text-emerald-800" : "text-rose-800"}>
                  {isOk ? "ok" : "fail"}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function MaterializationPanel({
  observability,
}: {
  observability: ObservabilitySummary;
}) {
  return (
    <section
      className="rounded-xl border border-ink-300 bg-white p-4 shadow-sm"
      aria-labelledby="materialization-heading"
    >
      <h3
        id="materialization-heading"
        className="text-sm font-semibold text-ink-900"
      >
        {ar.status.materialization.title}
      </h3>
      <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <InfoRow label={ar.status.materialization.runCount}>
          <span className="num-latn">
            {formatNumber(observability.raw_counters["materialize.requests"] ?? 0)}
          </span>
        </InfoRow>
        <InfoRow label={ar.status.materialization.successCount}>
          <span className="num-latn">
            {formatNumber(
              observability.raw_counters["materialize.successes"] ?? 0,
            )}
          </span>
        </InfoRow>
        <InfoRow label={ar.status.materialization.failureCount}>
          <span className="num-latn">
            {formatNumber(observability.raw_counters["materialize.failures"] ?? 0)}
          </span>
        </InfoRow>
      </dl>
      <p className="mt-3 text-xs leading-relaxed text-ink-500">
        {ar.status.materialization.liveNote}
      </p>
    </section>
  );
}

function SourcesPanel({ cards }: { cards: SourceHealthCardData[] }) {
  return (
    <section className="flex flex-col gap-3" aria-labelledby="sources-heading">
      <header className="flex flex-col">
        <h3 id="sources-heading" className="text-sm font-semibold text-ink-900">
          {ar.status.sources.title}
        </h3>
        <p className="text-xs text-ink-500">{ar.status.sources.summary}</p>
      </header>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((entry) =>
          entry.health && entry.health.status === "found" ? (
            <HealthCard key={entry.catalog.dataset_id} health={entry.health} />
          ) : (
            <HealthFailureCard key={entry.catalog.dataset_id} entry={entry} />
          ),
        )}
      </div>
    </section>
  );
}

function HealthFailureCard({ entry }: { entry: SourceHealthCardData }) {
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-ink-900">{entry.catalog.title}</h3>
        <span className="id-mono text-[0.75rem] text-ink-500">
          {entry.catalog.dataset_id}
        </span>
      </header>
      <p className="text-xs text-ink-500">
        {SOURCE_LABELS[entry.catalog.source] ?? entry.catalog.source}
        <span className="id-mono ms-2">{entry.catalog.source}</span>
      </p>
      {entry.error?.kind === "unauthorized" ? (
        <UnauthorizedState />
      ) : entry.error ? (
        <ErrorState
          stage={entry.error.stage}
          errorType={entry.error.name}
          message={entry.error.message}
        />
      ) : (
        <MissingState />
      )}
    </article>
  );
}

function CountersPanel({
  observability,
}: {
  observability: ObservabilitySummary;
}) {
  return (
    <section className="flex flex-col gap-3" aria-labelledby="counters-heading">
      <header className="flex flex-col">
        <h3 id="counters-heading" className="text-sm font-semibold text-ink-900">
          {ar.status.counters.title}
        </h3>
        <p className="text-xs text-ink-500">{ar.status.counters.note}</p>
      </header>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {observability.groups.map((group) => (
          <article
            key={group.name}
            className="rounded-xl border border-ink-300 bg-white p-4 shadow-sm"
          >
            <header className="flex items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-ink-900">
                <span className="id-mono">{group.name}</span>
              </h4>
            </header>
            <p className="mt-1 text-xs leading-relaxed text-ink-700">
              {group.summary}
            </p>
            <ul className="mt-3 space-y-1 text-xs">
              {group.counters.map((counter) => (
                <li
                  key={counter.name}
                  className="flex items-center justify-between rounded border border-ink-100 bg-ink-50 px-2 py-1"
                >
                  <span className="id-mono text-ink-700">{counter.name}</span>
                  <span className="num-latn font-medium text-ink-900">
                    {formatNumber(counter.value)}
                  </span>
                </li>
              ))}
              {group.detail_counters.length > 0 && (
                <li className="mt-2">
                  <ul className="space-y-1">
                    {group.detail_counters.map((counter) => (
                      <li
                        key={counter.name}
                        className="flex items-center justify-between rounded border border-ink-100 bg-white px-2 py-1"
                      >
                        <span className="id-mono text-ink-500">
                          {counter.name}
                        </span>
                        <span className="num-latn text-ink-700">
                          {formatNumber(counter.value)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </li>
              )}
            </ul>
          </article>
        ))}
      </div>
      {observability.notes.length > 0 && (
        <ul className="list-disc space-y-1 ps-5 text-xs text-ink-500">
          {observability.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function InfoRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-xs font-medium text-ink-500">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
