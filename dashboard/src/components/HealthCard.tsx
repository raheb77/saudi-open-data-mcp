import { ar } from "../i18n/ar";
import { formatAge, formatDateTime } from "../lib/format";
import { SOURCE_LABELS } from "../lib/catalogPresentation";
import type { DatasetHealthLookupResult } from "../types/core";
import { MetadataStrip } from "./MetadataStrip";
import { FreshnessBadge, HealthStatusBadge } from "./StatusBadge";

interface HealthCardProps {
  health: DatasetHealthLookupResult;
}

export function HealthCard({ health }: HealthCardProps) {
  if (health.status === "missing") {
    return null;
  }
  const freshness = health.freshness;
  const sourceLabel = health.source
    ? (SOURCE_LABELS[health.source] ?? health.source)
    : null;
  const dataOrigin = freshness?.artifact_present ? "local_snapshot" : null;
  const hiddenFields = dataOrigin
    ? (["dataset_id", "source", "status", "freshness"] as const)
    : (["dataset_id", "source", "status", "freshness", "data_origin"] as const);
  const snapshotAgeLabel =
    freshness?.snapshot_age_seconds != null
      ? formatAge(freshness.snapshot_age_seconds)
      : null;
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="id-mono text-sm font-semibold text-ink-900">
            {health.dataset_id}
          </h3>
          <p className="text-xs text-ink-500">
            <span>{sourceLabel ?? "—"}</span>
            {health.source && (
              <span className="id-mono ms-2 text-[0.75rem] text-ink-500">
                {health.source}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {health.health_status && (
            <HealthStatusBadge status={health.health_status} />
          )}
          {freshness && <FreshnessBadge status={freshness.status} />}
        </div>
      </header>

      {freshness?.snapshot_modified_at && (
        <p className="text-xs text-ink-500">
          {ar.home.cardLabels.lastUpdated}:{" "}
          <span className="num-latn">
            {formatDateTime(freshness.snapshot_modified_at)}
          </span>
        </p>
      )}

      {(health.caveats.length > 0 || health.known_issues.length > 0) && (
        <div className="text-xs text-ink-700">
          {health.caveats.length > 0 && (
            <ul className="list-disc space-y-1 ps-5">
              {health.caveats.map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          )}
          {health.known_issues.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 ps-5 text-amber-900">
              {health.known_issues.map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <MetadataStrip
        dataset_id={health.dataset_id}
        source={health.source}
        variant="flat"
        showTitle={false}
        hiddenFields={hiddenFields}
        status_kind="health"
        status={health.health_status ?? "unknown"}
        data_origin={dataOrigin}
        freshness_status={freshness?.status ?? null}
        schema_version={health.schema_version}
        snapshot_age_label={snapshotAgeLabel}
      />
    </article>
  );
}
