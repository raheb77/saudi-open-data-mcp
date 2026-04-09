import { ar } from "../i18n/ar";
import type { QueryFilterValue } from "../types/core";

export interface FilterRow {
  id?: string;
  key: string;
  value: string;
}

let filterRowSequence = 0;

export function createFilterRow(): FilterRow {
  filterRowSequence += 1;
  return {
    id: `filter-row-${filterRowSequence}`,
    key: "",
    value: "",
  };
}

interface FilterFormProps {
  filters: FilterRow[];
  onFiltersChange: (filters: FilterRow[]) => void;
  limit: string;
  onLimitChange: (limit: string) => void;
  onApply: () => void;
  onReset: () => void;
}

export function FilterForm({
  filters,
  onFiltersChange,
  limit,
  onLimitChange,
  onApply,
  onReset,
}: FilterFormProps) {
  function update(targetId: string, patch: Partial<FilterRow>) {
    const next = filters.map((row, index) =>
      filterRowIdentity(row, index) === targetId ? { ...row, ...patch } : row,
    );
    onFiltersChange(next);
  }

  function remove(targetId: string) {
    onFiltersChange(
      filters.filter((row, index) => filterRowIdentity(row, index) !== targetId),
    );
  }

  function add() {
    onFiltersChange([...filters, createFilterRow()]);
  }

  return (
    <form
      className="flex flex-col gap-3 rounded-lg border border-ink-300 bg-white p-4 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-medium text-ink-700">
          {ar.query.filtersLabel}
        </legend>

        <div className="flex flex-col gap-2">
          {filters.length === 0 && (
            <p className="text-xs text-ink-500">—</p>
          )}
          {filters.map((row, index) => {
            const rowId = filterRowIdentity(row, index);
            const rowLabelId = `${rowId}-label`;
            return (
              <div
                key={rowId}
                role="group"
                aria-labelledby={rowLabelId}
                className="flex flex-wrap items-center gap-2"
              >
                <span id={rowLabelId} className="sr-only">
                  {ar.query.filterRowLabel} {index + 1}
                </span>
                <input
                  aria-label={ar.query.keyPlaceholder}
                  aria-describedby={rowLabelId}
                  dir="ltr"
                  placeholder={ar.query.keyPlaceholder}
                  value={row.key}
                  onChange={(event) => update(rowId, { key: event.target.value })}
                  className="id-mono w-44 rounded-md border border-ink-300 px-2 py-1 text-sm"
                />
                <span className="text-ink-500">=</span>
                <input
                  aria-label={ar.query.valuePlaceholder}
                  aria-describedby={rowLabelId}
                  dir="ltr"
                  placeholder={ar.query.valuePlaceholder}
                  value={row.value}
                  onChange={(event) => update(rowId, { value: event.target.value })}
                  className="id-mono w-56 rounded-md border border-ink-300 px-2 py-1 text-sm"
                />
                <button
                  type="button"
                  aria-label={`${ar.query.removeFilter} ${index + 1}`}
                  aria-describedby={rowLabelId}
                  onClick={() => remove(rowId)}
                  className="text-xs text-rose-700 hover:underline"
                >
                  {ar.query.removeFilter}
                </button>
              </div>
            );
          })}
          <button
            type="button"
            onClick={add}
            className="self-start text-xs font-medium text-ink-700 hover:underline"
          >
            + {ar.query.addFilter}
          </button>
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-ink-700">
          <span>{ar.query.limitLabel}</span>
          <input
            type="number"
            min="1"
            max="1000"
            value={limit}
            onChange={(event) => onLimitChange(event.target.value)}
            className="num-latn w-24 rounded-md border border-ink-300 px-2 py-1 text-sm"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="submit"
          className="rounded-md bg-ink-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-ink-700"
        >
          {ar.query.apply}
        </button>
        <button
          type="button"
          onClick={onReset}
          className="rounded-md border border-ink-300 px-3 py-1.5 text-sm font-medium text-ink-700 hover:bg-ink-100"
        >
          {ar.query.reset}
        </button>
      </div>
    </form>
  );
}

export function filterRowsToFilters(
  rows: FilterRow[],
): Record<string, QueryFilterValue> {
  const result: Record<string, QueryFilterValue> = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (!key) continue;
    const raw = row.value.trim();
    if (raw === "") {
      result[key] = "";
      continue;
    }
    // Match the CLI: try JSON-scalar parse, fall back to plain string.
    try {
      const parsed = JSON.parse(raw);
      if (
        typeof parsed === "string" ||
        typeof parsed === "number" ||
        typeof parsed === "boolean" ||
        parsed === null
      ) {
        result[key] = parsed;
        continue;
      }
    } catch {
      // fall through
    }
    result[key] = raw;
  }
  return result;
}

function filterRowIdentity(row: FilterRow, index: number): string {
  return row.id ?? `legacy-filter-row-${index}`;
}
