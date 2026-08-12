from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from ..detection import DetectedFileType
from ..errors import ExtractionFailedError
from ..models import (
    AssetReference,
    BoundingBox,
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


def _safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _pdf_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _pdf_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_pdf_safe(v) for v in value]
    try:
        return str(value)
    except Exception:
        return None


def _outline_data(reader: PdfReader) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def walk(items: Any, level: int = 0) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            title = _safe_attr(item, "title")
            try:
                page_number = reader.get_destination_page_number(item)
                page_number = page_number + 1 if page_number is not None else None
            except Exception:
                page_number = None
            result.append({"title": title or str(item), "level": level, "page_number": page_number})

    try:
        walk(reader.outline)
    except Exception:
        pass
    return result


def _annotation_data(page: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    try:
        annotations = page.get("/Annots", []) or []
        for ref in annotations:
            try:
                obj = ref.get_object()
            except Exception:
                obj = ref
            action = obj.get("/A") if hasattr(obj, "get") else None
            if action is not None and hasattr(action, "get"):
                try:
                    action = action.get_object()
                except Exception:
                    pass
            result.append({
                "subtype": str(obj.get("/Subtype")) if hasattr(obj, "get") and obj.get("/Subtype") is not None else None,
                "rect": _pdf_safe(obj.get("/Rect")) if hasattr(obj, "get") else None,
                "contents": str(obj.get("/Contents")) if hasattr(obj, "get") and obj.get("/Contents") is not None else None,
                "uri": str(action.get("/URI")) if hasattr(action, "get") and action.get("/URI") is not None else None,
                "destination": _pdf_safe(obj.get("/Dest")) if hasattr(obj, "get") else None,
            })
    except Exception:
        pass
    return result


def _field_data(reader: PdfReader) -> dict[str, Any]:
    try:
        fields = reader.get_fields() or {}
    except Exception:
        return {}
    result: dict[str, Any] = {}
    for name, field in fields.items():
        result[str(name)] = {
            "field_type": _pdf_safe(_safe_attr(field, "field_type")) or _pdf_safe(field.get("/FT") if hasattr(field, "get") else None),
            "value": _pdf_safe(_safe_attr(field, "value")) or _pdf_safe(field.get("/V") if hasattr(field, "get") else None),
            "default_value": _pdf_safe(field.get("/DV") if hasattr(field, "get") else None),
            "alternate_name": _pdf_safe(field.get("/TU") if hasattr(field, "get") else None),
            "mapping_name": _pdf_safe(field.get("/TM") if hasattr(field, "get") else None),
        }
    return result


def _bbox_from_docling(prov: Any) -> BoundingBox | None:
    bbox = _safe_attr(prov, "bbox")
    if bbox is None:
        return None
    try:
        origin = _safe_attr(_safe_attr(bbox, "coord_origin"), "value") or str(_safe_attr(bbox, "coord_origin", ""))
        return BoundingBox(float(bbox.l), float(bbox.t), float(bbox.r), float(bbox.b), f"docling:{origin}")
    except Exception:
        return None


def _docling_table_data(item: Any) -> dict[str, Any]:
    data = _safe_attr(item, "data")
    if data is None:
        return {}
    grid_out: list[list[dict[str, Any]]] = []
    try:
        for row in data.grid:
            row_out = []
            for cell in row:
                row_out.append({
                    "text": _safe_attr(cell, "text", ""),
                    "row_span": _safe_attr(cell, "row_span", 1),
                    "col_span": _safe_attr(cell, "col_span", 1),
                    "row_header": bool(_safe_attr(cell, "row_header", False)),
                    "column_header": bool(_safe_attr(cell, "column_header", False)),
                    "row_section": bool(_safe_attr(cell, "row_section", False)),
                })
            grid_out.append(row_out)
    except Exception:
        pass
    return {
        "num_rows": _safe_attr(data, "num_rows"),
        "num_cols": _safe_attr(data, "num_cols"),
        "grid": grid_out,
    }


def _docling_element_type(label: str) -> ElementType:
    label = label.lower()
    if label in {"title", "section_header", "field_heading"}:
        return ElementType.HEADING
    if "list" in label:
        return ElementType.LIST
    if label == "table":
        return ElementType.TABLE
    if label in {"picture", "figure"}:
        return ElementType.IMAGE
    if label == "formula":
        return ElementType.FORMULA
    if label == "code":
        return ElementType.CODE
    return ElementType.PARAGRAPH


class PdfExtractor(BaseExtractor):
    name = "docling+pypdf"
    supported_types = frozenset({"pdf"})

    def __init__(self) -> None:
        try:
            import pypdf
            pypdf_version = pypdf.__version__
        except Exception:
            pypdf_version = None
        try:
            import docling
            docling_version = _safe_attr(docling, "__version__")
            self._docling_available = True
        except Exception:
            docling_version = None
            self._docling_available = False
        self.version = f"docling={docling_version or 'unavailable'};pypdf={pypdf_version or 'unknown'}"

    def extract(self, path: Path, detected: DetectedFileType, metadata: DocumentMetadata) -> CanonicalDocument:
        reader = self._open_reader(path)
        if self._docling_available:
            try:
                document = self._extract_docling(path, metadata)
                metadata.extractor = "docling+pypdf"
                metadata.properties.setdefault("pdf", {})["primary_backend"] = "docling"
            except Exception as exc:
                document = self._extract_pypdf(reader, metadata)
                document.warnings.append(ExtractionWarning(
                    code="pdf.docling.failed",
                    message="Docling was available but PDF conversion failed; pypdf fallback was used.",
                    details={"error": str(exc)},
                ))
        else:
            document = self._extract_pypdf(reader, metadata)
            document.warnings.append(ExtractionWarning(
                code="pdf.docling.unavailable",
                message="Docling is not installed; PDF extraction used the pypdf fallback without semantic table/layout analysis or OCR.",
                severity=Severity.INFO,
            ))
        self._augment_low_level(reader, document)
        return document

    @staticmethod
    def _open_reader(path: Path) -> PdfReader:
        try:
            reader = PdfReader(path, strict=False)
            if reader.is_encrypted:
                try:
                    result = reader.decrypt("")
                except Exception:
                    result = 0
                if not result:
                    raise ExtractionFailedError("PDF is encrypted and cannot be opened without a password.")
            return reader
        except ExtractionFailedError:
            raise
        except Exception as exc:
            raise ExtractionFailedError(f"Failed to open PDF: {path.name}: {exc}") from exc

    def _extract_pypdf(self, reader: PdfReader, metadata: DocumentMetadata) -> CanonicalDocument:
        units: list[DocumentUnit] = []
        warnings: list[ExtractionWarning] = []
        total_text = 0
        for page_index, page in enumerate(reader.pages, start=1):
            source = SourceReference(unit_index=page_index, page_number=page_index)
            try:
                text = page.extract_text(extraction_mode="layout") or ""
            except Exception as exc:
                try:
                    text = page.extract_text() or ""
                except Exception as fallback_exc:
                    text = ""
                    warnings.append(ExtractionWarning(
                        code="pdf.text.failed",
                        message="Text extraction failed for a PDF page.",
                        source=source,
                        details={"layout_error": str(exc), "fallback_error": str(fallback_exc)},
                    ))
            total_text += len(text.strip())
            box = page.mediabox
            elements = []
            if text:
                elements.append(DocumentElement(
                    element_id=f"page-{page_index}-text-1",
                    element_type=ElementType.PARAGRAPH,
                    order=1,
                    text=text,
                    data={"backend": "pypdf", "extraction_mode": "layout"},
                    source=source,
                ))
            units.append(DocumentUnit(
                index=page_index,
                kind=UnitKind.PAGE,
                name=f"Page {page_index}",
                elements=elements,
                metadata={
                    "width_points": float(box.width),
                    "height_points": float(box.height),
                    "rotation": int(page.rotation or 0),
                },
            ))
        metadata.properties.setdefault("pdf", {})["primary_backend"] = "pypdf"
        if units and total_text < max(10, len(units) * 3):
            warnings.append(ExtractionWarning(
                code="pdf.possible_scanned_document",
                message="Very little text was extracted. The PDF may be scanned/image-only; install the full Docling/OCR dependencies for OCR extraction.",
            ))
        return CanonicalDocument(metadata=metadata, units=units, warnings=warnings)

    def _extract_docling(self, path: Path, metadata: DocumentMetadata) -> CanonicalDocument:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(path)
        doc = result.document
        page_count = int(doc.num_pages())
        units = [DocumentUnit(index=i, kind=UnitKind.PAGE, name=f"Page {i}") for i in range(1, page_count + 1)]
        by_page = {unit.index: unit for unit in units}
        order_by_page = {i: 1 for i in by_page}
        unpaged: list[DocumentElement] = []
        unpaged_order = 1

        for item, level in doc.iterate_items(traverse_pictures=True):
            label_obj = _safe_attr(item, "label")
            label = _safe_attr(label_obj, "value") or str(label_obj or item.__class__.__name__)
            prov_list = _safe_attr(item, "prov", []) or []
            prov = prov_list[0] if prov_list else None
            page_no = int(_safe_attr(prov, "page_no", 0) or 0)
            source = SourceReference(
                unit_index=page_no or None,
                page_number=page_no or None,
                bbox=_bbox_from_docling(prov),
            )
            element_type = _docling_element_type(label)
            text = _safe_attr(item, "text")
            data: dict[str, Any] = {
                "backend": "docling",
                "label": label,
                "hierarchy_level": level,
                "self_ref": _safe_attr(item, "self_ref"),
                "content_layer": str(_safe_attr(item, "content_layer")) if _safe_attr(item, "content_layer") is not None else None,
            }
            if element_type == ElementType.TABLE:
                data["table"] = _docling_table_data(item)
                if not text:
                    grid = data["table"].get("grid") or []
                    text = "\n".join(" | ".join(str(cell.get("text", "")) for cell in row) for row in grid)

            if page_no in by_page:
                order = order_by_page[page_no]
                element_id = f"page-{page_no}-docling-{order}"
                by_page[page_no].elements.append(DocumentElement(element_id, element_type, order, text or None, data=data, source=source))
                order_by_page[page_no] += 1
            else:
                unpaged.append(DocumentElement(f"docling-unpaged-{unpaged_order}", element_type, unpaged_order, text or None, data=data, source=source))
                unpaged_order += 1

        if unpaged:
            units.append(DocumentUnit(index=page_count + 1, kind=UnitKind.DOCUMENT, name="Unpaged content", elements=unpaged, metadata={"synthetic": True}))
        metadata.properties.setdefault("pdf", {}).update({
            "docling_page_count": page_count,
            "docling_schema_version": _safe_attr(doc, "version"),
        })
        return CanonicalDocument(metadata=metadata, units=units)

    def _augment_low_level(self, reader: PdfReader, document: CanonicalDocument) -> None:
        pdf_meta = document.metadata.properties.setdefault("pdf", {})
        try:
            raw_metadata = reader.metadata
            pdf_meta["metadata"] = {str(k): _pdf_safe(v) for k, v in (raw_metadata or {}).items()}
        except Exception:
            pdf_meta["metadata"] = {}
        pdf_meta.update({
            "page_count": len(reader.pages),
            "page_layout": _safe_attr(reader, "page_layout"),
            "page_mode": _safe_attr(reader, "page_mode"),
            "outline": _outline_data(reader),
            "form_fields": _field_data(reader),
        })

        unit_by_page = {unit.index: unit for unit in document.units if unit.kind == UnitKind.PAGE}
        for page_index, page in enumerate(reader.pages, start=1):
            unit = unit_by_page.get(page_index)
            if unit is None:
                continue
            annotations = _annotation_data(page)
            unit.metadata["annotations"] = annotations
            order = max((e.order for e in unit.elements), default=0) + 1
            for annotation_index, annotation in enumerate(annotations, start=1):
                if annotation.get("uri") or annotation.get("destination"):
                    unit.elements.append(DocumentElement(
                        f"page-{page_index}-link-{annotation_index}", ElementType.LINK, order,
                        annotation.get("contents"), data=annotation,
                        source=SourceReference(unit_index=page_index, page_number=page_index),
                    ))
                    order += 1
            try:
                for image_index, image in enumerate(page.images):
                    payload = image.data
                    media_type, _ = mimetypes.guess_type(image.name)
                    document.assets.append(AssetReference(
                        asset_id=f"pdf-page-{page_index}-image-{image_index + 1}",
                        asset_type="pdf_image",
                        original_name=image.name,
                        output_path=f"assets/page-{page_index}-{image_index + 1}-{Path(image.name).name}",
                        media_type=media_type,
                        sha256=hashlib.sha256(payload).hexdigest(),
                        size_bytes=len(payload),
                        source=SourceReference(unit_index=page_index, page_number=page_index),
                        metadata={"pdf_page": page_index, "pdf_image_index": image_index},
                    ))
            except Exception as exc:
                document.warnings.append(ExtractionWarning(
                    code="pdf.images.partial",
                    message="One or more PDF images could not be enumerated.",
                    source=SourceReference(unit_index=page_index, page_number=page_index),
                    details={"error": str(exc)},
                ))

        try:
            attachments = reader.attachments
            for name, content_list in attachments.items():
                for index, payload in enumerate(content_list):
                    media_type, _ = mimetypes.guess_type(str(name))
                    suffix = f"-{index + 1}" if len(content_list) > 1 else ""
                    out_name = Path(str(name)).name or f"attachment-{index + 1}.bin"
                    document.assets.append(AssetReference(
                        asset_id=f"pdf-attachment-{len(document.assets) + 1}",
                        asset_type="pdf_attachment",
                        original_name=str(name),
                        output_path=f"assets/attachment{suffix}-{out_name}",
                        media_type=media_type,
                        sha256=hashlib.sha256(payload).hexdigest(),
                        size_bytes=len(payload),
                        metadata={"pdf_attachment_name": str(name), "pdf_attachment_index": index},
                    ))
        except Exception as exc:
            document.warnings.append(ExtractionWarning(
                code="pdf.attachments.partial",
                message="PDF attachments could not be fully enumerated.",
                details={"error": str(exc)},
            ))
