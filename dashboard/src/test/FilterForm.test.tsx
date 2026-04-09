import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { FilterForm, type FilterRow } from "../components/FilterForm";

function FilterFormHarness() {
  const [filters, setFilters] = useState<FilterRow[]>([]);
  const [limit, setLimit] = useState("100");

  return (
    <FilterForm
      filters={filters}
      onFiltersChange={setFilters}
      limit={limit}
      onLimitChange={setLimit}
      onApply={vi.fn()}
      onReset={() => {
        setFilters([]);
        setLimit("100");
      }}
    />
  );
}

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

  it("supports multiple controlled filter rows", () => {
    render(<FilterFormHarness />);

    fireEvent.click(screen.getByRole("button", { name: /\+ أضف مرشحًا/ }));
    fireEvent.click(screen.getByRole("button", { name: /\+ أضف مرشحًا/ }));

    expect(screen.getAllByLabelText("اسم الحقل")).toHaveLength(2);
    expect(screen.getAllByLabelText("القيمة")).toHaveLength(2);
  });

  it("deletes one row while preserving the remaining canonical field inputs", () => {
    render(<FilterFormHarness />);

    fireEvent.click(screen.getByRole("button", { name: /\+ أضف مرشحًا/ }));
    fireEvent.click(screen.getByRole("button", { name: /\+ أضف مرشحًا/ }));

    const keyInputs = screen.getAllByLabelText("اسم الحقل");
    const valueInputs = screen.getAllByLabelText("القيمة");

    fireEvent.change(keyInputs[0], {
      target: { value: "observation_quarter" },
    });
    fireEvent.change(valueInputs[0], { target: { value: "2025-Q4" } });
    fireEvent.change(screen.getAllByLabelText("اسم الحقل")[1], {
      target: { value: "headline_budget_balance" },
    });
    fireEvent.change(screen.getAllByLabelText("القيمة")[1], {
      target: { value: "-100.5" },
    });

    fireEvent.click(screen.getByRole("button", { name: "احذف 1" }));

    expect(screen.getAllByLabelText("اسم الحقل")).toHaveLength(1);
    expect(screen.getByLabelText("اسم الحقل")).toHaveValue(
      "headline_budget_balance",
    );
    expect(screen.getByLabelText("القيمة")).toHaveValue("-100.5");
    expect(screen.getByLabelText("اسم الحقل")).toHaveAttribute("dir", "ltr");
    expect(screen.getByLabelText("القيمة")).toHaveAttribute("dir", "ltr");
  });

  it("adds row-specific accessible delete labels for screen-reader clarity", () => {
    render(<FilterFormHarness />);

    fireEvent.click(screen.getByRole("button", { name: /\+ أضف مرشحًا/ }));
    fireEvent.click(screen.getByRole("button", { name: /\+ أضف مرشحًا/ }));

    expect(
      screen.getByRole("button", { name: "احذف 1" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "احذف 2" }),
    ).toBeInTheDocument();
  });
});
