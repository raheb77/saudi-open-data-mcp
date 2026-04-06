// Mock ObservabilitySummary payload, structurally identical to the
// real resource://observability output. Counter names match the real
// _COUNTER_GROUP_SPECS in observability/summary.py exactly.

import type { ObservabilitySummary } from "../types/core";

export const MOCK_OBSERVABILITY: ObservabilitySummary = {
  process_local: true,
  groups: [
    {
      name: "startup",
      summary:
        "عدّادات بناء الخادم محلية للعملية. تعكس مرات المحاولة والجهوزية والإخفاقات وليس حركة الطلبات.",
      counters: [
        { name: "server.startup.attempts", value: 3 },
        { name: "server.startup.ready", value: 3 },
        { name: "server.startup.failures", value: 0 },
      ],
      detail_counters: [],
    },
    {
      name: "preview",
      summary:
        "عدّادات طلبات المعاينة. preview.requests يحسب الاستدعاءات؛ بقية العدّادات تعكس المسار النهائي.",
      counters: [
        { name: "preview.requests", value: 142 },
        { name: "preview.local_snapshot", value: 118 },
        { name: "preview.live_refresh", value: 19 },
        { name: "preview.stale_fallback", value: 3 },
        { name: "preview.failures", value: 2 },
        { name: "preview.rate_limited", value: 0 },
      ],
      detail_counters: [],
    },
    {
      name: "auth",
      summary:
        "عدّادات مصادقة HTTP لمسار run-http فقط.",
      counters: [
        { name: "http.auth.requests", value: 268 },
        { name: "http.auth.accepted", value: 264 },
        { name: "http.auth.rejected", value: 4 },
        { name: "http.auth.rejected.missing", value: 1 },
        { name: "http.auth.rejected.invalid", value: 3 },
        { name: "http.authz.rejected", value: 0 },
        { name: "http.authz.rejected.insufficient_capability", value: 0 },
        { name: "http.authz.coverage_missing", value: 0 },
      ],
      detail_counters: [],
    },
    {
      name: "connectors",
      summary:
        "إجماليات إعادة المحاولة والإخفاق على مستوى الموصلات. التفاصيل لكل مصدر أدناه.",
      counters: [
        { name: "connector.retries", value: 6 },
        { name: "connector.failures", value: 1 },
      ],
      detail_counters: [
        { name: "connector.request_sama", value: 102 },
        { name: "connector.request_stats_gov_sa", value: 41 },
        { name: "connector.request_mof", value: 14 },
      ],
    },
    {
      name: "materialization",
      summary:
        "عدّادات تحديث المجموعة الساخنة، بما في ذلك دورات التحديث الخلفي للمستوى أ.",
      counters: [
        { name: "materialize.requests", value: 12 },
        { name: "materialize.successes", value: 60 },
        { name: "materialize.failures", value: 0 },
      ],
      detail_counters: [],
    },
    {
      name: "tier_a_refresh",
      summary:
        "عدّادات حلقة التحديث الخلفي للمستوى أ. هذه دورات حلقة وليست نتائج لكل مجموعة.",
      counters: [
        { name: "tier_a_refresh.runs", value: 12 },
        { name: "tier_a_refresh.run_failures", value: 0 },
      ],
      detail_counters: [],
    },
  ],
  raw_counters: {},
  notes: [
    "تُعاد العدّادات إلى الصفر عند إعادة تشغيل العملية.",
    "هذه ليست واجهة مقاييس خارجية؛ إنها لقطة محلية للعملية فقط.",
  ],
};
