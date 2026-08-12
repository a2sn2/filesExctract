from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from ..assets import collect_ooxml_assets
from ..detection import DetectedFileType
from ..errors import ExtractionFailedError
from ..models import (
    CanonicalDocument,
    DocumentElement,
    DocumentMetadata,
    DocumentUnit,
    ElementType,
    ExtractionWarning,
    Severity,
    SourceReference,
    UnitKind,
    UnsupportedObject,
)
from .base import BaseExtractor

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
EP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
W = f"{{{W_NS}}}"
M = f"{{{M_NS}}}"


def _safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _length(value: Any) -> int | None:
    return int(value) if value is not None else None


def _enum_name(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "name", str(value))


def _core_properties(props: Any) -> dict[str, Any]:
    names = (
        "author", "category", "comments", "content_status", "created", "identifier",
        "keywords", "language", "last_modified_by", "last_printed", "modified",
        "revision", "subject", "title", "version",
    )
    return {name: _safe_attr(props, name) for name in names if _safe_attr(props, name) not in (None, "")}


def _paragraph_numbering(paragraph: Paragraph) -> dict[str, Any] | None:
    p_pr = paragraph._p.pPr
    if p_pr is None or p_pr.numPr is None:
        return None
    num_pr = p_pr.numPr
    return {
        "num_id": int(num_pr.numId.val) if num_pr.numId is not None else None,
        "level": int(num_pr.ilvl.val) if num_pr.ilvl is not None else None,
    }


def _run_data(run: Any) -> dict[str, Any]:
    font = run.font
    inner_content: list[dict[str, Any]] = []
    for item in _safe_attr(run, "iter_inner_content", lambda: [])():
        if isinstance(item, str):
            if item:
                inner_content.append({"type": "text", "text": item})
            continue
        if bool(_safe_attr(item, "has_picture", False)):
            try:
                image = item.image
                payload = image.blob
                inner_content.append({
                    "type": "image",
                    "filename": image.filename,
                    "extension": image.ext,
                    "content_type": image.content_type,
                    "sha1": image.sha1,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "pixel_width": _safe_attr(image, "px_width"),
                    "pixel_height": _safe_attr(image, "px_height"),
                    "horizontal_dpi": _safe_attr(image, "horz_dpi"),
                    "vertical_dpi": _safe_attr(image, "vert_dpi"),
                })
            except Exception:
                inner_content.append({"type": "drawing", "picture": True})
            continue
        item_name = item.__class__.__name__
        inner_content.append({"type": "rendered_page_break" if "PageBreak" in item_name else "drawing", "class": item_name})

    return {
        "text": run.text,
        "bold": run.bold,
        "italic": run.italic,
        "underline": str(run.underline) if run.underline is not None else None,
        "style": _safe_attr(_safe_attr(run, "style"), "name"),
        "inner_content": inner_content,
        "font": {
            "name": font.name,
            "size_emu": _length(font.size),
            "bold": font.bold,
            "italic": font.italic,
            "underline": str(font.underline) if font.underline is not None else None,
            "all_caps": font.all_caps,
            "small_caps": font.small_caps,
            "strike": font.strike,
            "hidden": _safe_attr(font, "hidden"),
            "subscript": font.subscript,
            "superscript": font.superscript,
        },
    }


def _hyperlinks(paragraph: Paragraph) -> list[dict[str, Any]]:
    result = []
    for link in _safe_attr(paragraph, "hyperlinks", []) or []:
        result.append({
            "text": _safe_attr(link, "text"),
            "address": _safe_attr(link, "address"),
            "fragment": _safe_attr(link, "fragment"),
            "url": _safe_attr(link, "url"),
            "contains_page_break": bool(_safe_attr(link, "contains_page_break", False)),
        })
    return result


