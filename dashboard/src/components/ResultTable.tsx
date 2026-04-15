import { useState } from "react";
import { ar } from "../i18n/ar";
import { getDisplayValueLabel } from "../lib/displayText";
import { FIELD_LABELS } from "../lib/fieldLabels";
import { formatCellValue } from "../lib/format";
import {
  buildResultTableColumns,
  getExpandableTextClampClass,
  shouldRenderExpandableText,
  type ResultTableColumn,
} from "../lib/resultTablePresentation";
import type { CanonicalRecord } from "../types/core";

interface ResultTableProps {
  records: CanonicalRecord[];
}

export function ResultTable({ records }: ResultTableProps) {
  if (records.length === 0) {
    return (
      <div
        className="rounded-lg border border-ink-300 bg-white px-4 py-6 text-center text-sm text-ink-500"
        data-testid="result-table-empty"
      >
        {ar.query.table.empty}
      </div>
    );
  }

  // Keep the table honest to the canonical record fields, but sort them into
  // an analyst-first reading order so core measures and provenance are easier
  // to scan than raw source text blocks.
  const fieldNames = getVisibleTableFieldNames(records);
  const columns = buildResultTableColumns(fieldNames);

  if (columns.length === 0) {
    return (
      <div className="rounded-lg border border-ink-300 bg-white px-4 py-6 text-center text-sm text-ink-500">
        {ar.query.table.noColumns}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-ink-200 bg-white shadow-sm">
      <div
        className="max-h-[70vh] overflow-x-auto overflow-y-auto"
        data-testid="result-table-scroll-region"
      >
        <table
          className="result-table table-compact min-w-[800px] divide-y divide-ink-200 text-sm"
          data-testid="result-table"
        >
          <thead className="border-b border-ink-300">
            <tr>
              <th
                scope="col"
                className="w-14 min-w-[3.5rem] px-3 py-2.5 text-start text-[0.8rem] font-semibold text-ink-600"
              >
                {ar.query.table.recordIndex}
              </th>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  data-column-key={column.key}
                  title={column.key}
                  className={getHeaderClassName(column)}
                >
                  <span>{FIELD_LABELS[column.key] ?? column.key}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {records.map((record) => (
              <tr key={record.record_index} className="result-row">
                <td className="w-14 min-w-[3.5rem] px-3 py-2.5 align-top">
                  <span className="num-latn inline-flex min-w-7 items-center justify-center rounded-full bg-white px-1.5 py-0.5 text-[0.7rem] font-medium text-ink-500 shadow-sm ring-1 ring-inset ring-ink-200">
                    {record.record_index}
                  </span>
                </td>
                {columns.map((column) => {
                  const rawValue = record.fields[column.key];
                  const isPathValue =
                    typeof rawValue === "string" &&
                    isCompactPathField(column.key, rawValue);
                  const fullText =
                    typeof rawValue === "string" &&
                    ((column.isLink && isHttpUrl(rawValue)) || isPathValue)
                      ? rawValue
                      : undefined;
                  return (
                    <td
                      key={column.key}
                      className={getCellClassName(
                        column,
                        rawValue,
                        fullText,
                        isPathValue,
                      )}
                      data-full-text={fullText}
                    >
                      <ResultTableCell column={column} value={rawValue} />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResultTableCell({
  column,
  value,
}: {
  column: ResultTableColumn;
  value: CanonicalRecord["fields"][string];
}) {
  if (typeof value === "string" && column.isLink && isHttpUrl(value)) {
    return (
      <a
        href={value}
        target="_blank"
        rel="noreferrer"
        className={[
          "id-mono block truncate text-sky-700 underline decoration-sky-200 underline-offset-2 hover:text-sky-900",
          column.isSecondary || column.kind === "provenance-primary"
            ? "max-w-[7rem] text-[0.72rem] sm:max-w-[8.5rem] xl:max-w-[10rem]"
            : "max-w-[8rem] text-xs sm:max-w-[10rem] xl:max-w-[12rem]",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {value}
        <span className="text-[0.7em] opacity-60" aria-hidden="true"> ↗</span>
      </a>
    );
  }

  if (typeof value === "string" && isCompactPathField(column.key, value)) {
    return (
      <span
        className="id-mono block max-w-[7.5rem] truncate text-[0.72rem] leading-5 text-ink-600 sm:max-w-[9rem] xl:max-w-[10rem]"
        dir="ltr"
        title={value}
      >
        {compactPathValue(value)}
      </span>
    );
  }

  if (typeof value === "string" && shouldRenderExpandableText(column.key, value)) {
    return <ExpandableTextCell column={column} value={value} />;
  }

  const translatedValue =
    typeof value === "string" ? getDisplayValueLabel(value) : null;
  const formattedValue = translatedValue ?? formatCellValue(value);
  const displayTitle =
    typeof value === "string" && translatedValue
      ? value
      : typeof formattedValue === "string"
        ? formattedValue
        : undefined;

  return (
    <span
      className={getValueClassName(column, Boolean(translatedValue))}
      dir={translatedValue ? "auto" : column.isTechnicalToken ? undefined : "auto"}
      title={displayTitle}
    >
      {formattedValue}
    </span>
  );
}

function ExpandableTextCell({
  column,
  value,
}: {
  column: ResultTableColumn;
  value: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const clampClass = getExpandableTextClampClass(column);
  const isProvenance =
    column.kind === "provenance-primary" || column.kind === "provenance-secondary";

  return (
    <div className="flex max-w-[9rem] flex-col gap-1 sm:max-w-[11rem] xl:max-w-[13rem]">
      <span
        className={[
          "whitespace-pre-wrap break-words",
          expanded
            ? "rounded-md border border-ink-200 bg-white/80 px-2 py-1 leading-5"
            : `${clampClass} leading-5`,
          column.isSecondary || isProvenance
            ? "text-[0.72rem] text-ink-600"
            : "text-xs text-ink-700",
          column.isTechnicalToken ? "id-mono" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        dir="auto"
        title={value}
      >
        {value}
      </span>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
        className="self-start text-[0.68rem] font-medium text-ink-500 underline decoration-dotted underline-offset-2 hover:text-ink-900"
      >
        {expanded ? ar.query.table.showLess : ar.query.table.showMore}
      </button>
    </div>
  );
}

function getHeaderClassName(column: ResultTableColumn): string {
  return [
    "px-3 py-2.5 text-start font-semibold align-top break-normal whitespace-nowrap leading-5",
    column.isSecondary ||
    column.kind === "provenance-primary" ||
    column.kind === "context"
      ? "text-[0.72rem] text-ink-500"
      : "text-[0.8rem] text-ink-600",
    getWidthClassName(column),
  ]
    .filter(Boolean)
    .join(" ");
}

function getCellClassName(
  column: ResultTableColumn,
  value: CanonicalRecord["fields"][string],
  fullText?: string,
  isPathValue = false,
): string {
  const isNumericLike =
    typeof value === "number" ||
    (typeof value === "string" && /^-?\d/.test(value));

  return [
    "px-3 py-2.5 align-top",
    fullText ? "truncate-cell" : "",
    isPathValue ? "path-cell" : "",
    getWidthClassName(column),
    isNumericLike || column.kind === "time" || column.kind === "release"
      ? "num-latn"
      : "",
    column.kind === "provenance-primary"
      ? "bg-ink-50/55"
      : column.isSecondary
        ? "bg-ink-50/75"
        : "",
    column.kind === "long-text"
      ? "border-s border-ink-100"
      : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function getValueClassName(
  column: ResultTableColumn,
  hasTranslatedValue: boolean,
): string {
  return [
    "block whitespace-normal break-words leading-5",
    column.kind === "measure"
      ? "inline-flex min-w-[5rem] items-center rounded-md bg-ink-100 px-2 py-0.5 font-semibold text-ink-900"
      : "text-ink-800",
    column.kind === "time" || column.kind === "release"
      ? "whitespace-nowrap font-medium"
      : "",
    column.kind === "series-name" ? "font-medium text-ink-900" : "",
    column.kind === "context" ? "text-xs leading-5 text-ink-700" : "",
    column.kind === "provenance-primary" ? "text-xs leading-5 text-ink-700" : "",
    column.isSecondary ? "text-[0.72rem] leading-5 text-ink-600" : "",
    column.isTechnicalToken && !hasTranslatedValue ? "id-mono text-xs" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function getWidthClassName(column: ResultTableColumn): string {
  switch (column.kind) {
    case "time":
    case "release":
    case "measure":
      return "min-w-[8rem] whitespace-nowrap";
    case "series-code":
      return "min-w-[11rem]";
    case "series-name":
      return "min-w-[14rem]";
    case "context":
      return "min-w-[9rem]";
    case "provenance-primary":
      return "min-w-[9rem]";
    case "provenance-secondary":
      return "min-w-[8rem]";
    case "long-text":
      return "min-w-[9rem]";
    default:
      return "min-w-[8rem]";
  }
}

function isHttpUrl(value: string): boolean {
  return /^https?:\/\//.test(value);
}

function getVisibleTableFieldNames(records: CanonicalRecord[]): string[] {
  const seen = new Set<string>();
  const fieldNames: string[] = [];

  for (const record of records) {
    for (const fieldName of Object.keys(record.fields)) {
      if (seen.has(fieldName)) {
        continue;
      }
      seen.add(fieldName);
      fieldNames.push(fieldName);
    }
  }

  if (shouldHideDuplicateLinkColumn(records, "source_report_url", "source_url")) {
    return fieldNames.filter((fieldName) => fieldName !== "source_report_url");
  }

  return fieldNames;
}

function shouldHideDuplicateLinkColumn(
  records: CanonicalRecord[],
  duplicateKey: string,
  canonicalKey: string,
): boolean {
  let sawDuplicate = false;

  for (const record of records) {
    const duplicateValue = record.fields[duplicateKey];
    if (typeof duplicateValue !== "string" || duplicateValue.length === 0) {
      continue;
    }
    sawDuplicate = true;

    const canonicalValue = record.fields[canonicalKey];
    if (typeof canonicalValue !== "string" || canonicalValue !== duplicateValue) {
      return false;
    }
  }

  return sawDuplicate;
}

function isCompactPathField(fieldName: string, value: string): boolean {
  return fieldName === "source_locator" || (/^\//.test(value) && value.includes("/"));
}

function compactPathValue(value: string): string {
  if (value.length <= 28) {
    return value;
  }

  const [pathWithoutQuery] = value.split("?");
  const segments = pathWithoutQuery.split("/").filter(Boolean);

  if (segments.length === 0) {
    return `${value.slice(0, 20)}...`;
  }

  const leadingSegment = segments[0];
  const trailingSegment = segments[segments.length - 1];
  const compactTrailingSegment =
    trailingSegment.length > 16
      ? `${trailingSegment.slice(0, 13)}...`
      : trailingSegment;

  return `/${leadingSegment}/.../${compactTrailingSegment}`;
}
