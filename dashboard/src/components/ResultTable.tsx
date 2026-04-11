import { useState } from "react";
import { ar } from "../i18n/ar";
import { FIELD_LABELS } from "../lib/fieldLabels";
import { formatCellValue } from "../lib/format";
import {
  buildResultTableColumns,
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
  const columns = buildResultTableColumns(Object.keys(records[0].fields));

  if (columns.length === 0) {
    return (
      <div className="rounded-lg border border-ink-300 bg-white px-4 py-6 text-center text-sm text-ink-500">
        {ar.query.table.noColumns}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-ink-200 bg-white shadow-sm">
      <table
        className="min-w-full divide-y divide-ink-200 text-sm"
        data-testid="result-table"
      >
        <thead className="bg-ink-100">
          <tr>
            <th
              scope="col"
              className="sticky top-0 z-10 bg-ink-100 px-3 py-2 text-start text-xs font-semibold text-ink-700"
            >
              {ar.query.table.recordIndex}
            </th>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                data-column-key={column.key}
                className={getHeaderClassName(column)}
              >
                <div className="flex flex-col">
                  <span>{FIELD_LABELS[column.key] ?? column.key}</span>
                  <span className="id-mono text-[0.7rem] text-ink-500">
                    {column.key}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {records.map((record) => (
            <tr
              key={record.record_index}
              className="odd:bg-white even:bg-ink-50 hover:bg-ink-100"
            >
              <td className="px-3 py-3 align-top">
                <span className="num-latn inline-flex min-w-8 items-center justify-center rounded-full bg-white px-2 py-1 text-xs font-medium text-ink-500 shadow-sm ring-1 ring-inset ring-ink-200">
                  {record.record_index}
                </span>
              </td>
              {columns.map((column) => {
                return (
                  <td
                    key={column.key}
                    className={getCellClassName(column, record.fields[column.key])}
                  >
                    <ResultTableCell
                      column={column}
                      value={record.fields[column.key]}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
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
        className="id-mono block max-w-[11rem] truncate rounded-md bg-white px-2 py-1 text-sky-700 underline decoration-sky-300 underline-offset-2 ring-1 ring-inset ring-ink-200 hover:text-sky-900 sm:max-w-[14rem] xl:max-w-[16rem]"
        title={value}
      >
        {value}
      </a>
    );
  }

  if (typeof value === "string" && shouldRenderExpandableText(column.key, value)) {
    return <ExpandableTextCell secondary={column.isSecondary} value={value} />;
  }

  const formattedValue = formatCellValue(value);
  return (
    <span
      className={getValueClassName(column)}
      dir={column.isTechnicalToken ? undefined : "auto"}
      title={typeof formattedValue === "string" ? formattedValue : undefined}
    >
      {formattedValue}
    </span>
  );
}

function ExpandableTextCell({
  secondary,
  value,
}: {
  secondary: boolean;
  value: string;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex max-w-[12rem] flex-col gap-1 sm:max-w-[16rem] xl:max-w-[20rem]">
      <span
        className={[
          "rounded-md border border-ink-200 px-2.5 py-2 whitespace-pre-wrap break-words leading-6",
          expanded ? "" : "cell-clamp-3",
          secondary
            ? "bg-ink-50 text-xs text-ink-600"
            : "bg-white text-sm text-ink-800",
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
        className="self-start text-xs font-medium text-ink-600 underline decoration-dotted underline-offset-2 hover:text-ink-900"
      >
        {expanded ? ar.query.table.showLess : ar.query.table.showMore}
      </button>
    </div>
  );
}

function getHeaderClassName(column: ResultTableColumn): string {
  return [
    "sticky top-0 z-10 bg-ink-100 px-3 py-2 text-start text-xs font-semibold align-top",
    column.isSecondary ? "text-ink-600" : "text-ink-700",
    getWidthClassName(column),
  ]
    .filter(Boolean)
    .join(" ");
}

function getCellClassName(
  column: ResultTableColumn,
  value: CanonicalRecord["fields"][string],
): string {
  const isNumericLike =
    typeof value === "number" ||
    (typeof value === "string" && /^-?\d/.test(value));

  return [
    "px-3 py-3 align-top",
    getWidthClassName(column),
    isNumericLike || column.kind === "time" || column.kind === "release"
      ? "num-latn"
      : "",
    column.isSecondary || column.kind === "provenance-primary"
      ? "bg-ink-50/70"
      : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function getValueClassName(column: ResultTableColumn): string {
  return [
    "block whitespace-normal break-words leading-6",
    column.kind === "measure"
      ? "inline-flex min-w-[5.75rem] items-center rounded-md bg-ink-100 px-2 py-1 font-semibold text-ink-900"
      : "text-ink-800",
    column.kind === "time" || column.kind === "release"
      ? "whitespace-nowrap font-medium"
      : "",
    column.kind === "series-name" ? "font-medium text-ink-900" : "",
    column.kind === "provenance-primary" ? "text-sm text-ink-700" : "",
    column.isSecondary ? "text-xs text-ink-600" : "",
    column.isTechnicalToken ? "id-mono text-xs" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function getWidthClassName(column: ResultTableColumn): string {
  switch (column.kind) {
    case "time":
    case "release":
    case "measure":
      return "whitespace-nowrap";
    case "series-code":
      return "min-w-[11rem]";
    case "series-name":
      return "min-w-[14rem]";
    case "provenance-primary":
      return "min-w-[12rem]";
    case "provenance-secondary":
      return "min-w-[10rem]";
    case "long-text":
      return "min-w-[12rem]";
    default:
      return "";
  }
}

function isHttpUrl(value: string): boolean {
  return /^https?:\/\//.test(value);
}
