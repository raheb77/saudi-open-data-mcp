import { Link } from "react-router-dom";
import { ar } from "../i18n/ar";
import { formatDateTime } from "../lib/format";
import { SOURCE_LABELS } from "../mocks/datasets";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
} from "../types/core";
import { MetadataStrip } from "./MetadataStrip";
import { FreshnessBadge, HealthStatusBadge } from "./StatusBadge";

interface DatasetCardProps {
  catalog: DatasetCatalogEntry;
  health: DatasetHealthLookupResult | undefined;
}

export function DatasetCard({ catalog, health }: DatasetCardProps) {
  const freshness = health?.freshness ?? null;
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-ink-900">{catalog.title}</h3>
        <span className="id-mono text-[0.75rem] text-ink-500">
          {catalog.dataset_id}
        </span>
      </header>

      <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <Row label={ar.home.cardLabels.source}>
          <span className="flex items-center gap-2">
            <span>{SOURCE_LABELS[catalog.source] ?? catalog.source}</span>
            <span className="id-mono text-[0.75rem] text-ink-500">
              {catalog.source}
            </span>
          </span>
        </Row>
        <Row label={ar.home.cardLabels.status}>
          <HealthStatusBadge status={catalog.health_status} />
        </Row>
        {freshness && (
          <Row label={ar.home.cardLabels.freshness}>
            <FreshnessBadge status={freshness.status} />
          </Row>
        )}
        {freshness?.snapshot_modified_at && (
          <Row label={ar.home.cardLabels.lastUpdated}>
            <span className="num-latn">
              {formatDateTime(freshness.snapshot_modified_at)}
            </span>
          </Row>
        )}
      </dl>

      <MetadataStrip
        dataset_id={catalog.dataset_id}
        source={catalog.source}
        status="success"
        data_origin={freshness?.artifact_present ? "local_snapshot" : null}
        freshness_status={freshness?.status ?? null}
        schema_version={health?.schema_version ?? null}
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
    <div className="flex items-center gap-2">
      <dt className="text-xs font-medium text-ink-500">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
