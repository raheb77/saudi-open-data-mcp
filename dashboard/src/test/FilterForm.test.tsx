import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FilterForm } from "../components/FilterForm";

describe("FilterForm", () => {
  it("forces LTR direction for key and value inputs", () => {
    render(
      <FilterForm
        filters={[{ key: "observation_quarter", value: "2025-Q4" }]}
        onFiltersChange={vi.fn()}
        limit="100"
        onLimitChange={vi.fn()}
        onApply={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("اسم الحقل")).toHaveAttribute("dir", "ltr");
    expect(screen.getByLabelText("القيمة")).toHaveAttribute("dir", "ltr");
  });
});
