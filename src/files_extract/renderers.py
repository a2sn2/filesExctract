from __future__ import annotations

import json
from typing import Any

from .models import CanonicalDocument, DocumentElement, ElementType, UnitKind


def render_json(document: CanonicalDocument, *, indent: int = 2) -> str:
    return json.dumps(document.to_dict(), ensure_ascii=False, indent=indent, sort_keys=False)


def _escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _render_grid(grid: list[list[Any]], lines: list[str]) -> None:
    if not grid:
        return
    rows: list[list[str]] = []
    width = 0
    for row in grid:
        vals: list[str] = []
        for cell in row:
            vals.append(_escape(cell.get("text")) if isinstance(cell, dict) else _escape(cell))
        width = max(width, len(vals))
        rows.append(vals)
    if width == 0:
        return
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("|" + "|".join(["---"] * width) + "|")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")


def _render_element(element: DocumentElement, lines: list[str]) -> None:
    if element.element_type == ElementType.METADATA:
        return
    text = element.text or ""
    if element.element_type == ElementType.HEADING:
        lines.extend([f"### {text or '[Heading]'}", ""])
        return
    if element.element_type == ElementType.LIST:
        if text:
            for part in text.splitlines():
                lines.append(f"- {part}")
            lines.append("")
        return
    if element.element_type == ElementType.TABLE:
        table = element.data.get("table") if isinstance(element.data, dict) else None
        if isinstance(table, dict):
            _render_grid(table.get("grid") or table.get("rows") or [], lines)
        elif text:
            lines.extend([text, ""])
        return
    if element.element_type == ElementType.NOTE:
        if text:
            lines.extend([f"> **Note:** {text.replace(chr(10), ' ')}", ""])
        return
    if element.element_type == ElementType.IMAGE:
        info = element.data.get("image", {}) if isinstance(element.data, dict) else {}
        lines.extend([f"[Image: {info.get('filename') or element.element_id}]", ""])
        return
    if element.element_type == ElementType.LINK:
        uri = element.data.get("uri") if isinstance(element.data, dict) else None
        if uri:
            lines.extend([f"[{text or uri}]({uri})", ""])
        return
    if element.element_type in {ElementType.CODE, ElementType.FORMULA} and text:
        lines.extend(["```text", text, "```", ""])
        return
    if text:
        lines.extend([text, ""])


def _render_sheet(unit: Any, lines: list[str]) -> None:
    meta = unit.metadata or {}
    lines.extend([
        f"- State: `{meta.get('state', '')}`",
        f"- Used range: {meta.get('max_row', 0)} row(s) × {meta.get('max_column', 0)} column(s)",
        "",
    ])
    cells = [e for e in unit.elements if e.element_type == ElementType.CELL]
    if cells:
        lines.extend(["### Cells", "", "| Cell | Value | Formula | Cached value | Comment | Hyperlink |", "|---|---|---|---|---|---|"])
        for e in sorted(cells, key=lambda x: x.order):
            d = e.data; comment = d.get("comment") or {}; link = d.get("hyperlink") or {}
            lines.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
                _escape(d.get("coordinate")), _escape(d.get("value")), _escape(d.get("formula")),
                _escape(d.get("cached_value")), _escape(comment.get("text")),
                _escape(link.get("target") or link.get("location")),
            ))
        lines.append("")


def render_markdown(document: CanonicalDocument) -> str:
    lines: list[str] = [f"# {document.metadata.filename}", ""]
    lines.extend([
        f"- Type: `{document.metadata.document_type}`",
        f"- Units: {document.unit_count}",
        f"- Elements: {document.element_count}",
        f"- Assets: {len(document.assets)}",
        f"- SHA-256: `{document.metadata.sha256}`",
        f"- Extractor: `{document.metadata.extractor}`",
        "",
    ])
    for unit in document.units:
        if unit.kind == UnitKind.SHEET:
            title = f"## Sheet {unit.index}: {unit.name or ''}".rstrip()
        elif unit.kind == UnitKind.PAGE:
            title = f"## Page {unit.index}"
        elif unit.kind == UnitKind.SLIDE:
            title = f"## Slide {unit.index}: {unit.name or ''}".rstrip()
        else:
            title = f"## Document content: {unit.name or ''}".rstrip()
        lines.extend([title, ""])
        if unit.kind == UnitKind.SHEET:
            _render_sheet(unit, lines)
        else:
            for element in sorted(unit.elements, key=lambda x: x.order):
                _render_element(element, lines)
    if document.assets:
        lines.extend(["## Assets", ""])
        for asset in document.assets:
            lines.append(f"- `{asset.asset_id}` → `{asset.output_path or asset.original_name or ''}` ({asset.media_type or asset.asset_type})")
        lines.append("")
    if document.warnings:
        lines.extend(["## Extraction warnings", ""])
        for warning in document.warnings:
            lines.append(f"- `{warning.code}`: {warning.message}")
        lines.append("")
    if document.unsupported_objects:
        lines.extend(["## Unsupported or partially parsed objects", ""])
        for item in document.unsupported_objects:
            lines.append(f"- `{item.object_type}` / `{item.status}`: {item.description or ''}".rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
