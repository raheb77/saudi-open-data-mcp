import { ar } from "../i18n/ar";
import type {
  DatasetCoverageStatus,
  DatasetHealthStatus,
  PreviewStatus,
  ResultDataOrigin,
  SnapshotFreshnessStatus,
} from "../types/core";

export function getPreviewStatusNarrative(status: PreviewStatus): string {
  switch (status) {
    case "record_derivable":
      return ar.datasetState.previewNarratives.recordDerivable;
    case "limited":
      return ar.datasetState.previewNarratives.limited;
    case "failed":
      return ar.datasetState.previewNarratives.failed;
    case "missing":
    default:
      return ar.datasetState.previewNarratives.missing;
  }
}

export function getHealthStatusNarrative(status: DatasetHealthStatus): string {
  switch (status) {
    case "healthy":
      return ar.datasetState.healthNarratives.healthy;
    case "degraded":
      return ar.datasetState.healthNarratives.degraded;
    case "unavailable":
      return ar.datasetState.healthNarratives.unavailable;
    case "unknown":
    default:
      return ar.datasetState.healthNarratives.unknown;
  }
}

export function getFreshnessNarrative(
  status: SnapshotFreshnessStatus,
): string {
  switch (status) {
    case "fresh":
      return ar.datasetState.freshnessNarratives.fresh;
    case "stale":
      return ar.datasetState.freshnessNarratives.stale;
    case "missing":
      return ar.datasetState.freshnessNarratives.missing;
    case "unknown":
    default:
      return ar.datasetState.freshnessNarratives.unknown;
  }
}

export function getDataOriginNarrative(origin: ResultDataOrigin): string {
  switch (origin) {
    case "local_snapshot":
      return ar.datasetState.originNarratives.localSnapshot;
    case "live_refresh":
      return ar.datasetState.originNarratives.liveRefresh;
    case "stale_snapshot":
    default:
      return ar.datasetState.originNarratives.staleSnapshot;
  }
}

export function getCoverageNarrative(status: DatasetCoverageStatus): string {
  switch (status) {
    case "queryable":
      return ar.datasetState.coverageNarratives.queryable;
    case "limited":
      return ar.datasetState.coverageNarratives.limited;
    case "catalog_only":
      return ar.datasetState.coverageNarratives.catalogOnly;
    case "unavailable":
    default:
      return ar.datasetState.coverageNarratives.unavailable;
  }
}

export function getLimitedPracticalMeaning(limitations: string[]): string {
  const normalized = limitations.join(" ").toLowerCase();

  if (
    normalized.includes("sama_exchange_rates_current_html") ||
    normalized.includes("exchange_rates_current_html")
  ) {
    return ar.limited.practicalMeanings.exchangeRatesLegacyHtml;
  }

  if (
    normalized.includes("html") ||
    normalized.includes("release_card") ||
    normalized.includes("release_cards")
  ) {
    return ar.limited.practicalMeanings.htmlStructure;
  }

  if (normalized.includes("pdf")) {
    return ar.limited.practicalMeanings.pdfExtraction;
  }

  if (
    normalized.includes("normalization") ||
    normalized.includes("requires_source_specific_extraction")
  ) {
    return ar.limited.practicalMeanings.normalization;
  }

  return ar.limited.practicalMeanings.generic;
}
