import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DatasetCard } from "../components/DatasetCard";
import {
  ErrorState,
  LoadingState,
  MissingState,
  UnauthorizedState,
} from "../components/StateBlocks";
import { ar } from "../i18n/ar";
import {
  FEATURED_DATASET_IDS,
  SOURCE_LABELS,
  localizeDatasetTitle,
} from "../lib/catalogPresentation";
import {
  getDatasetHealthResult,
  getDatasetPreviewResult,
  listDatasets,
} from "../lib/liveData";
import { DashboardApiError, asDashboardApiError } from "../lib/mcpClient";
import type {
  DatasetCatalogEntry,
  DatasetHealthLookupResult,
  DatasetPreviewResult,
} from "../types/core";

interface HomeCardData {
  datasetId: string;
  catalog: DatasetCatalogEntry | null;
  preview: DatasetPreviewResult | null;
  health: DatasetHealthLookupResult | undefined;
  previewError: DashboardApiError | null;
}

type HomePageState =
  | { kind: "loading" }
  | { kind: "failed"; error: DashboardApiError }
  | { kind: "ready"; cards: HomeCardData[] };

export function HomePage() {
  const [state, setState] = useState<HomePageState>({ kind: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });

    void (async () => {
      try {
        const catalog = await listDatasets(controller.signal);
        const catalogById = new Map(
          catalog.map((entry) => [entry.dataset_id, entry] as const),
        );
        const cards = await Promise.all(
          FEATURED_DATASET_IDS.map(async (datasetId) => {
            const entry = catalogById.get(datasetId) ?? null;
            if (!entry) {
              return {
                datasetId,
                catalog: null,
                preview: null,
                health: undefined,
                previewError: null,
              } satisfies HomeCardData;
            }

            const [previewResult, healthResult] = await Promise.allSettled([
              getDatasetPreviewResult(entry.dataset_id, controller.signal),
              getDatasetHealthResult(
                entry.dataset_id,
                entry.source,
                controller.signal,
              ),
            ]);

            return {
              datasetId: entry.dataset_id,
              catalog: entry,
              preview:
                previewResult.status === "fulfilled" ? previewResult.value : null,
              health:
                healthResult.status === "fulfilled" ? healthResult.value : undefined,
              previewError:
                previewResult.status === "rejected"
                  ? asDashboardApiError(
                      previewResult.reason,
                      "home_preview",
                      "تعذّر تحميل معاينة البطاقة.",
                    )
                  : null,
            } satisfies HomeCardData;
          }),
        );

        if (!controller.signal.aborted) {
          setState({ kind: "ready", cards });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setState({
            kind: "failed",
            error: asDashboardApiError(
              error,
              "home_page",
              "تعذّر تحميل الصفحة الرئيسية من النواة الحية.",
            ),
          });
        }
      }
    })();

    return () => controller.abort();
  }, [reloadToken]);

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

      {state.kind === "loading" && <LoadingState />}

      {state.kind === "failed" && (
        <section className="flex flex-col gap-3">
          {state.error.kind === "unauthorized" ? (
            <UnauthorizedState />
          ) : (
            <ErrorState
              stage={state.error.stage}
              errorType={state.error.name}
              message={state.error.message}
            />
          )}
          <button
            type="button"
            onClick={() => setReloadToken((value) => value + 1)}
            className="self-start rounded-md border border-ink-300 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-100"
          >
            {ar.app.retry}
          </button>
        </section>
      )}

      {state.kind === "ready" && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {state.cards.map((card) => (
            <HomeCard key={card.datasetId} card={card} />
          ))}
        </section>
      )}
    </div>
  );
}

function HomeCard({ card }: { card: HomeCardData }) {
  if (!card.catalog) {
    return (
      <article className="flex flex-col gap-3 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
        <header className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold text-ink-900">
            {localizeDatasetTitle(card.datasetId, card.datasetId)}
          </h3>
          <span className="id-mono text-[0.75rem] text-ink-500">
            {card.datasetId}
          </span>
        </header>
        <MissingState />
      </article>
    );
  }

  if (card.preview) {
    return (
      <DatasetCard
        catalog={card.catalog}
        preview={card.preview}
        health={card.health}
      />
    );
  }

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-ink-300 bg-white p-4 shadow-sm">
      <header className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-ink-900">{card.catalog.title}</h3>
        <span className="id-mono text-[0.75rem] text-ink-500">
          {card.catalog.dataset_id}
        </span>
      </header>
      <p className="text-xs text-ink-500">
        {ar.home.cardLabels.source}:{" "}
        <span>{SOURCE_LABELS[card.catalog.source] ?? card.catalog.source}</span>
        <span className="id-mono ms-2">{card.catalog.source}</span>
      </p>
      {card.previewError?.kind === "unauthorized" ? (
        <UnauthorizedState />
      ) : (
        <ErrorState
          stage={card.previewError?.stage ?? "home_preview"}
          errorType={card.previewError?.name ?? "DashboardApiError"}
          message={
            card.previewError?.message ?? "تعذّر تحميل معاينة هذه البطاقة."
          }
        />
      )}
    </article>
  );
}
