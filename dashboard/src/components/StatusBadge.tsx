import { ar } from "../i18n/ar";
import type {
  DatasetHealthStatus,
  DatasetQueryStatus,
  PreviewStatus,
  ResultDataOrigin,
  SnapshotFreshnessStatus,
} from "../types/core";
import type { DatasetCoverageStatus } from "../lib/statePresentation";

type Tone = "ok" | "warn" | "bad" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  ok: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warn: "bg-amber-50 text-amber-800 ring-amber-200",
  bad: "bg-rose-50 text-rose-700 ring-rose-200",
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
};

interface BadgeProps {
  label: string;
  tone: Tone;
  /** Optional small Latin technical token rendered next to the label. */
  technical?: string;
  testId?: string;
}

export function StatusBadge({ label, tone, technical, testId }: BadgeProps) {
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_CLASS[tone]}`}
    >
      <span>{label}</span>
      {technical && <span className="id-mono">{technical}</span>}
    </span>
  );
}

// ---------- Specific badge factories so callers don't re-derive tones. ----------

export function QueryStatusBadge({ status }: { status: DatasetQueryStatus }) {
  const map: Record<DatasetQueryStatus, { label: string; tone: Tone }> = {
    success: { label: ar.state.success, tone: "ok" },
    limited: { label: ar.state.limited, tone: "warn" },
    failed: { label: ar.state.failed, tone: "bad" },
    missing: { label: ar.state.missing, tone: "neutral" },
    snapshot_missing: { label: ar.state.snapshotMissing, tone: "neutral" },
  };
  const entry = map[status];
  return <StatusBadge label={entry.label} tone={entry.tone} technical={status} />;
}

export function PreviewStatusBadge({ status }: { status: PreviewStatus }) {
  const map: Record<PreviewStatus, { label: string; tone: Tone }> = {
    record_derivable: { label: ar.state.recordDerivable, tone: "ok" },
    limited: { label: ar.state.limited, tone: "warn" },
    failed: { label: ar.state.failed, tone: "bad" },
    missing: { label: ar.state.missing, tone: "neutral" },
  };
  const entry = map[status];
  return <StatusBadge label={entry.label} tone={entry.tone} technical={status} />;
}

export function HealthStatusBadge({
  status,
}: {
  status: DatasetHealthStatus;
}) {
  const map: Record<DatasetHealthStatus, { label: string; tone: Tone }> = {
    healthy: { label: ar.state.healthy, tone: "ok" },
    degraded: { label: ar.state.degraded, tone: "warn" },
    unavailable: { label: ar.state.unavailable, tone: "bad" },
    unknown: { label: ar.state.unknown, tone: "neutral" },
  };
  const entry = map[status];
  return <StatusBadge label={entry.label} tone={entry.tone} technical={status} />;
}

export function FreshnessBadge({
  status,
}: {
  status: SnapshotFreshnessStatus;
}) {
  const map: Record<SnapshotFreshnessStatus, { label: string; tone: Tone }> = {
    fresh: { label: ar.state.fresh, tone: "ok" },
    stale: { label: ar.state.stale, tone: "warn" },
    missing: { label: ar.state.missing, tone: "bad" },
    unknown: { label: ar.state.freshnessUnknown, tone: "neutral" },
  };
  const entry = map[status];
  return <StatusBadge label={entry.label} tone={entry.tone} technical={status} />;
}

export function DataOriginBadge({ origin }: { origin: ResultDataOrigin }) {
  const map: Record<ResultDataOrigin, { label: string; tone: Tone }> = {
    local_snapshot: { label: ar.state.localSnapshot, tone: "ok" },
    live_refresh: { label: ar.state.liveRefresh, tone: "ok" },
    stale_snapshot: { label: ar.state.staleSnapshot, tone: "warn" },
  };
  const entry = map[origin];
  return <StatusBadge label={entry.label} tone={entry.tone} technical={origin} />;
}

export function CoverageBadge({
  status,
}: {
  status: DatasetCoverageStatus;
}) {
  const map: Record<DatasetCoverageStatus, { label: string; tone: Tone }> = {
    queryable: { label: ar.state.coverageQueryable, tone: "ok" },
    limited: { label: ar.state.coverageLimited, tone: "warn" },
    catalog_only: { label: ar.state.coverageCatalogOnly, tone: "neutral" },
    unavailable: { label: ar.state.coverageUnavailable, tone: "neutral" },
  };
  const entry = map[status];
  return <StatusBadge label={entry.label} tone={entry.tone} technical={status} />;
}
