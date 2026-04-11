import { ar } from "../i18n/ar";
import { formatAge } from "../lib/format";
import { SOURCE_LABELS } from "../lib/catalogPresentation";
import type {
  DatasetHealthLookupResult,
  DatasetPreviewResult,
} from "../types/core";
import { CardDisclosure } from "./CardDisclosure";
import { DatasetStateOverview } from "./DatasetStateOverview";
import { MetadataStrip } from "./MetadataStrip";
import { SnapshotContextBlock } from "./SnapshotContextBlock";

interface HealthCardProps {
  title: string;
  health: DatasetHealthLookupResult;
  preview: DatasetPreviewResult | null;
  previewErrorMessage?: string | null;
}

export function HealthCard({
  title,
  health,
  preview,
  previewErrorMessage = null,
}: HealthCardProps) {
  if (health.status === "missing") {
    return null;
  }
  const freshness = health.freshness;
  const sourceLabel = health.source
    ? (SOURCE_LABELS[health.source] ?? health.source)
    : null;
  const dataOrigin =
    preview?.data_origin ??
    (freshness?.artifact_present ? "local_snapshot" : null);
  const snapshotAgeLabel =
    freshness?.snapshot_age_seconds != null
      ? formatAge(freshness.snapshot_age_seconds)
      : null;
  const snapshotTimestamp =
    freshness?.snapshot_modified_at ?? preview?.snapshot_modified_at ?? null;
  const hasTechnicalMetadata = Boolean(health.schema_version);
  return (
    <article className="flex h-full flex-col gap-4 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-col gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
          <p className="id-mono text-[0.75rem] text-ink-500">{health.dataset_id}</p>
          <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-500">
            <span>{ar.home.cardLabels.source}:</span>
            <span className="text-ink-700">{sourceLabel ?? "—"}</span>
            {health.source && (
              <span className="id-mono rounded bg-ink-100 px-1.5 py-0.5 text-[0.72rem] text-ink-500">
                {health.source}
              </span>
            )}
          </p>
        </div>
      </header>

      <DatasetStateOverview
        previewStatus={preview?.status ?? null}
        previewLimitations={preview?.limitations ?? []}
        previewErrorMessage={previewErrorMessage}
        healthStatus={health.health_status ?? null}
        freshnessStatus={freshness?.status ?? null}
        dataOrigin={dataOrigin}
      />

      <SnapshotContextBlock
        timestamp={snapshotTimestamp}
        ageLabel={snapshotAgeLabel}
      />

      {(health.caveats.length > 0 || health.known_issues.length > 0) && (
        <div className="flex flex-col gap-2">
          <CardDisclosure
            summary={ar.cards.operationalNotes}
            items={health.caveats}
          />
          <CardDisclosure
            summary={ar.cards.knownIssues}
            items={health.known_issues}
            tone="warn"
          />
        </div>
      )}

      {hasTechnicalMetadata && (
        <div className="border-t border-ink-200 pt-3">
          <MetadataStrip
            dataset_id={health.dataset_id}
            source={health.source}
            variant="flat"
            showTitle={false}
            hiddenFields={[
              "dataset_id",
              "source",
              "status",
              "freshness",
              "data_origin",
              "snapshot_age",
            ]}
            status_kind="health"
            status={health.health_status ?? "unknown"}
            data_origin={dataOrigin}
            freshness_status={freshness?.status ?? null}
            schema_version={health.schema_version}
            snapshot_age_label={snapshotAgeLabel}
          />
        </div>
      )}
    </article>
  );
}
