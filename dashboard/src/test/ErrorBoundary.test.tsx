import { render, screen } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "../components/ErrorBoundary";

function BrokenComponent(): JSX.Element {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

  afterEach(() => {
    consoleSpy.mockClear();
  });

  it("renders an Arabic fallback instead of a blank screen", () => {
    render(
      <ErrorBoundary>
        <BrokenComponent />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();
    expect(screen.getByText("تعذّر عرض الصفحة")).toBeInTheDocument();
    expect(
      screen.getByText(
        "حدث خطأ غير متوقع أثناء بناء هذا العرض. بقيت الواجهة في وضع آمن بدل شاشة فارغة.",
      ),
    ).toBeInTheDocument();
  });
});
