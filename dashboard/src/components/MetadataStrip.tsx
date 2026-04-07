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

// MANDATORY shared metadata component.
//
// Per the Phase 5 metadata-honesty rule, every result-oriented view in
// the dashboard must render this strip. It echoes — without inventing —
// what the core itself returns: source, data_origin, freshness, status,
// degradation_reason, dataset_id, schema_version, snapshot_age.
//
// Fields that are not present in the underlying result are simply not
// rendered. The component never fabricates a freshness or origin.

type BaseMetadataStripProps = {
  dataset_id: string;
  source: SourceName | null;
  data_origin: ResultDataOrigin | null;
  freshness_status?: SnapshotFreshnessStatus | null;
  degradation_reason?: ResultDegradationReason | null;
  schema_version?: string | null;
  snapshot_age_label?: string | null;
  variant?: "default" | "flat";
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

const DEGRADATION_LABEL: Record<ResultDegradationReason, string> = {
  normalization_limited: ar.state.normalizationLimited,
  stale_fallback_after_refresh_failure: ar.state.staleFallback,
};

export function MetadataStrip(props: MetadataStripProps) {
  const isFlat = props.variant === "flat";
  return (
    <div
      data-testid="metadata-strip"
      className={
        isFlat
          ? "rounded-md border-0 bg-transparent px-0 py-0 shadow-none"
          : "rounded-lg border border-ink-300 bg-white px-4 py-3 shadow-sm"
      }
    >
      <h3 className="text-xs font-semibold text-ink-500">{ar.meta.title}</h3>
      <dl
        className={`grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3 ${
          isFlat ? "mt-1" : "mt-2"
        }`}
      >
        <Row label={ar.meta.datasetId}>
          <span className="id-mono">{props.dataset_id}</span>
        </Row>

        <Row label={ar.meta.source}>
          {props.source ? (
            <span className="flex items-center gap-2">
              <span>{SOURCE_LABELS[props.source] ?? props.source}</span>
              <span className="id-mono">{props.source}</span>
            </span>
          ) : (
            <span className="text-ink-500">—</span>
          )}
        </Row>

        <Row label={ar.meta.status}>
          <StatusCell props={props} />
        </Row>

        <Row label={ar.meta.dataOrigin}>
          {props.data_origin ? (
            <DataOriginBadge origin={props.data_origin} />
          ) : (
            <span className="text-ink-500">—</span>
          )}
        </Row>

        {props.freshness_status && (
          <Row label={ar.meta.freshness}>
            <FreshnessBadge status={props.freshness_status} />
          </Row>
        )}

        {props.degradation_reason && (
          <Row label={ar.meta.degradation}>
            <span className="text-amber-800">
              {DEGRADATION_LABEL[props.degradation_reason]}
            </span>
            <span className="id-mono ms-2">{props.degradation_reason}</span>
          </Row>
        )}

        {props.schema_version && (
          <Row label={ar.meta.schemaVersion}>
            <span className="num-latn">{props.schema_version}</span>
          </Row>
        )}

        {props.snapshot_age_label && (
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
    <div className="flex items-center gap-3">
      <dt className="text-xs font-medium text-ink-500">{label}</dt>
      <dd className="text-ink-900">{children}</dd>
    </div>
  );
}
