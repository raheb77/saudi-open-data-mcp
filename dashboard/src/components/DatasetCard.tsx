import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { ar } from "../i18n/ar";
import { formatAge } from "../lib/format";
import { SOURCE_LABELS } from "../lib/catalogPresentation";
import type {
  DatasetCatalogEntry,
  DatasetPreviewResult,
  DatasetHealthLookupResult,
} from "../types/core";
import { CoverageBadge, FreshnessBadge } from "./StatusBadge";
import { CoverageSignal } from "./CoverageSignal";
import { DatasetStateOverview } from "./DatasetStateOverview";
import { MetadataStrip } from "./MetadataStrip";
import { SnapshotContextBlock } from "./SnapshotContextBlock";

interface DatasetCardProps {
  catalog: DatasetCatalogEntry;
  preview: DatasetPreviewResult;
  health: DatasetHealthLookupResult | undefined;
}

export function DatasetCard({ catalog, preview, health }: DatasetCardProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [techOpen, setTechOpen] = useState(false);
  const detailsPanelId = useId();
  const techPanelId = useId();

  const snapshotAgeLabel =
    health?.freshness?.snapshot_age_seconds != null
      ? formatAge(health.freshness.snapshot_age_seconds)
      : null;
  const snapshotTimestamp =
    preview.snapshot_modified_at ?? health?.freshness?.snapshot_modified_at ?? null;
  const hasTechnicalMetadata = Boolean(
    preview.degradation_reason || health?.schema_version,
  );

  return (
    <article className="flex h-full flex-col rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      {/* ── P0: Always visible ── */}
      <header className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-ink-900">{catalog.title}</h3>
        <span className="id-mono text-[0.75rem] text-ink-500">
          {catalog.dataset_id}
        </span>
      </header>

      {/* Badges row */}
      <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2">
        <span className="id-mono rounded bg-ink-100 px-1.5 py-0.5 text-[0.72rem] text-ink-500">
          {SOURCE_LABELS[catalog.source] ?? catalog.source}
        </span>
        <CoverageBadge status={preview.coverage_status} />
        {preview.freshness_status && (
          <FreshnessBadge status={preview.freshness_status} />
        )}
      </div>

      {/* ── P1 Accordion trigger ── */}
      <button
        type="button"
        aria-expanded={detailsOpen}
        aria-controls={detailsPanelId}
        onClick={() => setDetailsOpen((v) => !v)}
        className="mt-3 flex min-h-[44px] w-full items-center justify-between gap-2 rounded-lg border border-ink-200 bg-ink-50/70 px-3 py-2 text-start text-xs font-medium text-ink-700 hover:bg-ink-100"
      >
        <span>
          {detailsOpen
            ? ar.cards.hideCardDetails
            : ar.cards.showCardDetails}
        </span>
        <svg
          className="accordion-chevron h-4 w-4 shrink-0 text-ink-500"
          data-open={detailsOpen}
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* ── P1 Expandable panel ── */}
      <div
        id={detailsPanelId}
        role="region"
        aria-label={ar.cards.showCardDetails}
        className="accordion-grid"
        data-open={detailsOpen}
      >
        <div className="accordion-inner">
          <div className="flex flex-col gap-4 pt-3">
            <CoverageSignal coverageStatus={preview.coverage_status} />

            <DatasetStateOverview
              previewStatus={preview.status}
              previewLimitations={preview.limitations}
              freshnessStatus={preview.freshness_status}
              dataOrigin={preview.data_origin}
              healthStatus={health?.health_status ?? null}
            />

            <SnapshotContextBlock
              timestamp={snapshotTimestamp}
              ageLabel={snapshotAgeLabel}
            />

            {/* ── P2 nested technical accordion ── */}
            {hasTechnicalMetadata && (
              <>
                <button
                  type="button"
                  aria-expanded={techOpen}
                  aria-controls={techPanelId}
                  onClick={() => setTechOpen((v) => !v)}
                  className="flex min-h-[44px] w-full items-center justify-between gap-2 rounded-lg border border-ink-200 bg-ink-50/70 px-3 py-2 text-start text-[0.72rem] font-medium text-ink-600 hover:bg-ink-100"
                >
                  <span>{ar.cards.extraTechnicalInfo}</span>
                  <svg
                    className="accordion-chevron h-3.5 w-3.5 shrink-0 text-ink-400"
                    data-open={techOpen}
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      fillRule="evenodd"
                      d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>

                <div
                  id={techPanelId}
                  role="region"
                  aria-label={ar.cards.extraTechnicalInfo}
                  className="accordion-grid"
                  data-open={techOpen}
                >
                  <div className="accordion-inner">
                    <div className="border-t border-ink-200 pt-3">
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
                          "snapshot_age",
                        ]}
                        status_kind="preview"
                        status={preview.status}
                        data_origin={preview.data_origin}
                        freshness_status={preview.freshness_status}
                        degradation_reason={preview.degradation_reason}
                        schema_version={health?.schema_version ?? null}
                        snapshot_age_label={snapshotAgeLabel}
                      />
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── CTA: always visible, pinned to bottom ── */}
      <Link
        to={`/query?dataset=${encodeURIComponent(catalog.dataset_id)}`}
        className="mt-auto self-start rounded-md border border-ink-300 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
        style={{ marginTop: "auto", paddingTop: detailsOpen ? undefined : "12px" }}
      >
        {ar.home.cardLabels.openInQuery}
      </Link>
    </article>
  );
}
