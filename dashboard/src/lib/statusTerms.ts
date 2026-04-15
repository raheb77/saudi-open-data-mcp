const STATUS_TRANSLATIONS: Record<string, string> = {
  internal_runtime_readiness: "جاهزية التشغيل الداخلية",

  process_running: "العملية تعمل",
  startup_validated: "بدء التشغيل مُتحقق",
  runtime_storage_prepared: "التخزين جاهز",
  app_wiring_completed: "الربط مكتمل",

  preview: "المعاينة",
  startup: "بدء التشغيل",
  connectors: "الموصّلات",
  auth: "المصادقة",
  materialization: "التحديث",
  materialize: "التحديث",
  tier_a_refresh: "تحديث المستوى أ",

  "preview.requests": "طلبات المعاينة",
  "preview.local_snapshot": "اللقطات المحلية",
  "preview.live_refresh": "التحديث المباشر",
  "preview.stale_fallback": "الرجوع للقديم",
  "preview.failures": "إخفاقات المعاينة",
  "preview.rate_limited": "تجاوز الحد",

  "server.startup.attempts": "محاولات البدء",
  "server.startup.ready": "جاهزية الخادم",
  "server.startup.failures": "إخفاقات البدء",

  "connector.retries": "إعادة المحاولات",
  "connector.failures": "إخفاقات الموصّلات",

  "http.auth.requests": "طلبات المصادقة",
  "http.auth.accepted": "مقبولة",
  "http.auth.rejected": "مرفوضة",
  "http.auth.rejected.missing": "مفقودة",
  "http.auth.rejected.invalid": "غير صالحة",
  "http.authz.rejected": "مرفوضة (تفويض)",
  "http.authz.rejected.insufficient_capability": "صلاحيات غير كافية",
  "http.authz.coverage_missing": "تغطية مفقودة",

  "materialize.requests": "طلبات التحديث",
  "materialize.successes": "نجاحات التحديث",
  "materialize.failures": "إخفاقات التحديث",

  "tier_a_refresh.runs": "دورات التحديث",
  "tier_a_refresh.run_failures": "إخفاقات الدورة",
};

const GROUP_SUMMARIES: Record<string, string> = {
  startup:
    "عدّادات بدء التشغيل محلية للعملية. تعكس المحاولات والجاهزية والإخفاقات، ولا تعبّر عن حركة الطلبات.",
  preview:
    "عدّادات طلبات المعاينة. عدّاد الطلبات يحسب الاستدعاءات، وبقية العدّادات تصف المسار النهائي أو الإخفاق.",
  auth:
    "عدّادات المصادقة والتفويض تخص مسار HTTP فقط. القبول والرفض نواتج ضمن طلبات المصادقة، وعدّادات التفويض تتتبع رفض الصلاحيات أو غياب التغطية بعد التحقق من الرمز.",
  connectors:
    "إجماليات إعادة المحاولة والإخفاق على مستوى الموصّلات. التفاصيل لكل مصدر تظهر أدناه للمراجعة السريعة.",
  materialization:
    "عدّادات تحديث المجموعة الساخنة. طلبات التحديث تحسب مرات التشغيل، بينما النجاحات والإخفاقات تحسب نتائج المجموعات داخل تلك الدورات.",
  materialize:
    "عدّادات تحديث المجموعة الساخنة. طلبات التحديث تحسب مرات التشغيل، بينما النجاحات والإخفاقات تحسب نتائج المجموعات داخل تلك الدورات.",
  tier_a_refresh:
    "عدّادات حلقة التحديث الخلفي للمستوى أ. هذه العدّادات تصف دورات الحلقة نفسها، لا نتائج كل مجموعة على حدة.",
};

const NOTE_TRANSLATIONS: Record<string, string> = {
  "Counters are process-local and reset on process restart.":
    "تُعاد العدّادات إلى الصفر عند إعادة تشغيل العملية.",
  "Request counters and outcome counters are not interchangeable; see each group summary.":
    "عدّادات الطلبات وعدّادات النتائج ليست متكافئة؛ راجع ملخص كل مجموعة قبل تفسيرها.",
  "Tier A background refresh emits tier_a_refresh.* structured log events, tier_a_refresh.* loop counters, and reuses materialize.* counters for per-dataset outcomes.":
    "تحديث المستوى أ الخلفي يصدر أحداث سجل منظمة من نوع tier_a_refresh.*، ويحدّث عدّادات الحلقة نفسها، ويعيد استخدام عدّادات materialize.* لنتائج كل مجموعة.",
};

const CONNECTOR_SOURCE_TRANSLATIONS: Record<string, string> = {
  sama: "ساما",
  stats_gov_sa: "الهيئة العامة للإحصاء",
  mof: "وزارة المالية",
  data_gov_sa: "البيانات المفتوحة",
  dummy: "المصدر التجريبي",
};

function translateConnectorSource(sourceKey: string): string {
  return CONNECTOR_SOURCE_TRANSLATIONS[sourceKey] ?? sourceKey.replaceAll("_", " ");
}

export function translateStatusTerm(key: string): string {
  if (STATUS_TRANSLATIONS[key]) {
    return STATUS_TRANSLATIONS[key];
  }

  if (key.startsWith("connector.request_attempts.")) {
    return `طلبات ${translateConnectorSource(key.slice("connector.request_attempts.".length))}`;
  }

  if (key.startsWith("connector.request_retries.")) {
    return `إعادات محاولة ${translateConnectorSource(key.slice("connector.request_retries.".length))}`;
  }

  if (key.startsWith("connector.request_failures.")) {
    return `إخفاقات ${translateConnectorSource(key.slice("connector.request_failures.".length))}`;
  }

  if (key.startsWith("connector.request_")) {
    return `طلبات ${translateConnectorSource(key.slice("connector.request_".length))}`;
  }

  return key;
}

export function translateStatusGroupSummary(
  groupName: string,
  fallback: string,
): string {
  return GROUP_SUMMARIES[groupName] ?? fallback;
}

export function translateStatusNote(note: string): string {
  return NOTE_TRANSLATIONS[note] ?? note;
}
