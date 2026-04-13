import { ar } from "../i18n/ar";
import { getCoverageNarrative } from "../lib/statePresentation";
import type { DatasetCoverageStatus } from "../types/core";
import { CoverageBadge } from "./StatusBadge";

interface CoverageSignalProps {
  coverageStatus?: DatasetCoverageStatus | null;
}

export function CoverageSignal({
  coverageStatus = null,
}: CoverageSignalProps) {
  const resolvedCoverageStatus = coverageStatus ?? "unavailable";

  return (
    <section className="rounded-lg border border-ink-200 bg-ink-50 px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[0.72rem] font-semibold text-ink-700">
          {ar.datasetState.coverage}
        </p>
        <CoverageBadge status={resolvedCoverageStatus} />
      </div>
      <p className="cell-clamp-2 mt-2 text-[0.78rem] leading-5 text-ink-700">
        {getCoverageNarrative(resolvedCoverageStatus)}
      </p>
    </section>
  );
}
