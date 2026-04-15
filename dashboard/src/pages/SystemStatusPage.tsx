import { useEffect, useState } from "react";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { HealthCard } from "../components/HealthCard";
import {
  DegradedState,
  ErrorState,
  LoadingState,
  MissingState,
  UnauthorizedState,
} from "../components/StateBlocks";
import { ar } from "../i18n/ar";
import { SOURCE_LABELS } from "../lib/catalogPresentation";
import { groupDatasetSurfaceEntries } from "../lib/datasetSurface";
import { formatNumber } from "../lib/format";
import {
  getDatasetHealthResult,
  getDatasetPreviewResult,
  getObservability,
  getReadiness,
  listDatasets,
} from "../lib/liveData";
import { DashboardApiError, asDashboardApiError } from "../lib/mcpClient";
import {
  translateStatusGroupSummary,
  translateStatusNote,
  translateStatusTerm,
} from "../lib/statusTerms";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  DatasetPreviewResult,
  ObservabilitySummary,
  ReadinessReport,
} from "../types/core";

interface SourceHealthCardData {
  catalog: DatasetCatalogEntry;
  health: DatasetHealthLookupResult | null;
  preview: DatasetPreviewResult | null;
  error: DashboardApiError | null;
  previewError: DashboardApiError | null;
}

type SectionState<T> =
  | { kind: "loading" }
  | { kind: "failed"; error: DashboardApiError }
  | { kind: "ready"; data: T };

interface StatusPageState {
  kind: "loading" | "ready";
  readiness: SectionState<ReadinessReport>;
  observability: SectionState<ObservabilitySummary>;
  healthCards: SectionState<SourceHealthCardData[]>;
}

function makeLoadingState(): StatusPageState {
  return {
    kind: "loading",
    readiness: { kind: "loading" },
    observability: { kind: "loading" },
    healthCards: { kind: "loading" },
  };
}

export function SystemStatusPage() {
  const [state, setState] = useState<StatusPageState>(makeLoadingState());
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState(makeLoadingState());

    void (async () => {
      const [readiness, observability, healthCards] = await Promise.allSettled([
        getReadiness(controller.signal),
        getObservability(controller.signal),
        loadHealthCards(controller.signal),
      ]);

      if (!controller.signal.aborted) {
        setState({
          kind: "ready",
          readiness: toSectionState(
            readiness,
            "status_readiness",
            "تعذّر تحميل قسم الجاهزية من النواة الحية.",
          ),
          observability: toSectionState(
            observability,
            "status_observability",
            "تعذّر تحميل مورد المراقبة الحية.",
          ),
          healthCards: toSectionState(
            healthCards,
            "status_sources",
            "تعذّر تحميل فهرس المجموعات أو حالة المصادر.",
          ),
        });
      }
    })();

    return () => controller.abort();
  }, [reloadToken]);

  const failedSections =
    state.kind === "ready"
      ? [
          state.readiness.kind === "failed" ? ar.status.readiness.title : null,
          state.observability.kind === "failed"
            ? ar.status.observability.title
            : null,
          state.healthCards.kind === "failed" ? ar.status.sources.title : null,
        ].filter((entry) => entry !== null)
      : [];

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumbs
        items={[
          { label: ar.app.nav.home, to: "/" },
          { label: ar.app.nav.systemStatus },
        ]}
      />

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold text-ink-900">
          {ar.status.heading}
        </h2>
        <p className="max-w-3xl text-sm leading-relaxed text-ink-700">
          {ar.status.description}
        </p>
      </section>

      {state.kind === "loading" && <LoadingState />}

      {state.kind === "ready" && (
        <>
          {failedSections.length > 0 && (
            <DegradedState
              title={ar.status.partialDegradation.title}
              body={ar.status.partialDegradation.body}
              testId="status-page-degraded"
            >
              <p className="text-tone-warn text-xs font-medium">
                {ar.status.partialDegradation.affectedSections}
              </p>
              <ul className="text-tone-warn mt-1 list-disc space-y-1 ps-5 text-xs">
                {failedSections.map((entry) => (
                  <li key={entry}>{entry}</li>
                ))}
              </ul>
              <button
                type="button"
                onClick={() => setReloadToken((value) => value + 1)}
                className="text-tone-warn mt-3 self-start rounded-md border bg-white px-3 py-1.5 text-xs font-medium hover:bg-ink-100"
                style={{ borderColor: "var(--color-warning-border)" }}
              >
                {ar.app.retry}
              </button>
            </DegradedState>
          )}

          {state.readiness.kind === "ready" ? (
            <ReadinessPanel report={state.readiness.data} />
          ) : (
            <SectionFailurePanel
              headingId="readiness-heading"
              title={ar.status.readiness.title}
              summary={ar.status.description}
              error={
                state.readiness.kind === "failed" ? state.readiness.error : null
              }
            />
          )}

          {state.observability.kind === "ready" ? (
            <>
              <MaterializationPanel observability={state.observability.data} />
              <CountersPanel observability={state.observability.data} />
            </>
          ) : (
            <SectionFailurePanel
              headingId="observability-heading"
              title={ar.status.observability.title}
              summary={ar.status.observability.summary}
              error={
                state.observability.kind === "failed"
                  ? state.observability.error
                  : null
              }
            />
          )}

          {state.healthCards.kind === "ready" ? (
            <SourcesPanel cards={state.healthCards.data} />
          ) : (
            <SectionFailurePanel
              headingId="sources-heading"
              title={ar.status.sources.title}
              summary={ar.status.sources.summary}
              error={
                state.healthCards.kind === "failed"
                  ? state.healthCards.error
                  : null
              }
            />
          )}
        </>
      )}
    </div>
  );
}

