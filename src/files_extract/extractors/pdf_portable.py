from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..models import (
    CanonicalDocument,
    DocumentElement,
    DocumentMetadata,
    DocumentUnit,
    ElementType,
    SourceReference,
    UnitKind,
)
from .pdf import (
    PdfExtractor as _BasePdfExtractor,
    _bbox_from_docling,
    _docling_element_type,
    _docling_table_data,
    _safe_attr,
)


class PdfExtractor(_BasePdfExtractor):
    """PDF extractor configured for portable desktop execution.

    Docling's current Transformers layout engine may use ``torch.compile`` on
    Windows. That can invoke the MSVC compiler at runtime, which is not a valid
    dependency for an end-user desktop product. Docling exposes an ONNX Runtime
    layout engine for the same Heron layout model, so FilesExtract selects it
    explicitly and pins execution to CPU. This keeps the semantic Docling path
    local/offline without requiring Visual Studio Build Tools on the target PC.
    """

    def _extract_docling(self, path: Path, metadata: DocumentMetadata) -> CanonicalDocument:
        from docling.datamodel.accelerator_options import (
            AcceleratorDevice,
            AcceleratorOptions,
        )
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.object_detection_engine_options import (
            OnnxRuntimeObjectDetectionEngineOptions,
        )
        from docling.datamodel.pipeline_options import (
            LayoutObjectDetectionOptions,
            PdfPipelineOptions,
            TesseractCliOcrOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        artifacts_path = os.environ.get("DOCLING_ARTIFACTS_PATH")
        pipeline_options = PdfPipelineOptions(
            artifacts_path=artifacts_path or None,
        )
        pipeline_options.document_timeout = 180
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True
        pipeline_options.accelerator_options = AcceleratorOptions(
            device=AcceleratorDevice.CPU,
        )

        layout_options = LayoutObjectDetectionOptions.from_preset(
            "layout_heron_default"
        )
        layout_options.engine_options = OnnxRuntimeObjectDetectionEngineOptions()
        pipeline_options.layout_options = layout_options

        tesseract_languages = self._tesseract_languages()
        selected_languages: list[str] = []
        if tesseract_languages:
            if "ara" in tesseract_languages:
                selected_languages.append("ara")
            if "eng" in tesseract_languages:
                selected_languages.append("eng")
            if selected_languages:
                pipeline_options.ocr_options = TesseractCliOcrOptions(
                    lang=selected_languages
                )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                ),
            }
        )
        result = converter.convert(path)
        doc = result.document

        pdf_properties = metadata.properties.setdefault("pdf", {})
        pdf_properties["ocr"] = {
            "enabled": True,
            "engine": "tesseract-cli" if selected_languages else "docling-auto",
            "languages": selected_languages,
        }
        pdf_properties["layout_engine"] = {
            "family": "layout_heron_default",
            "runtime": "onnxruntime",
            "device": "cpu",
            "requires_runtime_compiler": False,
        }

        page_count = int(doc.num_pages())
        units = [
            DocumentUnit(index=i, kind=UnitKind.PAGE, name=f"Page {i}")
            for i in range(1, page_count + 1)
        ]
        by_page = {unit.index: unit for unit in units}
        order_by_page = {i: 1 for i in by_page}
        unpaged: list[DocumentElement] = []
        unpaged_order = 1

        try:
            from docling_core.types.doc.document import ContentLayer

            included_layers = {ContentLayer.BODY, ContentLayer.FURNITURE}
        except Exception:
            included_layers = None

        for item, level in doc.iterate_items(
            traverse_pictures=True,
            included_content_layers=included_layers,
        ):
            label_obj = _safe_attr(item, "label")
            label = _safe_attr(label_obj, "value") or str(
                label_obj or item.__class__.__name__
            )
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
                "content_layer": (
                    str(_safe_attr(item, "content_layer"))
                    if _safe_attr(item, "content_layer") is not None
                    else None
                ),
            }
            if element_type == ElementType.TABLE:
                data["table"] = _docling_table_data(item)
                if not text:
                    grid = data["table"].get("grid") or []
                    text = "\n".join(
                        " | ".join(
                            str(cell.get("text", "")) for cell in row
                        )
                        for row in grid
                    )

            if page_no in by_page:
                order = order_by_page[page_no]
                element_id = f"page-{page_no}-docling-{order}"
                by_page[page_no].elements.append(
                    DocumentElement(
                        element_id,
                        element_type,
                        order,
                        text or None,
                        data=data,
                        source=source,
                    )
                )
                order_by_page[page_no] += 1
            else:
                unpaged.append(
                    DocumentElement(
                        f"docling-unpaged-{unpaged_order}",
                        element_type,
                        unpaged_order,
                        text or None,
                        data=data,
                        source=source,
                    )
                )
                unpaged_order += 1

        if unpaged:
            units.append(
                DocumentUnit(
                    index=page_count + 1,
                    kind=UnitKind.DOCUMENT,
                    name="Unpaged content",
                    elements=unpaged,
                    metadata={"synthetic": True},
                )
            )

        pdf_properties.update(
            {
                "docling_page_count": page_count,
                "docling_schema_version": _safe_attr(doc, "version"),
            }
        )
        return CanonicalDocument(metadata=metadata, units=units)