def _paragraph_element(paragraph: Paragraph, element_id: str, order: int, role: str = "body") -> DocumentElement:
    style_name = _safe_attr(_safe_attr(paragraph, "style"), "name") or ""
    numbering = _paragraph_numbering(paragraph)
    if style_name.lower().startswith(("heading", "title")):
        element_type = ElementType.HEADING
    elif numbering is not None or style_name.lower().startswith("list"):
        element_type = ElementType.LIST
    else:
        element_type = ElementType.PARAGRAPH
    fmt = paragraph.paragraph_format
    data = {
        "role": role,
        "style": style_name or None,
        "alignment": _enum_name(paragraph.alignment),
        "numbering": numbering,
        "contains_page_break": bool(_safe_attr(paragraph, "contains_page_break", False)),
        "rendered_page_break_count": len(_safe_attr(paragraph, "rendered_page_breaks", []) or []),
        "format": {
            "left_indent": _length(fmt.left_indent),
            "right_indent": _length(fmt.right_indent),
            "first_line_indent": _length(fmt.first_line_indent),
            "space_before": _length(fmt.space_before),
            "space_after": _length(fmt.space_after),
            "line_spacing": str(fmt.line_spacing) if fmt.line_spacing is not None else None,
            "keep_together": fmt.keep_together,
            "keep_with_next": fmt.keep_with_next,
            "page_break_before": fmt.page_break_before,
            "widow_control": fmt.widow_control,
        },
        "runs": [_run_data(run) for run in paragraph.runs],
        "hyperlinks": _hyperlinks(paragraph),
    }
    return DocumentElement(
        element_id=element_id,
        element_type=element_type,
        order=order,
        text=paragraph.text or None,
        data=data,
    )


def _cell_content(cell: Any, depth: int = 0) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for block in cell.iter_inner_content():
        if isinstance(block, Paragraph):
            content.append({
                "type": "paragraph",
                "text": block.text,
                "style": _safe_attr(_safe_attr(block, "style"), "name"),
                "hyperlinks": _hyperlinks(block),
            })
        elif isinstance(block, Table):
            content.append({"type": "table", "table": _table_data(block, depth + 1)})
    return {
        "text": cell.text,
        "vertical_alignment": _enum_name(cell.vertical_alignment),
        "content": content,
    }


def _table_data(table: Table, depth: int = 0) -> dict[str, Any]:
    rows: list[list[dict[str, Any]]] = []
    for row in table.rows:
        rows.append([_cell_content(cell, depth) for cell in row.cells])
    return {
        "style": _safe_attr(_safe_attr(table, "style"), "name"),
        "rows": rows,
        "row_count": len(table.rows),
        "column_count": len(table.columns),
        "nested_depth": depth,
    }


def _header_footer_content(container: Any) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            blocks.append({"type": "paragraph", "text": block.text, "style": _safe_attr(_safe_attr(block, "style"), "name")})
        elif isinstance(block, Table):
            blocks.append({"type": "table", "table": _table_data(block)})
    return {"is_linked_to_previous": bool(container.is_linked_to_previous), "blocks": blocks}


def _xml_text(node: ET.Element) -> str:
    return "".join((child.text or "") for child in node.iter() if child.tag in {W + "t", W + "delText", W + "tab"})


