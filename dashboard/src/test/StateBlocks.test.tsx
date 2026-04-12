import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  DegradedState,
  ErrorState,
  LimitedState,
  LoadingState,
} from "../components/StateBlocks";

describe("StateBlocks", () => {
  it("announces loading as a polite status", () => {
    render(<LoadingState />);

    expect(screen.getByTestId("state-loading")).toHaveAttribute("role", "status");
    expect(screen.getByTestId("state-loading")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("announces hard failures and degradation with alert semantics", () => {
    const { rerender } = render(
      <ErrorState
        stage="query_page"
        errorType="DashboardApiError"
        message="تعذّر تنفيذ الاستعلام الحي."
      />,
    );

    expect(screen.getByTestId("state-failed")).toHaveAttribute("role", "alert");
    expect(screen.getByTestId("state-failed")).toHaveAttribute(
      "aria-live",
      "assertive",
    );

    rerender(
      <DegradedState
        title="تعذّر تحميل سياق الثقة المساند"
        body="نتيجة الاستعلام الأساسية ما زالت معروضة."
        testId="state-degraded-custom"
      />,
    );

    expect(screen.getByTestId("state-degraded-custom")).toHaveAttribute(
      "role",
      "alert",
    );
    expect(screen.getByTestId("state-degraded-custom")).toHaveAttribute(
      "aria-live",
      "assertive",
    );
  });

  it("keeps limited states human-readable while preserving technical details", () => {
    render(
      <LimitedState
        limitations={[
          "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        ]}
      />,
    );

    expect(screen.getByText("المعنى العملي")).toBeInTheDocument();
    expect(
      screen.getByText(
        "عمليًا: صفحة المصدر موجودة، لكن بنيتها الحالية لا تسمح بعد باستخراج صفوف معيارية قابلة للمقارنة.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
      ),
    ).toBeInTheDocument();
  });

  it("explains older exchange-rate HTML snapshots as a refresh-needed limited case", () => {
    render(
      <LimitedState
        limitations={[
          "sama_exchange_rates_current_html_requires_supported_daily_quote_table",
        ]}
      />,
    );

    expect(
      screen.getByText(
        "عمليًا: هذه اللقطة تبدو من تنسيق أقدم لصفحة أسعار الصرف. حدّث اللقطة المحلية لقراءة الصفوف الحالية القابلة للاستعلام.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "sama_exchange_rates_current_html_requires_supported_daily_quote_table",
      ),
    ).toBeInTheDocument();
  });
});
