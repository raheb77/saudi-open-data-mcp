// Mock query results shaped exactly like DatasetQueryResult from
// src/saudi_open_data_mcp/tools/query.py. Each scenario covers one of
// the explicit core statuses so the dashboard can render them honestly.

import type {
  CanonicalRecord,
  DatasetQueryResult,
  QueryFilterValue,
} from "../types/core";
import { parseDatasetQueryResult } from "../lib/runtimeValidation";

export type QueryScenarioName =
  | "success"
  | "limited"
  | "stale"
  | "failed"
  | "missing"
  | "snapshot_missing"
  | "unauthorized"
  | "loading";

// ---------- success: SAMA POS weekly ----------

const POS_RECORDS: CanonicalRecord[] = [
  {
    dataset_id: "sama-pos-weekly",
    source: "sama",
    record_index: 0,
    fields: {
      week_start_date: "2026-03-23",
      week_end_date: "2026-03-29",
      transaction_count: 178_432_120,
      transaction_value_sar: 13_892_140_500,
      average_ticket_sar: 77.85,
    },
  },
  {
    dataset_id: "sama-pos-weekly",
    source: "sama",
    record_index: 1,
    fields: {
      week_start_date: "2026-03-16",
      week_end_date: "2026-03-22",
      transaction_count: 174_201_889,
      transaction_value_sar: 13_410_055_220,
      average_ticket_sar: 76.97,
    },
  },
  {
    dataset_id: "sama-pos-weekly",
    source: "sama",
    record_index: 2,
    fields: {
      week_start_date: "2026-03-09",
      week_end_date: "2026-03-15",
      transaction_count: 172_018_300,
      transaction_value_sar: 13_140_980_010,
      average_ticket_sar: 76.39,
    },
  },
  {
    dataset_id: "sama-pos-weekly",
    source: "sama",
    record_index: 3,
    fields: {
      week_start_date: "2026-03-02",
      week_end_date: "2026-03-08",
      transaction_count: 169_882_410,
      transaction_value_sar: 12_975_220_330,
      average_ticket_sar: 76.38,
    },
  },
];

const GDP_RECORDS: CanonicalRecord[] = [
  {
    dataset_id: "stats-gov-sa-real-gdp-growth-quarterly",
    source: "stats-gov-sa",
    record_index: 0,
    fields: {
      observation_quarter: "2025-Q4",
      gdp_series_code: "real_gdp_growth_rate_yoy",
      gdp_series_name: "Real GDP Growth Rate (Year-on-Year)",
      release_date: "2026-03-15",
      value_percent: 4.7,
    },
  },
  {
    dataset_id: "stats-gov-sa-real-gdp-growth-quarterly",
    source: "stats-gov-sa",
    record_index: 1,
    fields: {
      observation_quarter: "2025-Q3",
      gdp_series_code: "real_gdp_growth_rate_yoy",
      gdp_series_name: "Real GDP Growth Rate (Year-on-Year)",
      release_date: "2025-12-12",
      value_percent: 3.8,
    },
  },
  {
    dataset_id: "stats-gov-sa-real-gdp-growth-quarterly",
    source: "stats-gov-sa",
    record_index: 2,
    fields: {
      observation_quarter: "2025-Q2",
      gdp_series_code: "real_gdp_growth_rate_yoy",
      gdp_series_name: "Real GDP Growth Rate (Year-on-Year)",
      release_date: "2025-09-18",
      value_percent: 2.6,
    },
  },
];

const MOF_RECORDS: CanonicalRecord[] = [
  {
    dataset_id: "mof-budget-balance-quarterly",
    source: "mof",
    record_index: 0,
    fields: {
      observation_quarter: "2025-Q4",
      fiscal_series_code: "headline_budget_balance",
      fiscal_series_name: "Headline Budget Balance",
      value_sar_bn: -28.4,
    },
  },
  {
    dataset_id: "mof-budget-balance-quarterly",
    source: "mof",
    record_index: 1,
    fields: {
      observation_quarter: "2025-Q3",
      fiscal_series_code: "headline_budget_balance",
      fiscal_series_name: "Headline Budget Balance",
      value_sar_bn: -15.2,
    },
  },
];

const RECORD_BANK: Record<string, CanonicalRecord[]> = {
  "sama-pos-weekly": POS_RECORDS,
  "stats-gov-sa-real-gdp-growth-quarterly": GDP_RECORDS,
  "mof-budget-balance-quarterly": MOF_RECORDS,
};