def _extended_properties(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            if "docProps/app.xml" not in archive.namelist():
                return result
            root = ET.fromstring(archive.read("docProps/app.xml"))
            for name in ("Pages", "Words", "Characters", "CharactersWithSpaces", "Paragraphs", "Lines", "Company", "Application", "AppVersion"):
                node = root.find(f"{{{EP_NS}}}{name}")
                if node is not None and node.text is not None:
                    value: Any = node.text
                    if name in {"Pages", "Words", "Characters", "CharactersWithSpaces", "Paragraphs", "Lines"}:
                        try:
                            value = int(value)
                        except ValueError:
                            pass
                    result[name] = value
    except Exception:
        pass
    return result


def _raw_special_content(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "footnotes": [],
        "endnotes": [],
        "textboxes": [],
        "revisions": [],
        "content_controls": [],
        "equations": [],
        "field_instructions": [],
    }
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            for kind, member, tag in (
                ("footnotes", "word/footnotes.xml", "footnote"),
                ("endnotes", "word/endnotes.xml", "endnote"),
            ):
                if member in names:
                    root = ET.fromstring(archive.read(member))
                    for node in root.findall(f".//{W}{tag}"):
                        note_id = node.attrib.get(W + "id")
                        if note_id in {"-1", "0"}:
                            continue
                        text = _xml_text(node).strip()
                        if text:
                            result[kind].append({"id": note_id, "text": text})
            if "word/document.xml" in names:
                root = ET.fromstring(archive.read("word/document.xml"))
                for i, node in enumerate(root.findall(f".//{W}txbxContent"), start=1):
                    text = _xml_text(node).strip()
                    if text:
                        result["textboxes"].append({"index": i, "text": text})
                for tag, status in (("ins", "inserted"), ("del", "deleted")):
                    for node in root.findall(f".//{W}{tag}"):
                        text = _xml_text(node).strip()
                        if text:
                            result["revisions"].append({
                                "status": status,
                                "text": text,
                                "author": node.attrib.get(W + "author"),
                                "date": node.attrib.get(W + "date"),
                                "id": node.attrib.get(W + "id"),
                            })
                for index, node in enumerate(root.findall(f".//{W}sdt"), start=1):
                    text = _xml_text(node).strip()
                    props = node.find(f"{W}sdtPr")
                    alias = props.find(f"{W}alias") if props is not None else None
                    tag_node = props.find(f"{W}tag") if props is not None else None
                    result["content_controls"].append({
                        "index": index,
                        "text": text,
                        "alias": alias.attrib.get(W + "val") if alias is not None else None,
                        "tag": tag_node.attrib.get(W + "val") if tag_node is not None else None,
                    })
                for index, node in enumerate(root.findall(f".//{M}oMath"), start=1):
                    text = "".join((child.text or "") for child in node.iter() if child.tag == M + "t").strip()
                    result["equations"].append({"index": index, "text": text})
                seen_fields: set[str] = set()
                for node in root.findall(f".//{W}instrText"):
                    instruction = (node.text or "").strip()
                    if instruction and instruction not in seen_fields:
                        seen_fields.add(instruction)
                        result["field_instructions"].append(instruction)
    except Exception:
        pass
    return result


class DocxExtractor(BaseExtractor):
    name = "python-docx-native"
    supported_types = frozenset({"docx", "docm"})

    def __init__(self) -> None:
        try:
            import docx
            self.version = docx.__version__
        except Exception:
            self.version = None

    def extract(self, path: Path, detected: DetectedFileType, metadata: DocumentMetadata) -> CanonicalDocument:
        try:
            document = Document(path)
        except Exception as exc:
            raise ExtractionFailedError(f"Failed to open Word document: {path.name}: {exc}") from exc

        warnings: list[ExtractionWarning] = []
        unsupported: list[UnsupportedObject] = []
        source = SourceReference(unit_index=1, unit_name="Document")

        extended = _extended_properties(path)
        metadata.properties["word"] = {
            "core_properties": _core_properties(document.core_properties),
            "extended_properties": extended,
            "stored_page_count": extended.get("Pages"),
            "section_count": len(document.sections),
            "inline_shape_count": len(document.inline_shapes),
        }
        if extended.get("Pages") is None:
            warnings.append(ExtractionWarning(
                code="docx.page_count.unavailable",
                message="No stored Word page count was found. Exact pagination requires rendering with LibreOffice/Word.",
                severity=Severity.INFO,
                source=source,
            ))

        elements: list[DocumentElement] = []
        order = 1
        body_table_index = 0
        body_para_index = 0
        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                body_para_index += 1
                elements.append(_paragraph_element(block, f"doc-paragraph-{body_para_index}", order))
                order += 1
            elif isinstance(block, Table):
                body_table_index += 1
                data = _table_data(block)
                text = "\n".join(" | ".join(cell["text"] for cell in row) for row in data["rows"])
                elements.append(DocumentElement(
                    element_id=f"doc-table-{body_table_index}",
                    element_type=ElementType.TABLE,
                    order=order,
                    text=text or None,
                    data=data,
                    source=source,
                ))
                order += 1

        section_data: list[dict[str, Any]] = []
        for index, section in enumerate(document.sections, start=1):
            entry = {
                "index": index,
                "start_type": _enum_name(section.start_type),
                "orientation": _enum_name(section.orientation),
                "page_width": _length(section.page_width),
                "page_height": _length(section.page_height),
                "top_margin": _length(section.top_margin),
                "bottom_margin": _length(section.bottom_margin),
                "left_margin": _length(section.left_margin),
                "right_margin": _length(section.right_margin),
                "header_distance": _length(section.header_distance),
                "footer_distance": _length(section.footer_distance),
                "different_first_page_header_footer": section.different_first_page_header_footer,
                "header": _header_footer_content(section.header),
                "footer": _header_footer_content(section.footer),
                "first_page_header": _header_footer_content(section.first_page_header),
                "first_page_footer": _header_footer_content(section.first_page_footer),
                "even_page_header": _header_footer_content(section.even_page_header),
                "even_page_footer": _header_footer_content(section.even_page_footer),
            }
            section_data.append(entry)
        metadata.properties["word"]["sections"] = section_data

        header_footer_count = 0
        for section_entry in section_data:
            section_index = int(section_entry["index"])
            for role in (
                "header", "footer", "first_page_header", "first_page_footer",
                "even_page_header", "even_page_footer",
            ):
                story = section_entry[role]
                if section_index > 1 and story.get("is_linked_to_previous"):
                    continue
                for block_index, block in enumerate(story.get("blocks") or [], start=1):
                    if block.get("type") == "paragraph":
                        text = block.get("text") or ""
                        if not text:
                            continue
                        elements.append(DocumentElement(
                            element_id=f"doc-section-{section_index}-{role}-{block_index}",
                            element_type=ElementType.NOTE,
                            order=order,
                            text=text,
                            data={"role": role, "section_index": section_index, "style": block.get("style")},
                            source=source,
                        ))
                    elif block.get("type") == "table":
                        table_data = block.get("table") or {}
                        text = "\n".join(
                            " | ".join(cell.get("text", "") for cell in row)
                            for row in table_data.get("rows", [])
                        )
                        elements.append(DocumentElement(
                            element_id=f"doc-section-{section_index}-{role}-table-{block_index}",
                            element_type=ElementType.TABLE,
                            order=order,
                            text=text or None,
                            data={"role": role, "section_index": section_index, "table": table_data},
                            source=source,
                        ))
                    else:
                        continue
                    header_footer_count += 1
                    order += 1

        for comment in document.comments:
            elements.append(DocumentElement(
                element_id=f"doc-comment-{comment.comment_id}",
                element_type=ElementType.NOTE,
                order=order,
                text=comment.text or None,
                data={
                    "role": "comment",
                    "comment_id": comment.comment_id,
                    "author": comment.author,
                    "initials": comment.initials,
                    "timestamp": comment.timestamp,
                },
                source=source,
            ))
            order += 1

        special = _raw_special_content(path)
        for kind in ("footnotes", "endnotes"):
            for note in special[kind]:
                elements.append(DocumentElement(
                    element_id=f"doc-{kind[:-1]}-{note['id']}",
                    element_type=ElementType.NOTE,
                    order=order,
                    text=note["text"],
                    data={"role": kind[:-1], "id": note["id"]},
                    source=source,
                ))
                order += 1
        for box in special["textboxes"]:
            elements.append(DocumentElement(
                element_id=f"doc-textbox-{box['index']}",
                element_type=ElementType.OTHER,
                order=order,
                text=box["text"],
                data={"role": "textbox"},
                source=source,
            ))
            order += 1
        for rev_index, revision in enumerate(special["revisions"], start=1):
            elements.append(DocumentElement(
                element_id=f"doc-revision-{rev_index}",
                element_type=ElementType.OTHER,
                order=order,
                text=revision["text"],
                data={"role": "tracked_change", **revision},
                source=source,
            ))
            order += 1
        for control in special["content_controls"]:
            elements.append(DocumentElement(
                element_id=f"doc-content-control-{control['index']}",
                element_type=ElementType.OTHER,
                order=order,
                text=control.get("text") or None,
                data={"role": "content_control", **control},
                source=source,
            ))
            order += 1
        for equation in special["equations"]:
            elements.append(DocumentElement(
                element_id=f"doc-equation-{equation['index']}",
                element_type=ElementType.FORMULA,
                order=order,
                text=equation.get("text") or None,
                data={"role": "office_math", **equation},
                source=source,
            ))
            order += 1
        for field_index, instruction in enumerate(special["field_instructions"], start=1):
            elements.append(DocumentElement(
                element_id=f"doc-field-{field_index}",
                element_type=ElementType.METADATA,
                order=order,
                text=instruction,
                data={"role": "field_instruction"},
                source=source,
            ))
            order += 1

        archive_names: set[str] = set()
        try:
            with zipfile.ZipFile(path) as archive:
                archive_names = set(archive.namelist())
        except Exception:
            pass
        for prefix, object_type, description in (
            ("word/charts/", "docx_chart", "Word chart parts were detected; chart data is not normalized yet."),
            ("word/diagrams/", "docx_smartart", "SmartArt/diagram parts were detected; their visual structure is not normalized yet."),
            ("word/embeddings/", "docx_embedded_object", "Embedded OLE/package objects were detected and preserved as package parts only."),
        ):
            members = sorted(name for name in archive_names if name.startswith(prefix) and not name.endswith("/"))
            if members:
                unsupported.append(UnsupportedObject(
                    object_type=object_type,
                    status="detected_not_fully_parsed",
                    description=description,
                    source=source,
                    metadata={"count": len(members), "archive_parts": members},
                ))
        try:
            with zipfile.ZipFile(path) as archive:
                if "word/document.xml" in archive_names:
                    doc_root = ET.fromstring(archive.read("word/document.xml"))
                    alt_chunks = doc_root.findall(f".//{W}altChunk")
                    if alt_chunks:
                        unsupported.append(UnsupportedObject(
                            object_type="docx_altchunk",
                            status="detected_not_fully_parsed",
                            description="External/imported altChunk content was detected; the package relationship is retained but imported content is not expanded.",
                            source=source,
                            metadata={"count": len(alt_chunks)},
                        ))
        except Exception:
            pass

        if "word/vbaProject.bin" in archive_names:
            unsupported.append(UnsupportedObject(
                object_type="vba_project", status="detected_not_parsed",
                description="A Word VBA project was detected; macro source is not interpreted.",
                source=source, metadata={"archive_part": "word/vbaProject.bin"},
            ))

        assets = collect_ooxml_assets(path, detected.document_type)
        asset_by_sha = {asset.sha256: asset.asset_id for asset in assets if asset.sha256}
        for element in elements:
            for run in element.data.get("runs", []) if isinstance(element.data, dict) else []:
                for item in run.get("inner_content", []):
                    if item.get("type") == "image" and item.get("sha256") in asset_by_sha:
                        item["asset_id"] = asset_by_sha[item["sha256"]]

        unit = DocumentUnit(
            index=1,
            kind=UnitKind.DOCUMENT,
            name="Document",
            elements=elements,
            metadata={
                "paragraph_count": body_para_index,
                "table_count": body_table_index,
                "comment_count": len(document.comments),
                "footnote_count": len(special["footnotes"]),
                "endnote_count": len(special["endnotes"]),
                "textbox_count": len(special["textboxes"]),
                "tracked_change_count": len(special["revisions"]),
                "content_control_count": len(special["content_controls"]),
                "equation_count": len(special["equations"]),
                "field_instruction_count": len(special["field_instructions"]),
                "header_footer_element_count": header_footer_count,
                "stored_page_count": extended.get("Pages"),
            },
        )
        return CanonicalDocument(metadata=metadata, units=[unit], warnings=warnings, unsupported_objects=unsupported, assets=assets)
