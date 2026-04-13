import type {
  CanonicalRecord,
  DatasetQueryResult,
  SnapshotFreshnessStatus,
} from "../types/core";
import exportSemantics from "../../../src/saudi_open_data_mcp/tools/export_semantics.json";

// Client-side artifact builder for dashboard convenience only.
// The backend/CLI remains the canonical institutional export surface.
// This module mirrors the current governed query-result semantics without
// inventing extra fields or alternate meanings.

export type ExportArtifactFormat = "json" | "excel" | "pdf";

interface BuildQueryExportArtifactArgs {
  format: ExportArtifactFormat;
  result: DatasetQueryResult;
  freshnessStatus: SnapshotFreshnessStatus | null;
  exportedAt?: string;
}

export interface QueryExportArtifact {
  filename: string;
  mimeType: string;
  bytes: Uint8Array;
}

interface QueryExportContext {
  datasetId: string;
  source: string | null;
  exportedAt: string;
  queryStatus: string;
  coverageStatus: string;
  freshnessStatus: string | null;
  dataOrigin: string | null;
  matchedRecordCount: number;
  totalRecordsBeforeFilter: number | null;
  limit: number | null;
  appliedFiltersJson: string;
  degradationReason: string | null;
  failureStage: string | null;
  failureType: string | null;
  failureMessage: string | null;
  notes: string[];
}

const ENCODER = new TextEncoder();
const EXPORT_SEMANTICS = exportSemantics as ExportSemantics;

type ExportMetadataField =
  | "dataset_id"
  | "source"
  | "exported_at"
  | "query_status"
  | "coverage_status"
  | "freshness_status"
  | "data_origin"
  | "matched_record_count"
  | "total_records_before_filter"
  | "limit"
  | "applied_filters_json"
  | "degradation_reason"
  | "failure_stage"
  | "failure_type"
  | "failure_message";

interface ExportSemantics {
  applied_filters_empty_label: string;
  metadata_field_order: ExportMetadataField[];
  pdf: {
    document_title: string;
    dataset_source_section: string;
    result_context_section: string;
    degraded_context_section: string;
    failure_details_section: string;
    notes_section: string;
    records_label: string;
    labels: Record<ExportMetadataField, string>;
  };
  source_display_labels: Record<string, string>;
  record_field_labels: Record<string, string>;
}

export function buildQueryExportArtifact({
  format,
  result,
  freshnessStatus,
  exportedAt,
}: BuildQueryExportArtifactArgs): QueryExportArtifact {
  const context = buildQueryExportContext(result, freshnessStatus, exportedAt);
  const timestamp = filenameTimestamp(context.exportedAt);

  if (format === "json") {
    return {
      filename: `${result.dataset_id}.query_export.${timestamp}.json`,
      mimeType: "application/json",
      bytes: ENCODER.encode(JSON.stringify(result, null, 2)),
    };
  }

  if (format === "excel") {
    return {
      filename: `${result.dataset_id}.query_export.${timestamp}.xml`,
      mimeType: "application/vnd.ms-excel",
      bytes: ENCODER.encode(renderExcelWorkbook(result, context)),
    };
  }

  return {
    filename: `${result.dataset_id}.query_export.${timestamp}.pdf`,
    mimeType: "application/pdf",
    bytes: renderPdfDocument(result, context),
  };
}

