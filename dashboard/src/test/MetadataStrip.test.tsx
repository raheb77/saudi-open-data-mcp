import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetadataStrip } from "../components/MetadataStrip";

describe("MetadataStrip", () => {
  it("renders dataset_id, source and data_origin for a successful result", () => {
    render(
      <MetadataStrip
        dataset_id="sama-pos-weekly"
        source="sama"
        status_kind="query"
        status="success"
        data_origin="local_snapshot"
        freshness_status="fresh"
        degradation_reason={null}
        schema_version="1.0.0"
        snapshot_age_label="5d 0h"
      />,
    );

    const strip = screen.getByTestId("metadata-strip");
    expect(strip).toBeInTheDocument();
    expect(strip).toHaveTextContent("sama-pos-weekly");
    expect(strip).toHaveTextContent("sama");
    expect(strip).toHaveTextContent("1.0.0");
    expect(strip).toHaveTextContent("5d 0h");
  });

  it("omits optional rows when fields are absent (no fabrication)", () => {
    render(
      <MetadataStrip
        dataset_id="stats-gov-sa-cpi-headline-monthly"
        source="stats-gov-sa"
        status_kind="query"
        status="missing"
        data_origin={null}
      />,
    );

    const strip = screen.getByTestId("metadata-strip");
    // Schema version and snapshot age were not provided and must not
    // appear in the rendered strip.
    expect(strip).not.toHaveTextContent("1.0.0");
    expect(strip).not.toHaveTextContent("5d");
    expect(strip).toHaveTextContent("stats-gov-sa-cpi-headline-monthly");
  });

  it("renders a degradation reason with its raw identifier", () => {
    render(
      <MetadataStrip
        dataset_id="stats-gov-sa-cpi-headline-monthly"
        source="stats-gov-sa"
        status_kind="query"
        status="limited"
        data_origin="local_snapshot"
        degradation_reason="normalization_limited"
      />,
    );

    const strip = screen.getByTestId("metadata-strip");
    expect(strip).toHaveTextContent("normalization_limited");
  });

  it("renders preview and health status families explicitly", () => {
    const { rerender } = render(
      <MetadataStrip
        dataset_id="sama-pos-weekly"
        source="sama"
        status_kind="preview"
        status="record_derivable"
        data_origin="local_snapshot"
      />,
    );

    expect(screen.getByTestId("metadata-strip")).toHaveTextContent(
      "record_derivable",
    );

    rerender(
      <MetadataStrip
        dataset_id="stats-gov-sa-cpi-headline-monthly"
        source="stats-gov-sa"
        status_kind="health"
        status="degraded"
        data_origin={null}
      />,
    );

    expect(screen.getByTestId("metadata-strip")).toHaveTextContent("degraded");
  });

  it("supports a flat embedded variant without changing metadata content", () => {
    render(
      <MetadataStrip
        dataset_id="mof-budget-balance-quarterly"
        source="mof"
        variant="flat"
        status_kind="health"
        status="healthy"
        data_origin="local_snapshot"
        freshness_status="fresh"
        schema_version="1.0.0"
      />,
    );

    const strip = screen.getByTestId("metadata-strip");
    expect(strip.className).toContain("border-0");
    expect(strip.className).toContain("bg-transparent");
    expect(strip.className).toContain("shadow-none");
    expect(strip).toHaveTextContent("mof-budget-balance-quarterly");
    expect(strip).toHaveTextContent("healthy");
    expect(strip).toHaveTextContent("local_snapshot");
  });
});
