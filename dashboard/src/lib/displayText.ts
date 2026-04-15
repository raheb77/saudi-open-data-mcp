import { FIELD_LABELS } from "./fieldLabels";

const VALUE_LABELS: Record<string, string> = {
  repo_rate: "سعر إعادة الشراء",
  reverse_repo_rate: "سعر إعادة الشراء العكسي",
  unemployment_rate_total_population_15_plus: "معدل البطالة (15+)",
  headline_cpi_all_items: "مؤشر أسعار المستهلك",
  "Official Repo Rate": "سعر إعادة الشراء الرسمي",
  "Reverse Repo Rate": "سعر إعادة الشراء العكسي",
  "Headline CPI": "مؤشر أسعار المستهلك",
};

const RECENCY_WARNING_PATTERN =
  /^latest observation (?<observation>.+) is materially behind the expected (?<frequency>daily|weekly|monthly|quarterly|annual) recency window$/;

const RECENCY_FREQUENCY_LABELS: Record<string, string> = {
  daily: "اليومي",
  weekly: "الأسبوعي",
  monthly: "الشهري",
  quarterly: "الفصلي",
  annual: "السنوي",
};

export function getDisplayValueLabel(value: string): string | null {
  return VALUE_LABELS[value] ?? FIELD_LABELS[value] ?? null;
}

export function translateObservationRecencyWarning(warning: string): string {
  const match = RECENCY_WARNING_PATTERN.exec(warning);
  if (!match?.groups) {
    return warning;
  }

  const frequencyLabel = RECENCY_FREQUENCY_LABELS[match.groups.frequency];
  if (!frequencyLabel) {
    return warning;
  }

  return `آخر رصد (${match.groups.observation}) متأخر عن النافذة الزمنية المتوقعة للتحديث ${frequencyLabel}`;
}
