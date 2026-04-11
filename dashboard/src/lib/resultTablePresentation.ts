export type ResultTableColumnKind =
  | "time"
  | "series-code"
  | "series-name"
  | "measure"
  | "release"
  | "provenance-primary"
  | "provenance-secondary"
  | "long-text"
  | "default";

export interface ResultTableColumn {
  key: string;
  kind: ResultTableColumnKind;
  isLink: boolean;
  isSecondary: boolean;
  isTechnicalToken: boolean;
}

const TIME_FIELDS = new Set([
  "observation_date",
  "observation_month",
  "observation_quarter",
  "week_start_date",
  "week_end_date",
]);

const SERIES_CODE_FIELDS = new Set([
  "series_code",
  "inflation_series_code",
  "gdp_series_code",
  "labor_series_code",
  "fiscal_series_code",
  "deposit_category_code",
]);

const SERIES_NAME_FIELDS = new Set([
  "series_name",
  "inflation_series_name",
  "gdp_series_name",
  "labor_series_name",
  "fiscal_series_name",
  "deposit_category_name",
]);

const MEASURE_FIELDS = new Set([
  "transaction_count",
  "transaction_value_sar",
  "average_ticket_sar",
  "value",
  "value_percent",
  "value_sar_bn",
  "yoy_rate_percent",
  "mom_rate_percent",
]);

const PRIMARY_PROVENANCE_FIELDS = new Set([
  "source_release_title",
  "source_release_url",
  "source_report_url",
  "source_url",
]);

const SECONDARY_PROVENANCE_FIELDS = new Set([
  "source_release_date_text",
  "source_locator",
  "source_series_name",
  "source_observation_month_text",
]);

const LONG_TEXT_FIELDS = new Set(["source_summary_text"]);

const LINK_FIELDS = new Set([
  "source_release_url",
  "source_report_url",
  "source_url",
]);

const TECHNICAL_TOKEN_FIELDS = new Set([
  "series_code",
  "inflation_series_code",
  "gdp_series_code",
  "labor_series_code",
  "fiscal_series_code",
  "deposit_category_code",
  "source_locator",
  ...LINK_FIELDS,
]);

const EXPLICIT_COLUMN_ORDER = new Map([
  ["observation_date", 10],
  ["observation_month", 20],
  ["observation_quarter", 30],
  ["week_start_date", 40],
  ["week_end_date", 50],
  ["transaction_count", 100],
  ["transaction_value_sar", 110],
  ["average_ticket_sar", 120],
  ["value", 130],
  ["value_percent", 140],
  ["value_sar_bn", 150],
  ["yoy_rate_percent", 160],
  ["mom_rate_percent", 170],
  ["series_name", 220],
  ["inflation_series_name", 230],
  ["gdp_series_name", 240],
  ["labor_series_name", 250],
  ["fiscal_series_name", 260],
  ["deposit_category_name", 270],
  ["series_code", 300],
  ["inflation_series_code", 310],
  ["gdp_series_code", 320],
  ["labor_series_code", 330],
  ["fiscal_series_code", 340],
  ["deposit_category_code", 350],
  ["release_date", 390],
  ["source_release_title", 500],
  ["source_release_url", 510],
  ["source_report_url", 520],
  ["source_url", 530],
  ["source_release_date_text", 600],
  ["source_locator", 610],
  ["source_series_name", 620],
  ["source_observation_month_text", 630],
  ["source_summary_text", 700],
]);

export function buildResultTableColumns(fieldNames: string[]): ResultTableColumn[] {
  return [...fieldNames]
    .map((key, originalIndex) => ({
      key,
      kind: getResultTableColumnKind(key),
      isLink: LINK_FIELDS.has(key),
      isSecondary:
        SECONDARY_PROVENANCE_FIELDS.has(key) || LONG_TEXT_FIELDS.has(key),
      isTechnicalToken: TECHNICAL_TOKEN_FIELDS.has(key),
      originalIndex,
      sortOrder: getResultTableColumnOrder(key),
    }))
    .sort(
      (left, right) =>
        left.sortOrder - right.sortOrder ||
        left.originalIndex - right.originalIndex,
    )
    .map(({ originalIndex: _originalIndex, sortOrder: _sortOrder, ...column }) => column);
}

export function shouldRenderExpandableText(fieldName: string, value: string): boolean {
  const normalized = value.trim();
  if (!normalized) {
    return false;
  }

  if (LONG_TEXT_FIELDS.has(fieldName)) {
    return true;
  }

  if (fieldName === "source_release_title" && normalized.length > 60) {
    return true;
  }

  if (
    !LINK_FIELDS.has(fieldName) &&
    PRIMARY_PROVENANCE_FIELDS.has(fieldName) &&
    normalized.length > 90
  ) {
    return true;
  }

  if (
    !LINK_FIELDS.has(fieldName) &&
    SECONDARY_PROVENANCE_FIELDS.has(fieldName) &&
    normalized.length > 72
  ) {
    return true;
  }

  return normalized.includes("\n") || normalized.length > 140;
}

export function getExpandableTextClampClass(
  column: ResultTableColumn,
): "cell-clamp-1" | "cell-clamp-2" {
  switch (column.kind) {
    case "provenance-secondary":
      return "cell-clamp-1";
    case "long-text":
    case "provenance-primary":
    default:
      return "cell-clamp-2";
  }
}

function getResultTableColumnKind(fieldName: string): ResultTableColumnKind {
  if (TIME_FIELDS.has(fieldName)) {
    return "time";
  }

  if (SERIES_CODE_FIELDS.has(fieldName) || fieldName.endsWith("_series_code")) {
    return "series-code";
  }

  if (SERIES_NAME_FIELDS.has(fieldName) || fieldName.endsWith("_series_name")) {
    return "series-name";
  }

  if (fieldName === "release_date") {
    return "release";
  }

  if (LONG_TEXT_FIELDS.has(fieldName) || fieldName.endsWith("_summary_text")) {
    return "long-text";
  }

  if (PRIMARY_PROVENANCE_FIELDS.has(fieldName)) {
    return "provenance-primary";
  }

  if (SECONDARY_PROVENANCE_FIELDS.has(fieldName) || fieldName.startsWith("source_")) {
    return "provenance-secondary";
  }

  if (isMeasureField(fieldName)) {
    return "measure";
  }

  return "default";
}

function getResultTableColumnOrder(fieldName: string): number {
  const explicitOrder = EXPLICIT_COLUMN_ORDER.get(fieldName);
  if (explicitOrder !== undefined) {
    return explicitOrder;
  }

  const kind = getResultTableColumnKind(fieldName);
  switch (kind) {
    case "time":
      return 90;
    case "measure":
      return 190;
    case "series-name":
      return 240;
    case "series-code":
      return 290;
    case "release":
      return 390;
    case "provenance-primary":
      return 590;
    case "provenance-secondary":
      return 690;
    case "long-text":
      return 790;
    default:
      return 540;
  }
}

function isMeasureField(fieldName: string): boolean {
  if (MEASURE_FIELDS.has(fieldName)) {
    return true;
  }

  return (
    !fieldName.startsWith("source_") &&
    /(_count|_value(?:_|$)|_rate(?:_|$)|_percent$|_sar(?:_bn)?$)/.test(
      fieldName,
    )
  );
}
