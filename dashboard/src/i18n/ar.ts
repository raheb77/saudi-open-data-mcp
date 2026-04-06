// Single Arabic copy module for the v1 dashboard.
// All user-facing strings live here and are referenced by name from
// the components. Technical identifiers (dataset_id, field names, source
// codes) are intentionally not translated — they remain Latin and are
// rendered with the monospace `id-mono` style.

export const ar = {
  app: {
    title: "لوحة البيانات السعودية المفتوحة",
    subtitle: "واجهة عرض رقيقة فوق نواة MCP الحالية",
    nav: {
      home: "الرئيسية",
      query: "الاستعلام",
      systemStatus: "حالة النظام",
    },
    role: {
      label: "الدور",
      viewer: "مُطّلع",
      operator: "مُشغّل",
      admin: "مدير",
    },
  },

  home: {
    heading: "نظرة عامة على مجموعات البيانات الرئيسية",
    description:
      "هذه نظرة موجزة على مجموعات بيانات مختارة. كل بطاقة تعكس بالضبط ما تُعيده النواة: المصدر والحالة وحداثة اللقطة المحلية.",
    viewQuery: "افتح صفحة الاستعلام",
    viewStatus: "افتح صفحة حالة النظام",
    cardLabels: {
      source: "المصدر",
      status: "الحالة الصحية",
      freshness: "الحداثة",
      origin: "أصل البيانات",
      lastUpdated: "آخر تحديث",
      schemaVersion: "إصدار المخطط",
      openInQuery: "افتح في صفحة الاستعلام",
    },
  },

  query: {
    heading: "الاستعلام عن السجلات المحلية",
    description:
      "هذه الصفحة تعرض استدعاء query_dataset كما تعرضه النواة: محلي فقط، مرشحات تطابق دقيق، حدّ نتائج اختياري.",
    datasetSelectorLabel: "اختر مجموعة البيانات",
    filtersLabel: "المرشحات",
    addFilter: "أضف مرشحًا",
    removeFilter: "احذف",
    keyPlaceholder: "اسم الحقل",
    valuePlaceholder: "القيمة",
    limitLabel: "الحد الأقصى للسجلات",
    apply: "تنفيذ الاستعلام",
    reset: "إعادة الضبط",
    export: "تصدير النتيجة (JSON)",
    scenarioLabel: "سيناريو محاكاة",
    scenarios: {
      success: "نجاح",
      limited: "محدود",
      stale: "لقطة قديمة",
      failed: "فشل",
      missing: "مجموعة غير موجودة",
      snapshotMissing: "لا توجد لقطة محلية",
      unauthorized: "غير مخوّل",
      loading: "تحميل",
    },
    table: {
      empty: "لا توجد سجلات مطابقة",
      recordIndex: "#",
      noColumns: "لا توجد أعمدة قابلة للعرض",
    },
    appliedFilters: "المرشحات المُطبَّقة",
    totalBeforeFilter: "إجمالي السجلات قبل الترشيح",
    matchedCount: "السجلات المطابقة",
    limitApplied: "الحد المُطبَّق",
  },

  status: {
    heading: "حالة النظام والمصادر",
    description:
      "تجميع رقيق لما تعرضه النواة فعلًا اليوم: جاهزية HTTP، حداثة المصادر، عدّادات المراقبة المحلية.",
    readiness: {
      title: "الجاهزية",
      ready: "جاهز",
      notReady: "غير جاهز",
      scope: "نطاق الفحص",
      checks: "الفحوصات",
      appName: "اسم التطبيق",
    },
    sources: {
      title: "حالة المصادر ومجموعات البيانات",
      summary:
        "ملخص لكل مجموعة بيانات: الحالة الصحية وحالة اللقطة المحلية. هذه ليست مقاييس فورية للمصدر الأصلي.",
    },
    counters: {
      title: "عدّادات المراقبة (محلية للعملية)",
      note: "تُعاد العدّادات إلى الصفر عند إعادة تشغيل العملية. هذه ليست واجهة مقاييس خارجية.",
    },
    materialization: {
      title: "ملخص آخر تحديث للمجموعة الساخنة",
      lastRunAt: "آخر تشغيل",
      successCount: "عدد النجاحات",
      failureCount: "عدد الإخفاقات",
      tierA: "المستوى أ",
      tierB: "المستوى ب",
    },
  },

  meta: {
    title: "سياق النتيجة",
    source: "المصدر",
    dataOrigin: "أصل البيانات",
    freshness: "الحداثة",
    status: "الحالة",
    degradation: "سبب التدهور",
    datasetId: "مُعرّف المجموعة",
    schemaVersion: "إصدار المخطط",
    snapshotAge: "عمر اللقطة",
  },

  state: {
    loading: "جارٍ التحميل…",
    empty: "لا توجد بيانات لعرضها",
    success: "ناجح",
    limited: "محدود",
    stale: "لقطة قديمة",
    failed: "فشل",
    missing: "غير موجود",
    snapshotMissing: "لا توجد لقطة محلية",
    unauthorized: "غير مخوّل",
    healthy: "سليم",
    degraded: "متدهور",
    unavailable: "غير متاح",
    unknown: "غير معروف",
    fresh: "حديث",
    freshnessUnknown: "غير محدد",
    localSnapshot: "لقطة محلية",
    liveRefresh: "تحديث مباشر",
    staleSnapshot: "لقطة قديمة",
    normalizationLimited: "تطبيع محدود",
    staleFallback: "احتياط بسبب فشل التحديث",
  },

  empty: {
    title: "لا توجد بيانات",
    body: "لا توجد سجلات مطابقة للمرشحات الحالية.",
  },

  error: {
    title: "تعذّر إكمال العملية",
    body: "أعادت النواة فشلًا واضحًا. لم نُخفِ التفاصيل خلف رسالة عامة.",
    stageLabel: "مرحلة الفشل",
    typeLabel: "نوع الخطأ",
  },

  limited: {
    title: "نتيجة محدودة من النواة",
    body: "النواة تمكّنت من قراءة اللقطة لكنها لم تستخرج سجلات قابلة للاستعلام. هذه الحالة مُصرَّح بها صراحة وليست خطأً.",
    limitationsLabel: "القيود المُعلنة",
  },

  stale: {
    title: "لقطة قديمة قيد العرض",
    body: "النواة عرضت لقطة محلية متجاوزة لنافذة الحداثة بعد فشل التحديث المباشر. القيمة محتملة الصلاحية لكنها متجاوزة.",
  },

  unauthorized: {
    title: "غير مخوّل بهذه القدرة",
    body: "الدور الحالي لا يمتلك القدرة المطلوبة لهذا الإجراء. هذه قاعدة من نواة النواة، وليست منطقًا مُختَرَعًا في الواجهة.",
  },

  missing: {
    title: "مجموعة بيانات غير معروفة",
    body: "لا يوجد سجل في السجل المركزي يطابق هذا المُعرّف.",
  },

  snapshotMissing: {
    title: "لا توجد لقطة محلية",
    body: "المجموعة معروفة في السجل لكن لا توجد لقطة محلية لقراءتها. شغّل عملية تحديث ثم أعد المحاولة.",
  },
} as const;

export type ArabicCopy = typeof ar;
