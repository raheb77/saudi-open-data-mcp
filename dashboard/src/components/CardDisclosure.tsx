import { useId, useState } from "react";
import { ar } from "../i18n/ar";
import { formatNumber } from "../lib/format";

interface CardDisclosureProps {
  summary: string;
  items: string[];
  tone?: "neutral" | "warn";
  technical?: boolean;
}

export function CardDisclosure({
  summary,
  items,
  tone = "neutral",
  technical = false,
}: CardDisclosureProps) {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();

  if (items.length === 0) {
    return null;
  }

  return (
    <section
      className={[
        "rounded-lg border px-3 py-2",
        tone === "warn"
          ? "border-amber-200 bg-amber-50/70"
          : "border-ink-200 bg-ink-50/70",
      ].join(" ")}
    >
      <button
        type="button"
        aria-controls={panelId}
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full flex-wrap items-center justify-between gap-2 text-right text-[0.72rem] font-medium text-ink-700"
      >
        <span>{summary}</span>
        <span className="flex items-center gap-2 text-[0.7rem] text-ink-500">
          <span className="num-latn">({formatNumber(items.length)})</span>
          <span>{expanded ? ar.cards.hideDetails : ar.cards.showDetails}</span>
        </span>
      </button>

      {expanded && (
        <ul id={panelId} className="mt-2 space-y-2">
          {items.map((entry) => (
            <li key={entry}>
              {technical ? (
                <span
                  className="id-mono block break-all rounded-md bg-white/80 px-2 py-1 text-[0.72rem] leading-5 text-ink-700"
                  dir="ltr"
                >
                  {entry}
                </span>
              ) : (
                <span className="block text-[0.78rem] leading-5 text-ink-700">
                  {entry}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
