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

    const monthHeader = container.querySelector<HTMLTableCellElement>(
      'th[data-column-key="observation_month"]',
    );
    expect(monthHeader?.textContent).toBe("شهر الرصد");
    expect(monthHeader).toHaveAttribute("title", "observation_month");
    expect(screen.getAllByText("مؤشر أسعار المستهلك").length).toBeGreaterThan(0);
    expect(screen.queryByText("headline_cpi_all_items")).not.toBeInTheDocument();
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
    expect(link.closest("td")).toHaveAttribute(
      "data-full-text",
      "https://www.stats.gov.sa/en/w/news/155",
    );
    expect(link.closest("td")?.className).toContain("truncate-cell");

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

    const locatorCell = screen.getAllByText("/en-US/.../Currency.aspx")[0];
    expect(locatorCell).toHaveAttribute(
      "title",
      "/en-US/FinExc/Pages/Currency.aspx",
    );
    expect(locatorCell.closest("td")).toHaveAttribute(
      "data-full-text",
      "/en-US/FinExc/Pages/Currency.aspx",
    );
    expect(locatorCell.closest("td")?.className).toContain("path-cell");
    expect(locatorCell.closest("td")?.className).toContain("truncate-cell");
  });

  it("shows Arabic-only column headers while keeping the raw field name in the tooltip", () => {
    const records: CanonicalRecord[] = [
      {
        dataset_id: "sama-repo-rate",
        source: "sama",
        record_index: 1,
        fields: {
          effective_date: "2025-12-10",
          policy_rate_code: "repo_rate",
          policy_rate_name: "Official Repo Rate",
          rate_percent: 4.5,
          source_publish_date_text: "10/12/2025",
          source_rate_text: "4.25",
          source_change_points_text: "-25",
          source_table_title: "Policy Rate History",
          source_period_text: "2025-10-29 to 2025-12-10",
        },
      },
    ];

    const { container } = render(<ResultTable records={records} />);
    const effectiveDateHeader = container.querySelector<HTMLTableCellElement>(
      'th[data-column-key="effective_date"]',
    );

    expect(effectiveDateHeader?.textContent).toBe("تاريخ السريان");
    expect(effectiveDateHeader).toHaveAttribute("title", "effective_date");
    expect(effectiveDateHeader?.className).toContain("whitespace-nowrap");
    expect(effectiveDateHeader?.className).toContain("min-w-[8rem]");
    expect(screen.queryByText("effective_date")).not.toBeInTheDocument();
    expect(screen.getByText("رمز السعر")).toBeInTheDocument();
    expect(screen.getByText("اسم السعر")).toBeInTheDocument();
    expect(screen.getByText("النسبة المئوية")).toBeInTheDocument();
    expect(screen.getByText("تاريخ النشر")).toBeInTheDocument();
    expect(screen.getByText("نص السعر")).toBeInTheDocument();
    expect(screen.getByText("نقاط التغيير")).toBeInTheDocument();
    expect(screen.getByText("عنوان الجدول")).toBeInTheDocument();
    expect(screen.getByText("الفترة")).toBeInTheDocument();
    expect(screen.getByText("سعر إعادة الشراء")).toBeInTheDocument();
    expect(screen.getByText("سعر إعادة الشراء الرسمي")).toBeInTheDocument();
    expect(screen.queryByText("policy_rate_code")).not.toBeInTheDocument();
    expect(screen.queryByText("policy_rate_name")).not.toBeInTheDocument();
    expect(screen.queryByText("rate_percent")).not.toBeInTheDocument();
    expect(screen.queryByText("source_publish_date_text")).not.toBeInTheDocument();
    expect(screen.queryByText("source_rate_text")).not.toBeInTheDocument();
    expect(screen.queryByText("source_change_points_text")).not.toBeInTheDocument();
    expect(screen.queryByText("source_table_title")).not.toBeInTheDocument();
    expect(screen.queryByText("source_period_text")).not.toBeInTheDocument();
    expect(screen.queryByText("repo_rate")).not.toBeInTheDocument();

    const policyRateCodeCell = screen.getByText("سعر إعادة الشراء");
    expect(policyRateCodeCell).toHaveAttribute("title", "repo_rate");
  });

  it("hides a duplicate report link column when it repeats the source link", () => {
    const records: CanonicalRecord[] = [
      {
        dataset_id: "mof-budget-balance-quarterly",
        source: "mof",
        record_index: 1,
        fields: {
          observation_quarter: "2025-Q2",
          value_sar_bn: -34.534,
          source_url: "https://www.mof.gov.sa/en/budget/Pages/default.aspx",
          source_report_url: "https://www.mof.gov.sa/en/budget/Pages/default.aspx",
        },
      },
    ];

    const { container } = render(<ResultTable records={records} />);

    expect(
      container.querySelector('th[data-column-key="source_report_url"]'),
    ).not.toBeInTheDocument();
    expect(container.querySelector('th[data-column-key="source_url"]')).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", {
        name: "https://www.mof.gov.sa/en/budget/Pages/default.aspx",
      }),
    ).toHaveLength(1);
  });
});
