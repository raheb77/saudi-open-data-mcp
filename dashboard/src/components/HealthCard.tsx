import { ar } from "../i18n/ar";
import { formatAge, formatDateTime } from "../lib/format";
import { SOURCE_LABELS } from "../mocks/datasets";
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
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-col">
          <h3 className="text-sm font-semibold text-ink-900">
            {SOURCE_LABELS[health.source ?? ""] ?? health.source}
          </h3>
          <span className="id-mono text-[0.75rem] text-ink-500">
            {health.dataset_id}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {health.health_status && (
            <HealthStatusBadge status={health.health_status} />
          )}
          {freshness && <FreshnessBadge status={freshness.status} />}
        </div>
      </header>

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
        status="success"
        data_origin={freshness?.artifact_present ? "local_snapshot" : null}
        freshness_status={freshness?.status ?? null}
        schema_version={health.schema_version}
        snapshot_age_label={
          freshness?.snapshot_age_seconds != null
            ? formatAge(freshness.snapshot_age_seconds)
            : null
        }
      />

      {freshness?.snapshot_modified_at && (
        <p className="text-xs text-ink-500">
          {ar.home.cardLabels.lastUpdated}:{" "}
          <span className="num-latn">
            {formatDateTime(freshness.snapshot_modified_at)}
          </span>
        </p>
      )}
    </article>
  );
}
