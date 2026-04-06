import { ar } from "../i18n/ar";
import type { QueryFilterValue } from "../types/core";

export interface FilterRow {
  key: string;
  value: string;
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
  function update(index: number, patch: Partial<FilterRow>) {
    const next = filters.map((row, i) => (i === index ? { ...row, ...patch } : row));
    onFiltersChange(next);
  }

  function remove(index: number) {
    onFiltersChange(filters.filter((_, i) => i !== index));
  }

  function add() {
    onFiltersChange([...filters, { key: "", value: "" }]);
  }

  return (
    <form
      className="flex flex-col gap-3 rounded-lg border border-ink-300 bg-white p-4 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <legend className="text-sm font-medium text-ink-700">
        {ar.query.filtersLabel}
      </legend>

      <div className="flex flex-col gap-2">
        {filters.length === 0 && (
          <p className="text-xs text-ink-500">—</p>
        )}
        {filters.map((row, index) => (
          <div key={index} className="flex flex-wrap items-center gap-2">
            <input
              aria-label={ar.query.keyPlaceholder}
              placeholder={ar.query.keyPlaceholder}
              value={row.key}
              onChange={(event) => update(index, { key: event.target.value })}
              className="id-mono w-44 rounded-md border border-ink-300 px-2 py-1 text-sm"
            />
            <span className="text-ink-500">=</span>
            <input
              aria-label={ar.query.valuePlaceholder}
              placeholder={ar.query.valuePlaceholder}
              value={row.value}
              onChange={(event) => update(index, { value: event.target.value })}
              className="id-mono w-56 rounded-md border border-ink-300 px-2 py-1 text-sm"
            />
            <button
              type="button"
              onClick={() => remove(index)}
              className="text-xs text-rose-700 hover:underline"
            >
              {ar.query.removeFilter}
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={add}
          className="self-start text-xs font-medium text-ink-700 hover:underline"
        >
          + {ar.query.addFilter}
        </button>
      </div>

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
