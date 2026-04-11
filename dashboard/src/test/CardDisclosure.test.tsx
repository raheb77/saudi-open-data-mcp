import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CardDisclosure } from "../components/CardDisclosure";

describe("CardDisclosure", () => {
  it("keeps secondary details collapsed until the user reveals them", () => {
    render(
      <CardDisclosure
        summary="التفاصيل التقنية"
        items={[
          "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        ]}
        technical
        tone="warn"
      />,
    );

    expect(
      screen.queryByText(
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
      ),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /التفاصيل التقنية/i }));

    expect(
      screen.getByText(
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
      ),
    ).toBeInTheDocument();
  });
});
