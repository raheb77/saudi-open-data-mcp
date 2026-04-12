import { fireEvent, render, screen } from "@testing-library/react";
import { ResultTable } from "../components/ResultTable";
import { ar } from "../i18n/ar";
import type { CanonicalRecord } from "../types/core";

describe("ResultTable", () => {
  it("reorders analyst-facing CPI columns ahead of verbose provenance text", () => {
    const records: CanonicalRecord[] = [
      {
        dataset_id: "stats-gov-sa-cpi-headline-monthly",
        source: "stats-gov-sa",
        record_index: 0,
        fields: {
          observation_month: "2025-12",
          inflation_series_code: "headline_cpi_all_items",
          inflation_series_name: "Headline CPI",
          release_date: "2026-01-15",
          yoy_rate_percent: 2.1,
          mom_rate_percent: 0.1,
          source_locator: "/en/news?q=inflation&delta=20&start=0",
          source_url: "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
          source_release_url: "https://www.stats.gov.sa/en/w/news/155",
          source_release_title: "GASTAT: Saudi Arabia's inflation rate records 2.1% in December 2025",
          source_release_date_text: "15-01-2026",
          source_summary_text:
            "The annual inflation rate in Saudi Arabia reached 2.1% in December 2025, compared to December 2024, while it recorded a monthly increase of 0.1% compared to November 2025.",
        },
      },
    ];

    const { container } = render(<ResultTable records={records} />);
    const order = [
      ...container.querySelectorAll<HTMLTableCellElement>("th[data-column-key]"),
    ].map((element) => element.dataset.columnKey);

    expect(order).toEqual([
      "observation_month",
      "yoy_rate_percent",
      "mom_rate_percent",
      "inflation_series_name",
      "inflation_series_code",
      "release_date",
      "source_release_title",
      "source_release_url",
      "source_url",
      "source_release_date_text",
      "source_locator",
      "source_summary_text",
    ]);
  });

  it("renders verbose source text as expandable content and keeps provenance links clickable", () => {
    const summaryText =
      "The annual inflation rate in Saudi Arabia reached 2.1% in December 2025, compared to December 2024, while it recorded a monthly increase of 0.1% compared to November 2025.";

    render(
      <ResultTable
        records={[
          {
            dataset_id: "stats-gov-sa-cpi-headline-monthly",
            source: "stats-gov-sa",
            record_index: 0,
            fields: {
              observation_month: "2025-12",
              inflation_series_code: "headline_cpi_all_items",
              inflation_series_name: "Headline CPI",
              yoy_rate_percent: 2.1,
              mom_rate_percent: 0.1,
              release_date: "2026-01-15",
              source_release_url: "https://www.stats.gov.sa/en/w/news/155",
              source_summary_text: summaryText,
            },
          },
        ]}
      />,
    );

    const link = screen.getByRole("link", {
      name: "https://www.stats.gov.sa/en/w/news/155",
    });
    expect(link).toHaveAttribute(
      "href",
      "https://www.stats.gov.sa/en/w/news/155",
    );
    expect(link.className).not.toContain("ring-1");

    const toggle = screen.getByRole("button", { name: ar.query.table.showMore });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText(summaryText).className).toContain("cell-clamp-2");

    fireEvent.click(toggle);

    expect(screen.getByRole("button", { name: ar.query.table.showLess })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByText(summaryText)).toBeInTheDocument();
  });

  it("presents exchange-rate rows in analyst-first order with labeled market context and de-emphasized provenance", () => {
    const records: CanonicalRecord[] = [
      {
        dataset_id: "sama-exchange-rates-current",
        source: "sama",
        record_index: 0,
        fields: {
          as_of_date: "2026-04-12",
          closing_rate_sar: 3.75,
          currency_code: "USD",
          currency_name: "US DOLLAR",
          quote_currency_code: "SAR",
          quote_currency_name: "Saudi Riyal",
          source_url: "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
          source_last_updated_date_text: "12/04/2026",
          source_currency_text: "US DOLLAR",
          source_page_number: 1,
          source_locator: "/en-US/FinExc/Pages/Currency.aspx",
        },
      },
      {
        dataset_id: "sama-exchange-rates-current",
        source: "sama",
        record_index: 1,
        fields: {
          as_of_date: "2026-04-12",
          closing_rate_sar: 4.39818,
          currency_code: "EUR",
          currency_name: "EURO",
          quote_currency_code: "SAR",
          quote_currency_name: "Saudi Riyal",
          source_url: "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
          source_last_updated_date_text: "12/04/2026",
          source_currency_text: "EURO",
          source_page_number: 2,
          source_page_url:
            "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx?PageIndex=2",
          source_locator: "/en-US/FinExc/Pages/Currency.aspx",
        },
      },
    ];

    const { container } = render(<ResultTable records={records} />);
    const order = [
      ...container.querySelectorAll<HTMLTableCellElement>("th[data-column-key]"),
    ].map((element) => element.dataset.columnKey);

    expect(order).toEqual([
      "as_of_date",
      "closing_rate_sar",
      "currency_name",
      "currency_code",
      "quote_currency_name",
      "quote_currency_code",
      "source_url",
      "source_last_updated_date_text",
      "source_currency_text",
      "source_locator",
      "source_page_number",
      "source_page_url",
    ]);

    expect(screen.getByText("تاريخ السعر")).toBeInTheDocument();
    expect(screen.getByText("سعر الإغلاق (ريال)")).toBeInTheDocument();
    expect(screen.getByText("عملة التسعير")).toBeInTheDocument();

    const measureCell = screen.getByText("3.75");
    expect(measureCell.className).toContain("bg-ink-100");

    const contextHeader = container.querySelector<HTMLTableCellElement>(
      'th[data-column-key="quote_currency_name"]',
    );
    expect(contextHeader?.className).toContain("text-[0.72rem]");

    const pageLink = screen.getByRole("link", {
      name:
        "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx?PageIndex=2",
    });
    expect(pageLink.className).toContain("text-[0.72rem]");
  });
});
