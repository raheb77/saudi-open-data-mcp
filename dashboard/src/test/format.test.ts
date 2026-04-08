import { describe, expect, it } from "vitest";
import { formatAge } from "../lib/format";

describe("formatAge", () => {
  it("renders Latin numerals with Arabic time-unit wording", () => {
    expect(formatAge(2 * 86_400 + 3 * 3_600)).toBe("2 يوم 3 ساعة");
    expect(formatAge(2 * 3_600 + 5 * 60)).toBe("2 ساعة 5 دقيقة");
    expect(formatAge(5 * 60)).toBe("5 دقيقة");
  });

  it("returns an em dash when no age is available", () => {
    expect(formatAge(null)).toBe("—");
  });
});
