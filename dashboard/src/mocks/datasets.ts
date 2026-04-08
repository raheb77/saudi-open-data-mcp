// Mock catalog: a small representative subset of the real registry.
// Dataset IDs and field names match the actual core registry exactly,
// so the dashboard renders identifiers honestly without inventing names.

import type { DatasetCatalogEntry } from "../types/core";

export const MOCK_DATASETS: DatasetCatalogEntry[] = [
  {
    dataset_id: "sama-pos-weekly",
    source: "sama",
    title: "نقاط البيع الأسبوعية (SAMA)",
    update_frequency: "weekly",
    health_status: "healthy",
  },
  {
    dataset_id: "sama-exchange-rates-current",
    source: "sama",
    title: "أسعار الصرف الحالية (SAMA)",
    update_frequency: "daily",
    health_status: "healthy",
  },
  {
    dataset_id: "sama-repo-rate",
    source: "sama",
    title: "سعر إعادة الشراء الرسمي (SAMA)",
    update_frequency: "ad_hoc",
    health_status: "healthy",
  },
  {
    dataset_id: "stats-gov-sa-cpi-headline-monthly",
    source: "stats-gov-sa",
    title: "مؤشر أسعار المستهلك الشهري (الهيئة العامة للإحصاء)",
    update_frequency: "monthly",
    health_status: "degraded",
  },
  {
    dataset_id: "stats-gov-sa-real-gdp-growth-quarterly",
    source: "stats-gov-sa",
    title: "نمو الناتج المحلي الحقيقي الفصلي (الهيئة العامة للإحصاء)",
    update_frequency: "quarterly",
    health_status: "healthy",
  },
  {
    dataset_id: "mof-budget-balance-quarterly",
    source: "mof",
    title: "الرصيد المالي الفصلي (وزارة المالية)",
    update_frequency: "quarterly",
    health_status: "healthy",
  },
];

export const SOURCE_LABELS: Record<string, string> = {
  sama: "البنك المركزي السعودي",
  "stats-gov-sa": "الهيئة العامة للإحصاء",
  mof: "وزارة المالية",
  "data-gov-sa": "البوابة السعودية للبيانات المفتوحة",
};

export function findDatasetById(
  dataset_id: string,
): DatasetCatalogEntry | undefined {
  return MOCK_DATASETS.find((dataset) => dataset.dataset_id === dataset_id);
}
