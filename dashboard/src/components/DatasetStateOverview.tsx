import { ar } from "../i18n/ar";
import {
  getDataOriginNarrative,
  getFreshnessNarrative,
  getHealthStatusNarrative,
  getPreviewStatusNarrative,
} from "../lib/statePresentation";
import type {
  DatasetHealthStatus,
  PreviewStatus,
  ResultDataOrigin,
  SnapshotFreshnessStatus,
} from "../types/core";
import {
  DataOriginBadge,
  FreshnessBadge,
  HealthStatusBadge,
  PreviewStatusBadge,
  StatusBadge,
} from "./StatusBadge";

interface DatasetStateOverviewProps {
  previewStatus?: PreviewStatus | null;
  previewLimitations?: string[];
  previewErrorMessage?: string | null;
  healthStatus?: DatasetHealthStatus | null;
  freshnessStatus?: SnapshotFreshnessStatus | null;
  dataOrigin?: ResultDataOrigin | null;
}

export function DatasetStateOverview({
  previewStatus = null,
  previewLimitations = [],
  previewErrorMessage = null,
  healthStatus = null,
  freshnessStatus = null,
  dataOrigin = null,
}: DatasetStateOverviewProps) {
  const cards: React.ReactNode[] = [];

  if (previewStatus || previewErrorMessage) {
    cards.push(
      <StateFacetCard
        key="queryability"
        label={ar.datasetState.queryability}
        description={
          previewErrorMessage ??
          getPreviewStatusNarrative(previewStatus ?? "missing")
        }
        tone={getPreviewTone(previewStatus, previewErrorMessage)}
      >
        {previewStatus ? (
          <PreviewStatusBadge status={previewStatus} />
        ) : (
          <StatusBadge
            label={ar.datasetState.previewUnavailable}
            tone="neutral"
            technical="preview_unavailable"
          />
        )}
        {previewStatus === "limited" &&
          previewLimitations.map((entry) => (
            <span
              key={entry}
              className="id-mono block break-all text-[0.72rem] leading-5 text-amber-900"
              dir="ltr"
            >
              {entry}
            </span>
          ))}
      </StateFacetCard>,
    );
  }

  if (freshnessStatus || dataOrigin) {
    cards.push(
      <StateFacetCard
        key="snapshot"
        label={ar.datasetState.snapshotState}
        description={
          freshnessStatus
            ? getFreshnessNarrative(freshnessStatus)
            : ar.datasetState.freshnessNarratives.unknown
        }
        tone={getSnapshotTone(freshnessStatus)}
      >
        {freshnessStatus && <FreshnessBadge status={freshnessStatus} />}
        {dataOrigin && <DataOriginBadge origin={dataOrigin} />}
        {dataOrigin && (
          <p className="mt-1 text-[0.72rem] leading-5 text-ink-500">
            {getDataOriginNarrative(dataOrigin)}
          </p>
        )}
      </StateFacetCard>,
    );
  }

  if (healthStatus) {
    cards.push(
      <StateFacetCard
        key="health"
        label={ar.datasetState.sourceHealth}
        description={getHealthStatusNarrative(healthStatus)}
        tone={getHealthTone(healthStatus)}
      >
        <HealthStatusBadge status={healthStatus} />
      </StateFacetCard>,
    );
  }

  if (cards.length === 0) {
    return null;
  }

  return (
    <section
      className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3"
      data-testid="dataset-state-overview"
    >
      {cards}
    </section>
  );
}

function StateFacetCard({
  label,
  description,
  tone,
  children,
}: {
  label: string;
  description: string;
  tone: "ok" | "warn" | "bad" | "neutral";
  children: React.ReactNode;
}) {
  return (
    <section
      className={[
        "rounded-lg border px-3 py-3 shadow-sm",
        tone === "ok"
          ? "border-emerald-200 bg-emerald-50/60"
          : tone === "warn"
            ? "border-amber-200 bg-amber-50/70"
            : tone === "bad"
              ? "border-rose-200 bg-rose-50/70"
              : "border-ink-200 bg-ink-50",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <p className="text-[0.72rem] font-semibold text-ink-700">{label}</p>
      <div className="mt-2 flex min-w-0 flex-col gap-2">{children}</div>
      <p className="mt-2 text-xs leading-relaxed text-ink-700">{description}</p>
    </section>
  );
}

function getPreviewTone(
  status: PreviewStatus | null,
  errorMessage: string | null,
): "ok" | "warn" | "bad" | "neutral" {
  if (errorMessage) {
    return "neutral";
  }

  switch (status) {
    case "record_derivable":
      return "ok";
    case "limited":
      return "warn";
    case "failed":
      return "bad";
    case "missing":
    default:
      return "neutral";
  }
}

function getSnapshotTone(
  status: SnapshotFreshnessStatus | null,
): "ok" | "warn" | "bad" | "neutral" {
  switch (status) {
    case "fresh":
      return "ok";
    case "stale":
      return "warn";
    case "missing":
      return "bad";
    case "unknown":
    default:
      return "neutral";
  }
}

function getHealthTone(
  status: DatasetHealthStatus,
): "ok" | "warn" | "bad" | "neutral" {
  switch (status) {
    case "healthy":
      return "ok";
    case "degraded":
      return "warn";
    case "unavailable":
      return "bad";
    case "unknown":
    default:
      return "neutral";
  }
}
