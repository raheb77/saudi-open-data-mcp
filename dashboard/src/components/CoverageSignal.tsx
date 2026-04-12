import { ar } from "../i18n/ar";
import {
  getCoverageNarrative,
  getDatasetCoverageStatus,
} from "../lib/statePresentation";
import type { PreviewStatus } from "../types/core";
import { CoverageBadge } from "./StatusBadge";

interface CoverageSignalProps {
  previewStatus?: PreviewStatus | null;
  previewLimitations?: string[];
  previewErrorMessage?: string | null;
}

export function CoverageSignal({
  previewStatus = null,
  previewLimitations = [],
  previewErrorMessage = null,
}: CoverageSignalProps) {
  const coverageStatus = getDatasetCoverageStatus({
    previewStatus,
    previewLimitations,
    previewErrorMessage,
  });

  return (
    <section className="rounded-lg border border-ink-200 bg-ink-50 px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[0.72rem] font-semibold text-ink-700">
          {ar.datasetState.coverage}
        </p>
        <CoverageBadge status={coverageStatus} />
      </div>
      <p className="cell-clamp-2 mt-2 text-[0.78rem] leading-5 text-ink-700">
        {getCoverageNarrative(coverageStatus)}
      </p>
    </section>
  );
}