async function loadHealthCards(
  signal: AbortSignal,
): Promise<SourceHealthCardData[]> {
  const datasets = await listDatasets(signal);
  return Promise.all(
    datasets.map(async (catalog) => {
      const [healthResult, previewResult] = await Promise.allSettled([
        getDatasetHealthResult(catalog.dataset_id, catalog.source, signal),
        getDatasetPreviewResult(catalog.dataset_id, signal),
      ]);

      return {
        catalog,
        health: healthResult.status === "fulfilled" ? healthResult.value : null,
        preview:
          previewResult.status === "fulfilled" ? previewResult.value : null,
        error:
          healthResult.status === "rejected"
            ? asDashboardApiError(
                healthResult.reason,
                "status_health",
                "تعذّر تحميل حالة هذه المجموعة.",
              )
            : null,
        previewError:
          previewResult.status === "rejected"
            ? asDashboardApiError(
                previewResult.reason,
                "status_preview",
                "تعذّر تحميل حالة قابلية الاستعلام لهذه المجموعة.",
              )
            : null,
      } satisfies SourceHealthCardData;
    }),
  );
}

function toSectionState<T>(
  result: PromiseSettledResult<T>,
  stage: string,
  fallbackMessage: string,
): SectionState<T> {
  if (result.status === "fulfilled") {
    return { kind: "ready", data: result.value };
  }

  return {
    kind: "failed",
    error: asDashboardApiError(result.reason, stage, fallbackMessage),
  };
}

function SectionFailurePanel({
  headingId,
  title,
  summary,
  error,
}: {
  headingId: string;
  title: string;
  summary: string;
  error: DashboardApiError | null;
}) {
  return (
    <section className="flex flex-col gap-3" aria-labelledby={headingId}>
      <header className="flex flex-col">
        <h3 id={headingId} className="text-sm font-semibold text-ink-900">
          {title}
        </h3>
        <p className="hidden text-xs text-ink-500 md:block">{summary}</p>
      </header>
      {error?.kind === "unauthorized" ? (
        <UnauthorizedState />
      ) : (
        <ErrorState
          stage={error?.stage}
          errorType={error?.name}
          message={error?.message}
        />
      )}
    </section>
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
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
            report.ready ? "badge-tone-ok" : "badge-tone-bad"
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
          <span title={report.scope}>{translateStatusTerm(report.scope)}</span>
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
                <span className="text-ink-700" title={name}>
                  {translateStatusTerm(name)}
                </span>
                <span className={isOk ? "text-tone-ok" : "text-tone-bad"}>
                  {isOk ? ar.status.readiness.checkOk : ar.status.readiness.checkFail}
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
  const sections = groupDatasetSurfaceEntries(cards, {
    getCoverageStatus: (entry) =>
      entry.previewError
        ? "unavailable"
        : (entry.preview?.coverage_status ??
          entry.health?.coverage_status ??
          entry.catalog.coverage_status),
    getDatasetId: (entry) => entry.catalog.dataset_id,
    getTitle: (entry) => entry.catalog.title,
  });

  return (
    <section className="flex flex-col gap-3" aria-labelledby="sources-heading">
      <header className="flex flex-col">
        <h3 id="sources-heading" className="text-sm font-semibold text-ink-900">
          {ar.status.sources.title}
        </h3>
        <p className="text-xs text-ink-500">{ar.status.sources.summary}</p>
      </header>
      <div className="flex flex-col gap-6">
        {sections.map((section) => (
          <section
            key={section.coverageStatus}
            className="flex flex-col gap-3"
            aria-labelledby={`status-dataset-section-${section.coverageStatus}`}
            data-testid={`status-dataset-section-${section.coverageStatus}`}
          >
            <header className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-col gap-1">
                <h4
                  id={`status-dataset-section-${section.coverageStatus}`}
                  className="text-sm font-semibold text-ink-900"
                >
                  {section.title}
                </h4>
                <p className="max-w-3xl text-xs leading-relaxed text-ink-500">
                  {section.body}
                </p>
              </div>
              <span className="rounded-full bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-700">
                {ar.datasetSurface.countLabel}: {section.entries.length}
              </span>
            </header>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {section.entries.map((entry) =>
                entry.health && entry.health.status === "found" ? (
                  <HealthCard
                    key={entry.catalog.dataset_id}
                    title={entry.catalog.title}
                    health={entry.health}
                    preview={entry.preview}
                    previewErrorMessage={entry.previewError?.message ?? null}
                  />
                ) : (
                  <HealthFailureCard key={entry.catalog.dataset_id} entry={entry} />
                ),
              )}
            </div>
          </section>
        ))}
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
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-500">
        <span>{SOURCE_LABELS[entry.catalog.source] ?? entry.catalog.source}</span>
        <span className="id-mono">{entry.catalog.source}</span>
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
              <h4
                className="text-sm font-semibold text-ink-900"
                title={group.name}
              >
                {translateStatusTerm(group.name)}
              </h4>
            </header>
            <p className="mt-1 text-xs leading-relaxed text-ink-700">
              {translateStatusGroupSummary(group.name, group.summary)}
            </p>
            <ul className="mt-3 space-y-1 text-xs">
              {group.counters.map((counter) => (
                <li
                  key={counter.name}
                  className="flex items-center justify-between rounded border border-ink-100 bg-ink-50 px-2 py-1"
                >
                  <span className="text-ink-700" title={counter.name}>
                    {translateStatusTerm(counter.name)}
                  </span>
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
                        <span className="text-ink-500" title={counter.name}>
                          {translateStatusTerm(counter.name)}
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
            <li key={note}>{translateStatusNote(note)}</li>
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
