import { ar } from "../i18n/ar";
import type { DatasetCoverageStatus } from "../types/core";
import { FEATURED_DATASET_IDS } from "./catalogPresentation";

export interface DatasetSurfaceSection<T> {
  coverageStatus: DatasetCoverageStatus;
  title: string;
  body: string;
  entries: T[];
}

const COVERAGE_ORDER: DatasetCoverageStatus[] = [
  "queryable",
  "limited",
  "catalog_only",
  "unavailable",
];

const FEATURED_ORDER = new Map<string, number>(
  FEATURED_DATASET_IDS.map((datasetId, index) => [datasetId, index]),
);

export function groupDatasetSurfaceEntries<T>(
  entries: readonly T[],
  options: {
    getCoverageStatus: (entry: T) => DatasetCoverageStatus;
    getDatasetId: (entry: T) => string;
    getTitle: (entry: T) => string;
  },
): DatasetSurfaceSection<T>[] {
  const grouped = new Map<DatasetCoverageStatus, T[]>();

  for (const coverageStatus of COVERAGE_ORDER) {
    grouped.set(coverageStatus, []);
  }

  for (const entry of entries) {
    grouped.get(options.getCoverageStatus(entry))?.push(entry);
  }

  return COVERAGE_ORDER.flatMap((coverageStatus) => {
    const sectionEntries = grouped.get(coverageStatus) ?? [];
    if (sectionEntries.length === 0) {
      return [];
    }

    const sortedEntries = [...sectionEntries].sort((left, right) =>
      compareDatasetSurfaceEntries(left, right, options),
    );
    return [
      {
        coverageStatus,
        title: getDatasetSurfaceSectionCopy(coverageStatus).title,
        body: getDatasetSurfaceSectionCopy(coverageStatus).body,
        entries: sortedEntries,
      } satisfies DatasetSurfaceSection<T>,
    ];
  });
}

export function getDatasetSurfaceSectionCopy(status: DatasetCoverageStatus): {
  title: string;
  body: string;
} {
  switch (status) {
    case "queryable":
      return ar.datasetSurface.sections.queryable;
    case "limited":
      return ar.datasetSurface.sections.limited;
    case "catalog_only":
      return ar.datasetSurface.sections.catalogOnly;
    case "unavailable":
    default:
      return ar.datasetSurface.sections.unavailable;
  }
}

function compareDatasetSurfaceEntries<T>(
  left: T,
  right: T,
  options: {
    getDatasetId: (entry: T) => string;
    getTitle: (entry: T) => string;
  },
): number {
  const leftId = options.getDatasetId(left);
  const rightId = options.getDatasetId(right);
  const leftFeaturedRank = FEATURED_ORDER.get(leftId) ?? Number.POSITIVE_INFINITY;
  const rightFeaturedRank =
    FEATURED_ORDER.get(rightId) ?? Number.POSITIVE_INFINITY;

  if (leftFeaturedRank !== rightFeaturedRank) {
    return leftFeaturedRank - rightFeaturedRank;
  }

  return (
    options.getTitle(left).localeCompare(options.getTitle(right), "ar") ||
    leftId.localeCompare(rightId)
  );
}
