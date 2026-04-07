import { localizeCatalogEntry } from "./catalogPresentation";
import { asDashboardApiError, dashboardMcpClient } from "./mcpClient";
import {
  parseDatasetCatalogSummary,
  parseDatasetHealthLookupResult,
  parseDatasetPreviewResult,
  parseDatasetQueryResult,
  parseObservabilitySummary,
  parseReadinessReport,
} from "./runtimeValidation";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  DatasetPreviewResult,
  DatasetQueryResult,
  ObservabilitySummary,
  QueryFilterValue,
  ReadinessReport,
  SourceName,
} from "../types/core";

export async function listDatasets(
  signal?: AbortSignal,
): Promise<DatasetCatalogEntry[]> {
  const payload = await dashboardMcpClient.readJsonResource(
    "resource://catalog",
    signal,
  );
  try {
    const summary = parseDatasetCatalogSummary(payload);
    return summary.datasets.map(localizeCatalogEntry);
  } catch (error) {
    throw asDashboardApiError(
      error,
      "catalog_validation",
      "تعذّر التحقق من بيانات الفهرس الحية.",
    );
  }
}

export async function getDatasetQueryResult(
  datasetId: string,
  filters: Record<string, QueryFilterValue>,
  limit: number | null,
  signal?: AbortSignal,
): Promise<DatasetQueryResult> {
  const payload = await dashboardMcpClient.callTool(
    "query_dataset",
    {
      dataset_id: datasetId,
      filters,
      limit,
    },
    signal,
  );
  try {
    return parseDatasetQueryResult(payload);
  } catch (error) {
    throw asDashboardApiError(
      error,
      "query_validation",
      "تعذّر التحقق من نتيجة الاستعلام الحية.",
    );
  }
}

export async function getDatasetPreviewResult(
  datasetId: string,
  signal?: AbortSignal,
): Promise<DatasetPreviewResult> {
  const payload = await dashboardMcpClient.callTool(
    "preview_dataset",
    { dataset_id: datasetId },
    signal,
  );
  try {
    return parseDatasetPreviewResult(payload);
  } catch (error) {
    throw asDashboardApiError(
      error,
      "preview_validation",
      "تعذّر التحقق من نتيجة المعاينة الحية.",
    );
  }
}

export async function getDatasetHealthResult(
  datasetId: string,
  sourceFallback: SourceName | null,
  signal?: AbortSignal,
): Promise<DatasetHealthLookupResult> {
  const payload = await dashboardMcpClient.callTool(
    "dataset_health",
    { dataset_id: datasetId },
    signal,
  );
  try {
    return parseDatasetHealthLookupResult(payload, { sourceFallback });
  } catch (error) {
    throw asDashboardApiError(
      error,
      "health_validation",
      "تعذّر التحقق من حمولة الصحة الحية.",
    );
  }
}

export async function getReadiness(signal?: AbortSignal): Promise<ReadinessReport> {
  const payload = await dashboardMcpClient.getReadiness(signal);
  try {
    return parseReadinessReport(payload);
  } catch (error) {
    throw asDashboardApiError(
      error,
      "readiness_validation",
      "تعذّر التحقق من حمولة الجاهزية الحية.",
    );
  }
}

export async function getObservability(
  signal?: AbortSignal,
): Promise<ObservabilitySummary> {
  const payload = await dashboardMcpClient.readJsonResource(
    "resource://observability",
    signal,
  );
  try {
    return parseObservabilitySummary(payload);
  } catch (error) {
    throw asDashboardApiError(
      error,
      "observability_validation",
      "تعذّر التحقق من حمولة المراقبة الحية.",
    );
  }
}
