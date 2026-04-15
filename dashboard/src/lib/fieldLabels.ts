// Arabic display labels for canonical record field names.
// Canonical field names are always English identifiers; these labels are
// shown in the result table header above the id-mono field name span.
// Unknown fields fall back to the raw field name — never omit a column.
export const FIELD_LABELS: Record<string, string> = {
  // SAMA exchange rates
  as_of_date: "تاريخ السعر",
  effective_date: "تاريخ السريان",
  currency_code: "رمز العملة",
  currency_name: "اسم العملة",
  quote_currency_code: "رمز عملة التسعير",
  quote_currency_name: "عملة التسعير",
  closing_rate_sar: "سعر الإغلاق (ريال)",
  // SAMA POS weekly
  week_start_date: "بداية الأسبوع",
  week_end_date: "نهاية الأسبوع",
  transaction_count: "عدد العمليات",
  transaction_value_sar: "قيمة العمليات (ريال)",
  average_ticket_sar: "متوسط العملية (ريال)",
  source_table_title: "عنوان الجدول",
  source_period_text: "الفترة",
  // Inflation
  observation_date: "تاريخ الرصد",
  observation_month: "شهر الرصد",
  observation_year: "سنة الرصد",
  inflation_series_code: "رمز سلسلة التضخم",
  inflation_series_name: "اسم سلسلة التضخم",
  yoy_rate_percent: "التغير السنوي (٪)",
  mom_rate_percent: "التغير الشهري (٪)",
  // GDP
  observation_quarter: "الربع",
  series_code: "رمز السلسلة",
  series_name: "اسم السلسلة",
  gdp_series_code: "رمز السلسلة",
  gdp_series_name: "اسم السلسلة",
  release_date: "تاريخ الإصدار",
  value_percent: "القيمة (٪)",
  // Labor
  labor_series_code: "رمز سلسلة العمل",
  labor_series_name: "اسم سلسلة العمل",
  deposit_category_code: "رمز فئة الودائع",
  deposit_category_name: "اسم فئة الودائع",
  // Generic
  value: "القيمة",
  // MoF
  fiscal_series_code: "رمز السلسلة المالية",
  fiscal_series_name: "اسم السلسلة المالية",
  value_sar_bn: "القيمة (مليار ريال)",
  policy_rate_code: "رمز السعر",
  policy_rate_name: "اسم السعر",
  rate_percent: "النسبة المئوية",
  // Provenance
  source_release_title: "عنوان الإصدار",
  source_release_url: "رابط الإصدار",
  source_report_url: "رابط التقرير",
  source_url: "رابط المصدر",
  source_change_points_text: "نقاط التغيير",
  source_release_date_text: "تاريخ الإصدار النصي",
  source_locator: "محدد المصدر",
  source_currency_text: "اسم العملة في المصدر",
  source_last_updated_date_text: "تاريخ التحديث في المصدر",
  source_page_number: "رقم الصفحة في المصدر",
  source_page_url: "رابط صفحة المصدر",
  source_publish_date_text: "تاريخ النشر",
  source_rate_text: "نص السعر",
  source_series_name: "اسم السلسلة في المصدر",
  source_observation_month_text: "الشهر كما ورد في المصدر",
  source_summary_text: "ملخص المصدر",
};
