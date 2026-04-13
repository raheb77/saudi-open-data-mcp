"""Explicit institutional artifact renderers over governed query results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from saudi_open_data_mcp.tools.query import DatasetQueryResult


class ExportArtifactFormat(StrEnum):
    """Supported institutional artifact formats for governed query results."""

    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"


@dataclass(frozen=True)
class QueryExportContext:
    """Metadata carried into artifact renderers for one governed query result."""

    dataset_id: str
    source: str | None
    exported_at: str
    query_status: str
    coverage_status: str
    freshness_status: str | None
    data_origin: str | None
    matched_record_count: int
    total_records_before_filter: int | None
    limit: int | None
    applied_filters_json: str
    degradation_reason: str | None
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    notes: tuple[str, ...]


@lru_cache(maxsize=1)
def _load_export_semantics() -> dict[str, Any]:
    """Load the canonical governed export semantics shared across surfaces."""

    semantics_path = Path(__file__).with_name("export_semantics.json")
    return json.loads(semantics_path.read_text(encoding="utf-8"))


def render_query_result_excel_artifact(
    result: DatasetQueryResult,
    *,
    freshness_status: str | None,
    exported_at: datetime | None = None,
) -> bytes:
    """Render one query result as an Excel-compatible XML workbook."""

    context = _build_query_export_context(
        result,
        freshness_status=freshness_status,
        exported_at=exported_at,
    )
    worksheets = [_render_metadata_worksheet(context)]
    if result.matched_records:
        worksheets.append(_render_records_worksheet(result))
    if context.notes:
        worksheets.append(_render_notes_worksheet(context.notes))

    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<?mso-application progid="Excel.Sheet"?>\n'
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:x="urn:schemas-microsoft-com:office:excel" '
        'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n'
        "  <Styles>\n"
        '    <Style ss:ID="header"><Font ss:Bold="1"/></Style>\n'
        '    <Style ss:ID="wrap"><Alignment ss:Vertical="Top" ss:WrapText="1"/></Style>\n'
        "  </Styles>\n"
        f"{''.join(worksheets)}"
        "</Workbook>\n"
    )
    return workbook.encode("utf-8")


def render_query_result_pdf_artifact(
    result: DatasetQueryResult,
    *,
    freshness_status: str | None,
    exported_at: datetime | None = None,
) -> bytes:
    """Render one query result as a clean, metadata-first institutional PDF."""

    context = _build_query_export_context(
        result,
        freshness_status=freshness_status,
        exported_at=exported_at,
    )
    lines = _build_pdf_lines(context, result=result)
    return _render_pdf_document(lines)


def _build_query_export_context(
    result: DatasetQueryResult,
    *,
    freshness_status: str | None,
    exported_at: datetime | None,
) -> QueryExportContext:
    """Build the shared export context from the current governed query result."""

    export_time = (exported_at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    return QueryExportContext(
        dataset_id=result.dataset_id,
        source=result.source,
        exported_at=export_time.isoformat().replace("+00:00", "Z"),
        query_status=result.status.value,
        coverage_status=result.coverage_status.value,
        freshness_status=freshness_status,
        data_origin=(result.data_origin.value if result.data_origin is not None else None),
        matched_record_count=len(result.matched_records),
        total_records_before_filter=result.total_records_before_filter,
        limit=result.limit,
        applied_filters_json=json.dumps(
            result.applied_filters,
            ensure_ascii=False,
            sort_keys=True,
        ),
        degradation_reason=(
            result.degradation_reason.value
            if result.degradation_reason is not None
            else None
        ),
        failure_stage=(
            result.failure_stage.value if result.failure_stage is not None else None
        ),
        failure_type=(result.failure.error_type if result.failure is not None else None),
        failure_message=(result.failure.message if result.failure is not None else None),
        notes=result.limitations,
    )


def _render_metadata_worksheet(context: QueryExportContext) -> str:
    """Render the workbook metadata worksheet."""

    rows = [
        (field_name, _metadata_field_value(context, field_name))
        for field_name in _load_export_semantics()["metadata_field_order"]
    ]
    return _render_worksheet(
        "Metadata",
        [
            ("Field", "Value"),
            *rows,
        ],
    )


def _render_notes_worksheet(notes: tuple[str, ...]) -> str:
    """Render the workbook notes worksheet for limitations or other caveats."""

    return _render_worksheet(
        "Notes",
        [
            ("Index", "Note"),
            *[(index, note) for index, note in enumerate(notes, start=1)],
        ],
    )


def _render_records_worksheet(result: DatasetQueryResult) -> str:
    """Render the workbook records worksheet from canonical query matches."""

    columns = _collect_record_columns(result)
    rows: list[tuple[Any, ...]] = [("record_index", *columns)]
    for record in result.matched_records:
        rows.append(
            (record.record_index, *(record.fields.get(column) for column in columns))
        )
    return _render_worksheet("Records", rows)


def _render_worksheet(name: str, rows: list[tuple[Any, ...]]) -> str:
    """Render one SpreadsheetML worksheet."""

    rendered_rows = []
    for row_index, row in enumerate(rows):
        rendered_cells = []
        for cell in row:
            style_id = ' ss:StyleID="header"' if row_index == 0 else ""
            cell_type, cell_value = _spreadsheet_cell(cell)
            rendered_cells.append(
                f'        <Cell{style_id}><Data ss:Type="{cell_type}">{cell_value}</Data></Cell>'
            )
        rendered_rows.append("      <Row>\n" + "\n".join(rendered_cells) + "\n      </Row>")

    return (
        f'  <Worksheet ss:Name="{_escape_xml(name)}">\n'
        "    <Table>\n"
        f"{''.join(f'{row}\n' for row in rendered_rows)}"
        "    </Table>\n"
        "  </Worksheet>\n"
    )


def _spreadsheet_cell(value: Any) -> tuple[str, str]:
    """Render one SpreadsheetML cell payload."""

    if isinstance(value, bool):
        return ("Boolean", "1" if value else "0")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return ("Number", str(value))
    return ("String", _escape_xml(_display_value(value)))


def _collect_record_columns(result: DatasetQueryResult) -> tuple[str, ...]:
    """Collect canonical record field names in first-seen order."""

    columns: list[str] = []
    seen: set[str] = set()
    for record in result.matched_records:
        for key in record.fields:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return tuple(columns)


def _build_pdf_lines(
    context: QueryExportContext,
    *,
    result: DatasetQueryResult,
) -> list[str]:
    """Build line-oriented PDF content for one governed query result."""

    semantics = _load_export_semantics()
    pdf = semantics["pdf"]
    lines = [
        pdf["document_title"],
        "=" * 32,
        "",
        pdf["dataset_source_section"],
        f'{pdf["labels"]["dataset_id"]}: {context.dataset_id}',
        f'{pdf["labels"]["source"]}: {_source_display_label(context.source)}',
        "",
        pdf["result_context_section"],
        f'{pdf["labels"]["exported_at"]}: {context.exported_at}',
        f'{pdf["labels"]["query_status"]}: {context.query_status}',
        f'{pdf["labels"]["coverage_status"]}: {context.coverage_status}',
        f'{pdf["labels"]["freshness_status"]}: {_display_value(context.freshness_status)}',
        f'{pdf["labels"]["data_origin"]}: {_display_value(context.data_origin)}',
        f'{pdf["labels"]["matched_record_count"]}: {context.matched_record_count}',
        (
            f'{pdf["labels"]["total_records_before_filter"]}: '
            f'{_display_value(context.total_records_before_filter)}'
        ),
        f'{pdf["labels"]["limit"]}: {_display_value(context.limit)}',
        (
            f'{pdf["labels"]["applied_filters_json"]}: '
            f'{_applied_filters_display(context.applied_filters_json)}'
        ),
    ]

    if context.degradation_reason is not None:
        lines.extend(
            [
                "",
                pdf["degraded_context_section"],
                f'{pdf["labels"]["degradation_reason"]}: {context.degradation_reason}',
            ]
        )

    if any(
        item is not None
        for item in (context.failure_stage, context.failure_type, context.failure_message)
    ):
        lines.append("")
        lines.append(pdf["failure_details_section"])
        if context.failure_stage is not None:
            lines.append(f'{pdf["labels"]["failure_stage"]}: {context.failure_stage}')
        if context.failure_type is not None:
            lines.append(f'{pdf["labels"]["failure_type"]}: {context.failure_type}')
        if context.failure_message is not None:
            lines.append(f'{pdf["labels"]["failure_message"]}: {context.failure_message}')

    if context.notes:
        lines.extend(["", pdf["notes_section"]])
        lines.extend(f"- {note}" for note in context.notes)

    if result.matched_records:
        columns = _collect_record_columns(result)
        total_records = len(result.matched_records)
        lines.extend(["", f'{pdf["records_label"]} ({total_records})'])
        for display_index, record in enumerate(result.matched_records, start=1):
            lines.append(f"{display_index}. Record {display_index} of {total_records}")
            for column in columns:
                if column in record.fields:
                    lines.append(
                        "   - "
                        f"{_record_field_label(column)}: "
                        f"{_display_value(record.fields.get(column))}"
                    )
            lines.append("")

    return lines


def _render_pdf_document(lines: list[str]) -> bytes:
    """Render line-oriented content into a minimal multi-page PDF."""

    wrapped_lines: list[str] = []
    for line in lines:
        wrapped_lines.extend(_wrap_line(line, width=92))

    page_line_count = 54
    pages = [
        wrapped_lines[index : index + page_line_count]
        for index in range(0, len(wrapped_lines), page_line_count)
    ] or [[]]

    objects: list[bytes] = []
    page_object_numbers: list[int] = []
    next_object_number = 4

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [] /Count 0 >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    for page_lines in pages:
        page_object_number = next_object_number
        content_object_number = next_object_number + 1
        next_object_number += 2
        page_object_numbers.append(page_object_number)
        content_stream = _render_pdf_page_stream(page_lines)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 3 0 R >> >> "
                f"/Contents {content_object_number} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            (
                f"<< /Length {len(content_stream)} >>\nstream\n".encode("ascii")
                + content_stream
                + b"\nendstream"
            )
        )

    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_numbers)} >>".encode(
        "ascii"
    )

    pdf_parts = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in pdf_parts))
        pdf_parts.append(f"{object_number} 0 obj\n".encode("ascii"))
        pdf_parts.append(body)
        pdf_parts.append(b"\nendobj\n")

    xref_offset = sum(len(part) for part in pdf_parts)
    pdf_parts.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf_parts.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf_parts.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf_parts.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return b"".join(pdf_parts)


def _render_pdf_page_stream(lines: list[str]) -> bytes:
    """Render one PDF content stream with Courier text lines."""

    safe_lines = [_escape_pdf_text(_ascii_only(line)) for line in lines]
    content = ["BT", "/F1 10 Tf", "14 TL", "36 806 Td"]
    for index, line in enumerate(safe_lines):
        if index == 0:
            content.append(f"({line}) Tj")
        else:
            content.append("T*")
            content.append(f"({line}) Tj")
    content.append("ET")
    return "\n".join(content).encode("ascii")


def _wrap_line(line: str, *, width: int) -> list[str]:
    """Wrap one text line for narrow PDF page widths."""

    if line == "":
        return [""]

    remaining = _ascii_only(line)
    wrapped: list[str] = []
    while len(remaining) > width:
        split_at = remaining.rfind(" ", 0, width + 1)
        if split_at <= 0:
            split_at = width
        wrapped.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    wrapped.append(remaining)
    return wrapped


def _display_value(value: Any) -> str:
    """Render one scalar value honestly for export metadata or PDF text."""

    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _applied_filters_display(applied_filters_json: str) -> str:
    """Render applied filters more cleanly when the query used no filters."""

    if applied_filters_json == "{}":
        return _load_export_semantics()["applied_filters_empty_label"]
    return applied_filters_json


def _source_display_label(source: str | None) -> str:
    """Render an institutional source label without losing source identity."""

    labels = _load_export_semantics()["source_display_labels"]
    if source in labels:
        return labels[source]
    return _display_value(source)


def _record_field_label(field_name: str) -> str:
    """Render a readable field label while preserving the governed field identity."""

    field_labels = _load_export_semantics()["record_field_labels"]
    if field_name in field_labels:
        return field_labels[field_name]
    return f"{field_name.replace('_', ' ').title()} [{field_name}]"


def _metadata_field_value(context: QueryExportContext, field_name: str) -> Any:
    """Return one canonical metadata field value from the shared export context."""

    if field_name == "dataset_id":
        return context.dataset_id
    if field_name == "source":
        return _source_display_label(context.source)
    if field_name == "exported_at":
        return context.exported_at
    if field_name == "query_status":
        return context.query_status
    if field_name == "coverage_status":
        return context.coverage_status
    if field_name == "freshness_status":
        return context.freshness_status
    if field_name == "data_origin":
        return context.data_origin
    if field_name == "matched_record_count":
        return context.matched_record_count
    if field_name == "total_records_before_filter":
        return context.total_records_before_filter
    if field_name == "limit":
        return context.limit
    if field_name == "applied_filters_json":
        return _applied_filters_display(context.applied_filters_json)
    if field_name == "degradation_reason":
        return context.degradation_reason
    if field_name == "failure_stage":
        return context.failure_stage
    if field_name == "failure_type":
        return context.failure_type
    if field_name == "failure_message":
        return context.failure_message
    raise ValueError(f"unknown export metadata field: {field_name}")


def _escape_xml(value: str) -> str:
    """Escape a string for XML text content."""

    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _ascii_only(value: str) -> str:
    """Reduce PDF text to Latin-safe content for standard PDF base fonts."""

    return value.encode("ascii", "replace").decode("ascii")


def _escape_pdf_text(value: str) -> str:
    """Escape literal PDF text syntax characters."""

    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