export function downloadQueryExportArtifact(
  args: BuildQueryExportArtifactArgs,
): void {
  const artifact = buildQueryExportArtifact(args);
  const blobBytes = new Uint8Array(artifact.bytes.byteLength);
  blobBytes.set(artifact.bytes);
  const blob = new Blob([blobBytes.buffer], { type: artifact.mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = artifact.filename;
  link.click();
  URL.revokeObjectURL(url);
}

function buildQueryExportContext(
  result: DatasetQueryResult,
  freshnessStatus: SnapshotFreshnessStatus | null,
  exportedAt?: string,
): QueryExportContext {
  return {
    datasetId: result.dataset_id,
    source: result.source,
    exportedAt: canonicalizeIsoTimestamp(exportedAt ?? new Date().toISOString()),
    queryStatus: result.status,
    coverageStatus: result.coverage_status,
    freshnessStatus,
    dataOrigin: result.data_origin,
    matchedRecordCount: result.matched_records.length,
    totalRecordsBeforeFilter: result.total_records_before_filter,
    limit: result.limit,
    appliedFiltersJson: canonicalizeAppliedFiltersJson(result.applied_filters),
    degradationReason: result.degradation_reason,
    failureStage: result.failure_stage,
    failureType: result.failure?.error_type ?? null,
    failureMessage: result.failure?.message ?? null,
    notes: [...result.limitations],
  };
}

function renderExcelWorkbook(
  result: DatasetQueryResult,
  context: QueryExportContext,
): string {
  const worksheets = [renderMetadataWorksheet(context)];
  if (result.matched_records.length > 0) {
    worksheets.push(renderRecordsWorksheet(result.matched_records));
  }
  if (context.notes.length > 0) {
    worksheets.push(renderNotesWorksheet(context.notes));
  }

  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<?mso-application progid="Excel.Sheet"?>\n' +
    '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" ' +
    'xmlns:o="urn:schemas-microsoft-com:office:office" ' +
    'xmlns:x="urn:schemas-microsoft-com:office:excel" ' +
    'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n' +
    "  <Styles>\n" +
    '    <Style ss:ID="header"><Font ss:Bold="1"/></Style>\n' +
    '    <Style ss:ID="wrap"><Alignment ss:Vertical="Top" ss:WrapText="1"/></Style>\n' +
    "  </Styles>\n" +
    worksheets.join("") +
    "</Workbook>\n"
  );
}

function renderMetadataWorksheet(context: QueryExportContext): string {
  const rows: Array<[string, string | number | null]> =
    EXPORT_SEMANTICS.metadata_field_order.map((fieldName) => [
      fieldName,
      metadataFieldValue(context, fieldName),
    ]);
  return renderWorksheet("Metadata", [["Field", "Value"], ...rows]);
}

function renderNotesWorksheet(notes: string[]): string {
  return renderWorksheet("Notes", [
    ["Index", "Note"],
    ...notes.map((note, index) => [index + 1, note]),
  ]);
}

function renderRecordsWorksheet(records: CanonicalRecord[]): string {
  const columns = collectRecordColumns(records);
  return renderWorksheet("Records", [
    ["record_index", ...columns],
    ...records.map((record) => [
      record.record_index,
      ...columns.map((column) => record.fields[column] ?? null),
    ]),
  ]);
}

function renderWorksheet(
  name: string,
  rows: Array<Array<string | number | boolean | null>>,
): string {
  const renderedRows = rows
    .map((row, rowIndex) => {
      const renderedCells = row
        .map((cell) => {
          const style = rowIndex === 0 ? ' ss:StyleID="header"' : "";
          const [cellType, cellValue] = renderSpreadsheetCell(cell);
          return `        <Cell${style}><Data ss:Type="${cellType}">${cellValue}</Data></Cell>`;
        })
        .join("\n");
      return `      <Row>\n${renderedCells}\n      </Row>`;
    })
    .join("\n");

  return (
    `  <Worksheet ss:Name="${escapeXml(name)}">\n` +
    "    <Table>\n" +
    `${renderedRows}\n` +
    "    </Table>\n" +
    "  </Worksheet>\n"
  );
}

function renderSpreadsheetCell(
  value: string | number | boolean | null,
): [string, string] {
  if (typeof value === "boolean") {
    return ["Boolean", value ? "1" : "0"];
  }
  if (typeof value === "number") {
    return ["Number", String(value)];
  }
  return ["String", escapeXml(displayValue(value))];
}

function collectRecordColumns(records: CanonicalRecord[]): string[] {
  const seen = new Set<string>();
  const columns: string[] = [];
  for (const record of records) {
    for (const key of Object.keys(record.fields)) {
      if (!seen.has(key)) {
        seen.add(key);
        columns.push(key);
      }
    }
  }
  return columns;
}

function renderPdfDocument(
  result: DatasetQueryResult,
  context: QueryExportContext,
): Uint8Array {
  const wrappedLines = buildPdfLines(result, context).flatMap((line) =>
    wrapLine(line, 92),
  );
  const pageLineCount = 54;
  const pages =
    wrappedLines.length > 0
      ? chunk(wrappedLines, pageLineCount)
      : ([[]] as string[][]);

  const objects: Uint8Array[] = [];
  const pageObjectNumbers: number[] = [];
  let nextObjectNumber = 4;

  objects.push(ENCODER.encode("<< /Type /Catalog /Pages 2 0 R >>"));
  objects.push(ENCODER.encode("<< /Type /Pages /Kids [] /Count 0 >>"));
  objects.push(
    ENCODER.encode("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"),
  );

  for (const pageLines of pages) {
    const pageObjectNumber = nextObjectNumber;
    const contentObjectNumber = nextObjectNumber + 1;
    nextObjectNumber += 2;
    pageObjectNumbers.push(pageObjectNumber);

    const contentStream = renderPdfPageStream(pageLines);
    objects.push(
      ENCODER.encode(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentObjectNumber} 0 R >>`,
      ),
    );
    objects.push(
      concatBytes(
        ENCODER.encode(`<< /Length ${contentStream.length} >>\nstream\n`),
        contentStream,
        ENCODER.encode("\nendstream"),
      ),
    );
  }

  objects[1] = ENCODER.encode(
    `<< /Type /Pages /Kids [${pageObjectNumbers
      .map((value) => `${value} 0 R`)
      .join(" ")}] /Count ${pageObjectNumbers.length} >>`,
  );

  const parts: Uint8Array[] = [ENCODER.encode("%PDF-1.4\n%âãÏÓ\n")];
  const offsets = [0];

  objects.forEach((body, index) => {
    offsets.push(totalLength(parts));
    parts.push(ENCODER.encode(`${index + 1} 0 obj\n`));
    parts.push(body);
    parts.push(ENCODER.encode("\nendobj\n"));
  });

  const xrefOffset = totalLength(parts);
  parts.push(ENCODER.encode(`xref\n0 ${objects.length + 1}\n`));
  parts.push(ENCODER.encode("0000000000 65535 f \n"));
  offsets.slice(1).forEach((offset) => {
    parts.push(ENCODER.encode(`${offset.toString().padStart(10, "0")} 00000 n \n`));
  });
  parts.push(
    ENCODER.encode(
      `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`,
    ),
  );

  return concatBytes(...parts);
}

function buildPdfLines(
  result: DatasetQueryResult,
  context: QueryExportContext,
): string[] {
  const pdf = EXPORT_SEMANTICS.pdf;
  const lines = [
    pdf.document_title,
    "=".repeat(32),
    "",
    pdf.dataset_source_section,
    `${pdf.labels.dataset_id}: ${context.datasetId}`,
    `${pdf.labels.source}: ${sourceDisplayLabel(context.source)}`,
    "",
    pdf.result_context_section,
    `${pdf.labels.exported_at}: ${context.exportedAt}`,
    `${pdf.labels.query_status}: ${context.queryStatus}`,
    `${pdf.labels.coverage_status}: ${context.coverageStatus}`,
    `${pdf.labels.freshness_status}: ${displayValue(context.freshnessStatus)}`,
    `${pdf.labels.data_origin}: ${displayValue(context.dataOrigin)}`,
    `${pdf.labels.matched_record_count}: ${context.matchedRecordCount}`,
    `${pdf.labels.total_records_before_filter}: ${displayValue(context.totalRecordsBeforeFilter)}`,
    `${pdf.labels.limit}: ${displayValue(context.limit)}`,
    `${pdf.labels.applied_filters_json}: ${appliedFiltersDisplay(context.appliedFiltersJson)}`,
  ];

  if (context.degradationReason) {
    lines.push(
      "",
      pdf.degraded_context_section,
      `${pdf.labels.degradation_reason}: ${context.degradationReason}`,
    );
  }
  if (context.failureStage || context.failureType || context.failureMessage) {
    lines.push("", pdf.failure_details_section);
    if (context.failureStage) {
      lines.push(`${pdf.labels.failure_stage}: ${context.failureStage}`);
    }
    if (context.failureType) {
      lines.push(`${pdf.labels.failure_type}: ${context.failureType}`);
    }
    if (context.failureMessage) {
      lines.push(`${pdf.labels.failure_message}: ${context.failureMessage}`);
    }
  }
  if (context.notes.length > 0) {
    lines.push("", pdf.notes_section);
    context.notes.forEach((note) => {
      lines.push(`- ${note}`);
    });
  }
  if (result.matched_records.length > 0) {
    const columns = collectRecordColumns(result.matched_records);
    const totalRecords = result.matched_records.length;
    lines.push("", `${pdf.records_label} (${totalRecords})`);
    result.matched_records.forEach((record, index) => {
      lines.push(`${index + 1}. Record ${index + 1} of ${totalRecords}`);
      columns.forEach((column) => {
        if (column in record.fields) {
          lines.push(
            `   - ${recordFieldLabel(column)}: ${displayValue(record.fields[column] ?? null)}`,
          );
        }
      });
      lines.push("");
    });
  }
  return lines;
}

function renderPdfPageStream(lines: string[]): Uint8Array {
  const safeLines = lines.map((line) => escapePdfText(asciiOnly(line)));
  const content: string[] = ["BT", "/F1 10 Tf", "14 TL", "36 806 Td"];
  safeLines.forEach((line, index) => {
    if (index === 0) {
      content.push(`(${line}) Tj`);
      return;
    }
    content.push("T*");
    content.push(`(${line}) Tj`);
  });
  content.push("ET");
  return ENCODER.encode(content.join("\n"));
}

function wrapLine(line: string, width: number): string[] {
  if (line === "") return [""];

  let remaining = asciiOnly(line);
  const wrapped: string[] = [];
  while (remaining.length > width) {
    let splitAt = remaining.lastIndexOf(" ", width);
    if (splitAt <= 0) splitAt = width;
    wrapped.push(remaining.slice(0, splitAt).trimEnd());
    remaining = remaining.slice(splitAt).trimStart();
  }
  wrapped.push(remaining);
  return wrapped;
}

function chunk<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

function concatBytes(...parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const merged = new Uint8Array(total);
  let offset = 0;
  parts.forEach((part) => {
    merged.set(part, offset);
    offset += part.length;
  });
  return merged;
}

function totalLength(parts: Uint8Array[]): number {
  return parts.reduce((sum, part) => sum + part.length, 0);
}

function displayValue(value: string | number | boolean | null): string {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function appliedFiltersDisplay(appliedFiltersJson: string): string {
  if (appliedFiltersJson === "{}") {
    return EXPORT_SEMANTICS.applied_filters_empty_label;
  }
  return appliedFiltersJson;
}

function canonicalizeAppliedFiltersJson(
  filters: DatasetQueryResult["applied_filters"],
): string {
  const orderedEntries = Object.entries(filters).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  return JSON.stringify(Object.fromEntries(orderedEntries));
}

function sourceDisplayLabel(source: string | null): string {
  if (source && source in EXPORT_SEMANTICS.source_display_labels) {
    return EXPORT_SEMANTICS.source_display_labels[source];
  }
  return displayValue(source);
}

function recordFieldLabel(fieldName: string): string {
  const fieldLabels = EXPORT_SEMANTICS.record_field_labels;
  return (
    fieldLabels[fieldName] ??
    `${fieldName.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())} [${fieldName}]`
  );
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function asciiOnly(value: string): string {
  return value.replace(/[^\x20-\x7E]/g, "?");
}

function escapePdfText(value: string): string {
  return value
    .replaceAll("\\", "\\\\")
    .replaceAll("(", "\\(")
    .replaceAll(")", "\\)");
}

function filenameTimestamp(isoTimestamp: string): string {
  return isoTimestamp.replace(/[:.-]/g, "").replace("+0000", "Z").replace("+00:00", "Z");
}

function canonicalizeIsoTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function metadataFieldValue(
  context: QueryExportContext,
  fieldName: ExportMetadataField,
): string | number | null {
  switch (fieldName) {
    case "dataset_id":
      return context.datasetId;
    case "source":
      return sourceDisplayLabel(context.source);
    case "exported_at":
      return context.exportedAt;
    case "query_status":
      return context.queryStatus;
    case "coverage_status":
      return context.coverageStatus;
    case "freshness_status":
      return context.freshnessStatus;
    case "data_origin":
      return context.dataOrigin;
    case "matched_record_count":
      return context.matchedRecordCount;
    case "total_records_before_filter":
      return context.totalRecordsBeforeFilter;
    case "limit":
      return context.limit;
    case "applied_filters_json":
      return appliedFiltersDisplay(context.appliedFiltersJson);
    case "degradation_reason":
      return context.degradationReason;
    case "failure_stage":
      return context.failureStage;
    case "failure_type":
      return context.failureType;
    case "failure_message":
      return context.failureMessage;
  }
}