const SOURCE_FOR_DATASET: Record<string, "sama" | "stats-gov-sa" | "mof"> = {
  "sama-pos-weekly": "sama",
  "sama-exchange-rates-current": "sama",
  "sama-repo-rate": "sama",
  "stats-gov-sa-cpi-headline-monthly": "stats-gov-sa",
  "stats-gov-sa-real-gdp-growth-quarterly": "stats-gov-sa",
  "mof-budget-balance-quarterly": "mof",
};

function applyMockFilters(
  records: CanonicalRecord[],
  filters: Record<string, QueryFilterValue>,
): CanonicalRecord[] {
  const keys = Object.keys(filters);
  if (keys.length === 0) return records;
  return records.filter((record) =>
    keys.every((key) => record.fields[key] === filters[key]),
  );
}

export function buildMockQueryResult(
  dataset_id: string,
  scenario: QueryScenarioName,
  filters: Record<string, QueryFilterValue> = {},
  limit: number | null = null,
): DatasetQueryResult {
  const source = SOURCE_FOR_DATASET[dataset_id] ?? null;
  const fallbackRecords = RECORD_BANK[dataset_id] ?? [];

  if (scenario === "missing") {
    return parseDatasetQueryResult({
      dataset_id,
      status: "missing",
      source: null,
      data_origin: null,
      applied_filters: filters,
      limit,
      total_records_before_filter: null,
      failure_stage: null,
      degradation_reason: null,
      matched_records: [],
      limitations: [],
      failure: null,
    });
  }

  if (scenario === "snapshot_missing") {
    return parseDatasetQueryResult({
      dataset_id,
      status: "snapshot_missing",
      source,
      data_origin: null,
      applied_filters: filters,
      limit,
      total_records_before_filter: null,
      failure_stage: null,
      degradation_reason: null,
      matched_records: [],
      limitations: [],
      failure: null,
    });
  }

  if (scenario === "limited") {
    return parseDatasetQueryResult({
      dataset_id,
      status: "limited",
      source,
      data_origin: "local_snapshot",
      applied_filters: filters,
      limit,
      total_records_before_filter: null,
      failure_stage: null,
      degradation_reason: "normalization_limited",
      matched_records: [],
      limitations: [
        "stats_gov_sa_cpi_headline_monthly_html_requires_supported_release_cards",
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
      ],
      failure: null,
    });
  }

  if (scenario === "failed") {
    return parseDatasetQueryResult({
      dataset_id,
      status: "failed",
      source,
      data_origin: "local_snapshot",
      applied_filters: filters,
      limit,
      total_records_before_filter: null,
      failure_stage: "normalization",
      degradation_reason: null,
      matched_records: [],
      limitations: [],
      failure: {
        stage: "normalization",
        error_type: "InvalidSourceResponseError",
        message:
          "Ministry of Finance reports page did not expose approved quarterly report PDF links",
      },
    });
  }

  if (scenario === "stale") {
    // Stale snapshots travel as a successful query result whose
    // data_origin is local_snapshot but whose freshness (visible on
    // the metadata strip) is `stale`.
    const filtered = applyMockFilters(fallbackRecords, filters);
    const limited = limit ? filtered.slice(0, limit) : filtered;
    return parseDatasetQueryResult({
      dataset_id,
      status: "success",
      source,
      data_origin: "local_snapshot",
      applied_filters: filters,
      limit,
      total_records_before_filter: fallbackRecords.length,
      failure_stage: null,
      degradation_reason: null,
      matched_records: limited,
      limitations: [],
      failure: null,
    });
  }

  // success (default)
  const filtered = applyMockFilters(fallbackRecords, filters);
  const limited = limit ? filtered.slice(0, limit) : filtered;
  return parseDatasetQueryResult({
    dataset_id,
    status: "success",
    source,
    data_origin: "local_snapshot",
    applied_filters: filters,
    limit,
    total_records_before_filter: fallbackRecords.length,
    failure_stage: null,
    degradation_reason: null,
    matched_records: limited,
    limitations: [],
    failure: null,
  });
}

export const FIELD_LABELS: Record<string, string> = {
  // SAMA POS weekly
  week_start_date: "بداية الأسبوع",
  week_end_date: "نهاية الأسبوع",
  transaction_count: "عدد العمليات",
  transaction_value_sar: "قيمة العمليات (ريال)",
  average_ticket_sar: "متوسط العملية (ريال)",
  // GDP
  observation_quarter: "الربع",
  gdp_series_code: "رمز السلسلة",
  gdp_series_name: "اسم السلسلة",
  release_date: "تاريخ الإصدار",
  value_percent: "القيمة (٪)",
  // MoF
  fiscal_series_code: "رمز السلسلة المالية",
  fiscal_series_name: "اسم السلسلة المالية",
  value_sar_bn: "القيمة (مليار ريال)",
};
