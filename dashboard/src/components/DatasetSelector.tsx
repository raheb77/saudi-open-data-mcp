import { ar } from "../i18n/ar";
import type { DatasetCatalogEntry } from "../types/core";

interface DatasetSelectorProps {
  datasets: DatasetCatalogEntry[];
  value: string;
  onChange: (datasetId: string) => void;
}

export function DatasetSelector({
  datasets,
  value,
  onChange,
}: DatasetSelectorProps) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor="dataset-selector"
        className="text-sm font-medium text-ink-700"
      >
        {ar.query.datasetSelectorLabel}
      </label>
      <select
        id="dataset-selector"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-ink-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-ink-700 focus:outline-none focus:ring-1 focus:ring-ink-700"
      >
        {datasets.map((dataset) => (
          <option key={dataset.dataset_id} value={dataset.dataset_id}>
            {dataset.title}
          </option>
        ))}
      </select>
      <span className="id-mono text-[0.75rem] text-ink-500">{value}</span>
    </div>
  );
}
