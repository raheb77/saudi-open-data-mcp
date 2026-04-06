import { Link } from "react-router-dom";
import { DatasetCard } from "../components/DatasetCard";
import { ar } from "../i18n/ar";
import { MOCK_DATASETS } from "../mocks/datasets";
import { findHealthById } from "../mocks/health";

export function HomePage() {
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold text-ink-900">
          {ar.home.heading}
        </h2>
        <p className="max-w-3xl text-sm leading-relaxed text-ink-700">
          {ar.home.description}
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/query"
            className="rounded-md border border-ink-300 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
          >
            {ar.home.viewQuery}
          </Link>
          <Link
            to="/status"
            className="rounded-md border border-ink-300 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
          >
            {ar.home.viewStatus}
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {MOCK_DATASETS.map((catalog) => (
          <DatasetCard
            key={catalog.dataset_id}
            catalog={catalog}
            health={findHealthById(catalog.dataset_id)}
          />
        ))}
      </section>
    </div>
  );
}
