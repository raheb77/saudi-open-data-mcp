import type { DatasetCatalogEntry } from "../types/core";

export const SOURCE_LABELS: Record<string, string> = {
  sama: "البنك المركزي السعودي",
  "stats-gov-sa": "الهيئة العامة للإحصاء",
  mof: "وزارة المالية",
  "data-gov-sa": "البوابة السعودية للبيانات المفتوحة",
};

export const FEATURED_DATASET_IDS = [
  "sama-pos-weekly",
  "sama-exchange-rates-current",
  "sama-repo-rate",
  "stats-gov-sa-cpi-headline-monthly",
  "stats-gov-sa-real-gdp-growth-quarterly",
  "mof-budget-balance-quarterly",
] as const;

const DATASET_TITLE_AR: Record<string, string> = {
  "sama-balance-of-payments": "ميزان المدفوعات",
  "mof-budget-balance-quarterly": "الرصيد المالي الفصلي",
  "data-gov-sa-census-marital-status": "الحالة الاجتماعية في التعداد",
  "stats-gov-sa-cpi-headline-monthly":
    "التضخم العام لمؤشر أسعار المستهلك شهريًا",
  "sama-exchange-rates-current": "أسعار الصرف الحالية",
  "sama-deposits-core": "السلاسل الأساسية للودائع",
  "stats-gov-sa-real-gdp-growth-quarterly":
    "نمو الناتج المحلي الحقيقي فصليًا",
  "sama-interest-rates": "أسعار الفائدة",
  "sama-money-supply": "عرض النقود",
  "sama-money-supply-weekly": "عرض النقود الأسبوعي",
  "sama-repo-rate": "سعر إعادة الشراء الرسمي",
  "sama-pos-by-city": "نقاط البيع حسب المدينة",
  "sama-pos-weekly": "نقاط البيع الأسبوعية",
  "sama-reverse-repo-rate": "سعر إعادة الشراء العكسي",
  "stats-gov-sa-unemployment-rate-total-quarterly":
    "معدل البطالة لإجمالي السكان فصليًا",
};

export function localizeDatasetTitle(
  datasetId: string,
  fallbackTitle: string,
): string {
  return DATASET_TITLE_AR[datasetId] ?? fallbackTitle;
}

export function localizeCatalogEntry(
  entry: DatasetCatalogEntry,
): DatasetCatalogEntry {
  return {
    ...entry,
    title: localizeDatasetTitle(entry.dataset_id, entry.title),
  };
}
