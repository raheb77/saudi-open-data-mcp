import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  DegradedState,
  ErrorState,
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
});
