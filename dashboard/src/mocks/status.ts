import { parseObservabilitySummary } from "../lib/runtimeValidation";
import type { ObservabilitySummary } from "../types/core";
import { MOCK_OBSERVABILITY } from "./observability";

export function getObservabilitySummary(): ObservabilitySummary {
  return parseObservabilitySummary(MOCK_OBSERVABILITY);
}
