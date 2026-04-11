import { Link } from "react-router-dom";
import { ar } from "../i18n/ar";
import { formatAge } from "../lib/format";
import { SOURCE_LABELS } from "../lib/catalogPresentation";
import type {
  DatasetCatalogEntry,
  DatasetPreviewResult,
  DatasetHealthLookupResult,
} from "../types/core";
import { DatasetStateOverview } from "./DatasetStateOverview";
import { MetadataStrip } from "./MetadataStrip";
import { SnapshotContextBlock } from "./SnapshotContextBlock";

interface DatasetCardProps {
  catalog: DatasetCatalogEntry;
  preview: DatasetPreviewResult;
  health: DatasetHealthLookupResult | undefined;
}

export function DatasetCard({ catalog, preview, health }: DatasetCardProps) {
  const snapshotAgeLabel =
    health?.freshness?.snapshot_age_seconds != null
      ? formatAge(health.freshness.snapshot_age_seconds)
      : null;
  const snapshotTimestamp =
    preview.snapshot_modified_at ?? health?.freshness?.snapshot_modified_at ?? null;
  const hasTechnicalMetadata = Boolean(
    preview.degradation_reason || health?.schema_version,
  );

  return (
    <article className="flex h-full flex-col gap-4 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-ink-900">{catalog.title}</h3>
        <span className="id-mono text-[0.75rem] text-ink-500">
          {catalog.dataset_id}
        </span>
        <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-500">
          <span>{ar.home.cardLabels.source}:</span>
          <span className="text-ink-700">
            {SOURCE_LABELS[catalog.source] ?? catalog.source}
          </span>
          <span className="id-mono rounded bg-ink-100 px-1.5 py-0.5 text-[0.72rem] text-ink-500">
            {catalog.source}
          </span>
        </p>
      </header>

      <DatasetStateOverview
        previewStatus={preview.status}
        previewLimitations={preview.limitations}
        freshnessStatus={preview.freshness_status}
        dataOrigin={preview.data_origin}
        healthStatus={health?.health_status ?? null}
      />

      <SnapshotContextBlock
        timestamp={snapshotTimestamp}
        ageLabel={snapshotAgeLabel}
      />

      {hasTechnicalMetadata && (
        <div className="border-t border-ink-200 pt-3">
          <MetadataStrip
            dataset_id={catalog.dataset_id}
            source={catalog.source}
            variant="flat"
            showTitle={false}
            hiddenFields={[
              "dataset_id",
              "source",
              "status",
              "data_origin",
              "freshness",
              "snapshot_age",
            ]}
            status_kind="preview"
            status={preview.status}
            data_origin={preview.data_origin}
            freshness_status={preview.freshness_status}
            degradation_reason={preview.degradation_reason}
            schema_version={health?.schema_version ?? null}
            snapshot_age_label={snapshotAgeLabel}
          />
        </div>
      )}

      <Link
        to={`/query?dataset=${encodeURIComponent(catalog.dataset_id)}`}
        className="mt-auto self-start rounded-md border border-ink-300 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
      >
        {ar.home.cardLabels.openInQuery}
      </Link>
    </article>
  );
}
