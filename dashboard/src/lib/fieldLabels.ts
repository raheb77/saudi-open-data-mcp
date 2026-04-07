// Arabic display labels for canonical record field names.
// Canonical field names are always English identifiers; these labels are
// shown in the result table header above the id-mono field name span.
// Unknown fields fall back to the raw field name — never omit a column.
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
