import { ar } from "../i18n/ar";
import { SOURCE_LABELS } from "../lib/catalogPresentation";
import type {
  DatasetHealthStatus,
  PreviewStatus,
  DatasetQueryStatus,
  ResultDataOrigin,
  ResultDegradationReason,
  SnapshotFreshnessStatus,
  SourceName,
} from "../types/core";
import {
  DataOriginBadge,
  FreshnessBadge,
  HealthStatusBadge,
  PreviewStatusBadge,
  QueryStatusBadge,
} from "./StatusBadge";

// Shared metadata component.
//
// Per the Phase 5 metadata-honesty rule, every result-oriented view in
// the dashboard must render this strip. It echoes — without inventing —
// what the core itself returns: source, data_origin, freshness, status,
// degradation_reason, dataset_id, schema_version, snapshot_age.
//
// Fields that are not present in the underlying result are simply not
// rendered. Embedded cards may hide rows that are already surfaced by
// their parent card; when no additional metadata remains, the strip
// collapses instead of rendering an empty block.

type BaseMetadataStripProps = {
  dataset_id: string;
  source: SourceName | null;
  data_origin: ResultDataOrigin | null;
  freshness_status?: SnapshotFreshnessStatus | null;
  degradation_reason?: ResultDegradationReason | null;
  schema_version?: string | null;
  snapshot_age_label?: string | null;
  variant?: "default" | "flat";
  hiddenFields?: readonly MetadataField[];
  showTitle?: boolean;
};

type QueryMetadataStripProps = BaseMetadataStripProps & {
  status_kind: "query";
  status: DatasetQueryStatus;
};

type PreviewMetadataStripProps = BaseMetadataStripProps & {
  status_kind: "preview";
  status: PreviewStatus;
};

type HealthMetadataStripProps = BaseMetadataStripProps & {
  status_kind: "health";
  status: DatasetHealthStatus;
};

export type MetadataStripProps =
  | QueryMetadataStripProps
  | PreviewMetadataStripProps
  | HealthMetadataStripProps;

type MetadataField =
  | "dataset_id"
  | "source"
  | "status"
  | "data_origin"
  | "freshness"
  | "degradation"
  | "schema_version"
  | "snapshot_age";

const DEGRADATION_LABEL: Record<ResultDegradationReason, string> = {
  normalization_limited: ar.state.normalizationLimited,
  stale_fallback_after_refresh_failure: ar.state.staleFallback,
};

export function MetadataStrip(props: MetadataStripProps) {
  const isFlat = props.variant === "flat";
  const hiddenFields = new Set(props.hiddenFields ?? []);
  const showTitle = props.showTitle ?? true;
  const showDatasetId = !hiddenFields.has("dataset_id");
  const showSource = !hiddenFields.has("source");
  const showStatus = !hiddenFields.has("status");
  const showDataOrigin = !hiddenFields.has("data_origin");
  const showFreshness =
    !hiddenFields.has("freshness") && Boolean(props.freshness_status);
  const showDegradation =
    !hiddenFields.has("degradation") && Boolean(props.degradation_reason);
  const showSchemaVersion =
    !hiddenFields.has("schema_version") && Boolean(props.schema_version);
  const showSnapshotAge =
    !hiddenFields.has("snapshot_age") && Boolean(props.snapshot_age_label);

  if (
    !showDatasetId &&
    !showSource &&
    !showStatus &&
    !showDataOrigin &&
    !showFreshness &&
    !showDegradation &&
    !showSchemaVersion &&
    !showSnapshotAge
  ) {
    return null;
  }

  const gridClass = isFlat
    ? `${showTitle ? "mt-1 " : ""}grid grid-cols-1 gap-x-6 gap-y-3 text-sm`
    : `${showTitle ? "mt-2 " : ""}grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3`;
  return (
    <div
      data-testid="metadata-strip"
      className={
        isFlat
          ? "rounded-md border-0 bg-transparent px-0 py-0 shadow-none"
          : "rounded-lg border border-ink-300 bg-white px-4 py-3 shadow-sm"
      }
    >
      {showTitle && (
        <h3 className="text-xs font-semibold text-ink-500">{ar.meta.title}</h3>
      )}
      <dl className={gridClass}>
        {showDatasetId && (
          <Row label={ar.meta.datasetId}>
            <span className="id-mono">{props.dataset_id}</span>
          </Row>
        )}

        {showSource && (
          <Row label={ar.meta.source}>
            {props.source ? (
              <span className="flex flex-wrap items-center gap-2">
                <span>{SOURCE_LABELS[props.source] ?? props.source}</span>
                <span className="id-mono">{props.source}</span>
              </span>
            ) : (
              <span className="text-ink-500">—</span>
            )}
          </Row>
        )}

        {showStatus && (
          <Row label={ar.meta.status}>
            <StatusCell props={props} />
          </Row>
        )}

        {showDataOrigin && (
          <Row label={ar.meta.dataOrigin}>
            {props.data_origin ? (
              <DataOriginBadge origin={props.data_origin} />
            ) : (
              <span className="text-ink-500">—</span>
            )}
          </Row>
        )}

        {showFreshness && (
          <Row label={ar.meta.freshness}>
            <FreshnessBadge status={props.freshness_status!} />
          </Row>
        )}

        {showDegradation && (
          <Row label={ar.meta.degradation}>
            <span className="text-amber-800">
              {DEGRADATION_LABEL[props.degradation_reason!]}
            </span>
            <span className="id-mono">{props.degradation_reason!}</span>
          </Row>
        )}

        {showSchemaVersion && (
          <Row label={ar.meta.schemaVersion}>
            <span className="num-latn">{props.schema_version}</span>
          </Row>
        )}

        {showSnapshotAge && (
          <Row label={ar.meta.snapshotAge}>
            <span className="num-latn">{props.snapshot_age_label}</span>
          </Row>
        )}
      </dl>
    </div>
  );
}

function StatusCell({ props }: { props: MetadataStripProps }) {
  switch (props.status_kind) {
    case "preview":
      return <PreviewStatusBadge status={props.status} />;
    case "health":
      return <HealthStatusBadge status={props.status} />;
    case "query":
    default:
      return <QueryStatusBadge status={props.status} />;
  }
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
      <dd className="flex min-w-0 flex-wrap items-center gap-2 text-ink-900">
        {children}
      </dd>
    </div>
  );
}
