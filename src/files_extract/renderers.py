from __future__ import annotations

import json
from typing import Any

from .models import CanonicalDocument, ElementType, UnitKind


def render_json(document: CanonicalDocument, *, indent: int = 2) -> str:
    return json.dumps(document.to_dict(), ensure_ascii=False, indent=indent, sort_keys=False)


def _markdown_escape(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def render_markdown(document: CanonicalDocument) -> str:
    lines: list[str] = [f"# {document.metadata.filename}", ""]
    lines.extend(
        [
            f"- Type: `{document.metadata.document_type}`",
            f"- Units: {document.unit_count}",
            f"- SHA-256: `{document.metadata.sha256}`",
            f"- Extractor: `{document.metadata.extractor}`",
            "",
        ]
    )

    for unit in document.units:
        if unit.kind == UnitKind.SHEET:
            lines.append(f"## Sheet {unit.index}: {unit.name or ''}".rstrip())
        elif unit.kind == UnitKind.PAGE:
            lines.append(f"## Page {unit.index}")
        elif unit.kind == UnitKind.SLIDE:
            lines.append(f"## Slide {unit.index}: {unit.name or ''}".rstrip())
        else:
            lines.append(f"## Unit {unit.index}: {unit.name or ''}".rstrip())
        lines.append("")

        if unit.kind == UnitKind.SHEET:
            _render_sheet(unit, lines)
        else:
            for element in sorted(unit.elements, key=lambda item: item.order):
                if element.element_type == ElementType.METADATA:
                    continue
                if element.text:
                    lines.append(element.text)
                    lines.append("")

    if document.warnings:
        lines.extend(["## Extraction warnings", ""])
        for warning in document.warnings:
            lines.append(f"- `{warning.code}`: {warning.message}")
        lines.append("")

    if document.unsupported_objects:
        lines.extend(["## Detected unsupported/partial objects", ""])
        for item in document.unsupported_objects:
            lines.append(f"- `{item.object_type}` / `{item.status}`: {item.description or ''}".rstrip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_sheet(unit: Any, lines: list[str]) -> None:
    metadata = unit.metadata or {}
    lines.extend(
        [
            f"- State: `{metadata.get('state', '')}`",
            f"- Used range: {metadata.get('max_row', 0)} row(s) × {metadata.get('max_column', 0)} column(s)",
        ]
    )
    merged_ranges = metadata.get("merged_ranges") or []
    if merged_ranges:
        lines.append("- Merged ranges: " + ", ".join(f"`{item}`" for item in merged_ranges))
    hidden_rows = metadata.get("hidden_rows") or []
    hidden_columns = metadata.get("hidden_columns") or []
    if hidden_rows:
        lines.append("- Hidden rows: " + ", ".join(map(str, hidden_rows)))
    if hidden_columns:
        lines.append("- Hidden columns: " + ", ".join(map(str, hidden_columns)))
    lines.append("")

    cells = [element for element in unit.elements if element.element_type == ElementType.CELL]
    if cells:
        lines.extend(
            [
                "### Cells",
                "",
                "| Cell | Value | Formula | Cached value | Comment | Hyperlink |",
                "|---|---|---|---|---|---|",
            ]
        )
        for element in sorted(cells, key=lambda item: item.order):
            data = element.data
            comment = data.get("comment") or {}
            hyperlink = data.get("hyperlink") or {}
            lines.append(
                "| {cell} | {value} | {formula} | {cached} | {comment} | {link} |".format(
                    cell=_markdown_escape(data.get("coordinate")),
                    value=_markdown_escape(data.get("value")),
                    formula=_markdown_escape(data.get("formula")),
                    cached=_markdown_escape(data.get("cached_value")),
                    comment=_markdown_escape(comment.get("text")),
                    link=_markdown_escape(hyperlink.get("target") or hyperlink.get("location")),
                )
            )
        lines.append("")

    tables = metadata.get("tables") or []
    if tables:
        lines.extend(["### Excel tables", ""])
        for table in tables:
            lines.append(
                f"- `{table.get('display_name') or table.get('name')}`: `{table.get('ref')}`"
            )
        lines.append("")
