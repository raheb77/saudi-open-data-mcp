import { Link } from "react-router-dom";
import { ar } from "../i18n/ar";
import { formatAge, formatDateTime } from "../lib/format";
import { SOURCE_LABELS } from "../lib/catalogPresentation";
import type {
  DatasetCatalogEntry,
  DatasetPreviewResult,
  DatasetHealthLookupResult,
} from "../types/core";
import { MetadataStrip } from "./MetadataStrip";
import { DataOriginBadge, FreshnessBadge, PreviewStatusBadge } from "./StatusBadge";

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

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-ink-900">{catalog.title}</h3>
        <span className="id-mono text-[0.75rem] text-ink-500">
          {catalog.dataset_id}
        </span>
      </header>

      <p className="text-xs text-ink-500">
        {ar.home.cardLabels.source}:{" "}
        <span className="text-ink-700">
          {SOURCE_LABELS[catalog.source] ?? catalog.source}
        </span>
        <span className="id-mono ms-2 text-[0.75rem] text-ink-500">
          {catalog.source}
        </span>
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <PreviewStatusBadge status={preview.status} />
        {preview.freshness_status && (
          <FreshnessBadge status={preview.freshness_status} />
        )}
        {preview.data_origin && <DataOriginBadge origin={preview.data_origin} />}
      </div>

      {preview.snapshot_modified_at && (
        <p className="text-xs text-ink-500">
          {ar.home.cardLabels.lastUpdated}:{" "}
          <span className="num-latn">
            {formatDateTime(preview.snapshot_modified_at)}
          </span>
        </p>
      )}

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
        ]}
        status_kind="preview"
        status={preview.status}
        data_origin={preview.data_origin}
        freshness_status={preview.freshness_status}
        degradation_reason={preview.degradation_reason}
        schema_version={health?.schema_version ?? null}
        snapshot_age_label={snapshotAgeLabel}
      />

      <Link
        to={`/query?dataset=${encodeURIComponent(catalog.dataset_id)}`}
        className="self-start rounded-md border border-ink-300 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
      >
        {ar.home.cardLabels.openInQuery}
      </Link>
    </article>
  );
}
