import { ar } from "../i18n/ar";
import { formatDateTime } from "../lib/format";

interface SnapshotContextBlockProps {
  timestamp?: string | null;
  ageLabel?: string | null;
}

export function SnapshotContextBlock({
  timestamp = null,
  ageLabel = null,
}: SnapshotContextBlockProps) {
  if (!timestamp && !ageLabel) {
    return null;
  }

  return (
    <section className="rounded-lg border border-ink-200 bg-ink-50/80 px-3 py-2.5">
      <p className="text-[0.72rem] font-semibold text-ink-600">
        {ar.cards.snapshotTimestamp}
      </p>
      {timestamp ? (
        <p className="mt-1 text-sm font-semibold text-ink-900">
          <span className="num-latn">{formatDateTime(timestamp)}</span>
        </p>
      ) : (
        <p className="mt-1 text-xs text-ink-500">—</p>
      )}
      {ageLabel && (
        <p className="mt-1 text-[0.72rem] text-ink-500">
          {ar.cards.snapshotAgePrefix}{" "}
          <span className="num-latn">{ageLabel}</span>
        </p>
      )}
    </section>
  );
}
