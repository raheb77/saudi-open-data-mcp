import { ar } from "../i18n/ar";
import { formatCellValue } from "../lib/format";
import { FIELD_LABELS } from "../lib/fieldLabels";
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

  // Derive columns from the first record. The table is honest: every
  // column is a field name actually present in the canonical record.
  const columns = Object.keys(records[0].fields);

  if (columns.length === 0) {
    return (
      <div className="rounded-lg border border-ink-300 bg-white px-4 py-6 text-center text-sm text-ink-500">
        {ar.query.table.noColumns}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-ink-300 bg-white shadow-sm">
      <table
        className="min-w-full divide-y divide-ink-300 text-sm"
        data-testid="result-table"
      >
        <thead className="bg-ink-100">
          <tr>
            <th
              scope="col"
              className="px-3 py-2 text-start text-xs font-semibold text-ink-700"
            >
              {ar.query.table.recordIndex}
            </th>
            {columns.map((column) => (
              <th
                key={column}
                scope="col"
                className="px-3 py-2 text-start text-xs font-semibold text-ink-700"
              >
                <div className="flex flex-col">
                  <span>{FIELD_LABELS[column] ?? column}</span>
                  <span className="id-mono text-[0.7rem] text-ink-500">
                    {column}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {records.map((record) => (
            <tr key={record.record_index} className="hover:bg-ink-50">
              <td className="num-latn px-3 py-2 text-ink-500">
                {record.record_index}
              </td>
              {columns.map((column) => {
                const value = record.fields[column];
                const isNumericLike =
                  typeof value === "number" ||
                  (typeof value === "string" &&
                    /^-?\d/.test(value));
                return (
                  <td
                    key={column}
                    className={`px-3 py-2 ${isNumericLike ? "num-latn" : ""}`}
                  >
                    {formatCellValue(value)}
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
