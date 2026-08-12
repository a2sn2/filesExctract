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
    headers_footers = meta.get("headers_footers") or {}
    visible_stories = []
    for role, story in headers_footers.items():
        values = [story.get("left"), story.get("center"), story.get("right")] if isinstance(story, dict) else []
        text = " | ".join(str(value) for value in values if value)
        if text:
            visible_stories.append((role, text))
    if visible_stories:
        lines.extend(["### Headers / footers", ""] )
        for role, text in visible_stories:
            lines.append(f"- **{role.replace('_', ' ').title()}**: {text}")
        lines.append("")

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

    table_elements = [e for e in unit.elements if e.element_type == ElementType.TABLE]
    if table_elements:
        lines.extend(["### Excel table definitions", ""] )
        for element in table_elements:
            data = element.data or {}
            lines.append(f"- `{data.get('display_name') or data.get('name') or element.element_id}`: `{data.get('ref') or ''}`")
        lines.append("")

    image_elements = [e for e in unit.elements if e.element_type == ElementType.IMAGE]
    if image_elements:
        lines.extend(["### Images", ""] )
        for element in image_elements:
            image = element.data.get("image", {})
            anchor = image.get("from") or {}
            asset_id = image.get("asset_id") or "unlinked-asset"
            lines.append(
                f"- `{asset_id}` anchored near row {anchor.get('row_zero_based', '?')}, "
                f"column {anchor.get('column_zero_based', '?')}"
            )
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
            if unit.kind == UnitKind.SLIDE:
                inherited = []
                for source_name in ("layout_visible_text", "master_visible_text"):
                    for item in unit.metadata.get(source_name, []) or []:
                        text = item.get("text") or item.get("accessibility", {}).get("description")
                        if text and text not in inherited:
                            inherited.append(text)
                if inherited:
                    lines.extend(["### Inherited layout/master content", ""] )
                    lines.extend([f"- {text}" for text in inherited])
                    lines.append("")
            for element in sorted(unit.elements, key=lambda x: x.order):
                _render_element(element, lines)
    if document.metadata.document_type == "pdf":
        form_fields = document.metadata.properties.get("pdf", {}).get("form_fields", {}) or {}
        if form_fields:
            lines.extend(["## PDF form fields", ""] )
            for name, field in form_fields.items():
                lines.append(f"- **{name}**: {_escape(field.get('value'))} (`{field.get('field_type') or ''}`)")
            lines.append("")

    if document.metadata.document_type in {"docx", "docm", "doc"}:
        pagination = document.metadata.properties.get("word", {}).get("pagination", {}) or {}
        rendered_pages = pagination.get("rendered_pages") or []
        if rendered_pages:
            lines.extend(["## Rendered Word pagination reference", ""] )
            lines.append(
                "Native Word elements above preserve document structure; the following renderer-derived text "
                "preserves page boundaries."
            )
            lines.append("")
            for page in rendered_pages:
                lines.extend([f"### Rendered page {page.get('page_number')}", "", page.get("text") or "[No extractable text]", ""])

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
