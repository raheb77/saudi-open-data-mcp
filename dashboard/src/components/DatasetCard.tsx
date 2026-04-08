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
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-ink-900">{catalog.title}</h3>
        <span className="id-mono text-[0.75rem] text-ink-500">
          {catalog.dataset_id}
        </span>
      </header>

      <dl className="grid grid-cols-1 gap-3 text-sm">
        <Row label={ar.home.cardLabels.source}>
          <span className="flex flex-wrap items-center gap-2">
            <span>{SOURCE_LABELS[catalog.source] ?? catalog.source}</span>
            <span className="id-mono text-[0.75rem] text-ink-500">
              {catalog.source}
            </span>
          </span>
        </Row>
        <Row label={ar.home.cardLabels.status}>
          <PreviewStatusBadge status={preview.status} />
        </Row>
        {preview.data_origin && (
          <Row label={ar.home.cardLabels.origin}>
            <DataOriginBadge origin={preview.data_origin} />
          </Row>
        )}
        {preview.freshness_status && (
          <Row label={ar.home.cardLabels.freshness}>
            <FreshnessBadge status={preview.freshness_status} />
          </Row>
        )}
        {preview.snapshot_modified_at && (
          <Row label={ar.home.cardLabels.lastUpdated}>
            <span className="num-latn">
              {formatDateTime(preview.snapshot_modified_at)}
            </span>
          </Row>
        )}
      </dl>

      <MetadataStrip
        dataset_id={catalog.dataset_id}
        source={catalog.source}
        variant="flat"
        status_kind="preview"
        status={preview.status}
        data_origin={preview.data_origin}
        freshness_status={preview.freshness_status}
        degradation_reason={preview.degradation_reason}
        schema_version={health?.schema_version ?? null}
        snapshot_age_label={
          health?.freshness?.snapshot_age_seconds != null
            ? formatAge(health.freshness.snapshot_age_seconds)
            : null
        }
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

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="text-xs font-medium text-ink-500">{label}</dt>
      <dd className="min-w-0 text-ink-900">{children}</dd>
    </div>
  );
}
