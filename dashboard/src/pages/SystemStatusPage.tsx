import { HealthCard } from "../components/HealthCard";
import { ar } from "../i18n/ar";
import { formatDateTime, formatNumber } from "../lib/format";
import {
  getHealthEntries,
  getMaterializationSummary,
  getReadinessReport,
} from "../mocks/health";
import { getObservabilitySummary } from "../mocks/status";

export function SystemStatusPage() {
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

      <ReadinessPanel />
      <MaterializationPanel />
      <SourcesPanel />
      <CountersPanel />
    </div>
  );
}

function ReadinessPanel() {
  const report = getReadinessReport();
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
          {Object.entries(report.checks).map(([name, status]) => (
            <li
              key={name}
              className="flex items-center justify-between rounded border border-ink-100 bg-ink-50 px-2 py-1"
            >
              <span className="id-mono text-ink-700">{name}</span>
              <span
                className={
                  status === "ok"
                    ? "text-emerald-800"
                    : "text-rose-800"
                }
              >
                {status}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function MaterializationPanel() {
  const summary = getMaterializationSummary();
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
        <InfoRow label={ar.status.materialization.lastRunAt}>
          <span className="num-latn">
            {formatDateTime(summary.last_run_at)}
          </span>
        </InfoRow>
        <InfoRow label={`${ar.status.materialization.tierA} — ${ar.status.materialization.successCount}`}>
          <span className="num-latn">
            {formatNumber(summary.tier_a_success_count)}
          </span>
        </InfoRow>
        <InfoRow label={`${ar.status.materialization.tierA} — ${ar.status.materialization.failureCount}`}>
          <span className="num-latn">
            {formatNumber(summary.tier_a_failure_count)}
          </span>
        </InfoRow>
        <InfoRow label={`${ar.status.materialization.tierB} — ${ar.status.materialization.successCount}`}>
          <span className="num-latn">
            {formatNumber(summary.tier_b_success_count)}
          </span>
        </InfoRow>
      </dl>
    </section>
  );
}

function SourcesPanel() {
  const healthEntries = getHealthEntries();
  return (
    <section
      className="flex flex-col gap-3"
      aria-labelledby="sources-heading"
    >
      <header className="flex flex-col">
        <h3 id="sources-heading" className="text-sm font-semibold text-ink-900">
          {ar.status.sources.title}
        </h3>
        <p className="text-xs text-ink-500">{ar.status.sources.summary}</p>
      </header>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {healthEntries.map((entry) => (
          <HealthCard key={entry.dataset_id} health={entry} />
        ))}
      </div>
    </section>
  );
}

function CountersPanel() {
  const observability = getObservabilitySummary();
  return (
    <section
      className="flex flex-col gap-3"
      aria-labelledby="counters-heading"
    >
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
