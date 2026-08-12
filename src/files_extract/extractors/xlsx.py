from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell

from ..assets import collect_ooxml_assets
from ..detection import DetectedFileType
from ..errors import ExtractionFailedError
from ..models import (
    CanonicalDocument, DocumentElement, DocumentMetadata, DocumentUnit, ElementType,
    ExtractionWarning, SourceReference, UnitKind, UnsupportedObject,
)
from .base import BaseExtractor


def _safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _anchor_metadata(anchor: Any) -> dict[str, Any]:
    if isinstance(anchor, str):
        return {"anchor": anchor}
    result: dict[str, Any] = {}
    for key, attr in (("from", "_from"), ("to", "to")):
        marker = _safe_attr(anchor, attr)
        if marker is not None:
            result[key] = {
                "column_zero_based": _safe_attr(marker, "col"), "row_zero_based": _safe_attr(marker, "row"),
                "column_offset": _safe_attr(marker, "colOff"), "row_offset": _safe_attr(marker, "rowOff"),
            }
    return result


class XlsxExtractor(BaseExtractor):
    name = "openpyxl-native"
    supported_types = frozenset({"xlsx", "xlsm"})

    def __init__(self) -> None:
        try:
            import openpyxl
            self.version = openpyxl.__version__
        except Exception:
            self.version = None

    def extract(self, path: Path, detected: DetectedFileType, metadata: DocumentMetadata) -> CanonicalDocument:
        keep_vba = detected.document_type == "xlsm"
        try:
            wb = load_workbook(path, data_only=False, read_only=False, keep_vba=keep_vba, keep_links=True)
            cached = load_workbook(path, data_only=True, read_only=False, keep_vba=keep_vba, keep_links=True)
        except Exception as exc:
            raise ExtractionFailedError(f"Failed to open workbook: {path.name}: {exc}") from exc
        units: list[DocumentUnit] = []
        warnings: list[ExtractionWarning] = []
        unsupported: list[UnsupportedObject] = []
        try:
            metadata.properties["workbook"] = self._workbook_metadata(wb)
            try:
                with zipfile.ZipFile(path) as archive:
                    package_names = set(archive.namelist())
            except Exception:
                package_names = set()
            for prefix, object_type, description in (
                ("xl/pivotTables/", "xlsx_pivot_table", "Pivot table definitions were detected; source cells are extracted but pivot semantics are not fully normalized."),
                ("xl/slicers/", "xlsx_slicer", "Excel slicer parts were detected; slicer UI state is not normalized."),
                ("xl/threadedComments/", "xlsx_threaded_comments", "Threaded comments were detected; openpyxl cell comments do not expose the full threaded conversation."),
                ("xl/queryTables/", "xlsx_query_table", "External/query table definitions were detected; remote query results are not refreshed."),
            ):
                members = sorted(name for name in package_names if name.startswith(prefix) and not name.endswith("/"))
                if members:
                    unsupported.append(UnsupportedObject(
                        object_type=object_type,
                        status="detected_not_fully_parsed",
                        description=description,
                        metadata={"count": len(members), "archive_parts": members},
                    ))
            if "xl/connections.xml" in package_names:
                unsupported.append(UnsupportedObject(
                    object_type="xlsx_data_connections",
                    status="detected_not_fully_parsed",
                    description="Workbook data connections were detected; external data sources are not contacted or refreshed.",
                    metadata={"archive_part": "xl/connections.xml"},
                ))

            if keep_vba and _safe_attr(wb, "vba_archive") is not None:
                unsupported.append(UnsupportedObject("vba_project", "detected_not_parsed", "The VBA project is preserved but macro source is not interpreted."))
            external = list(_safe_attr(wb, "_external_links", []) or [])
            if external:
                unsupported.append(UnsupportedObject("external_workbook_links", "detected_partially_parsed", "External workbook links were detected but external content is not resolved.", metadata={"count": len(external)}))
            for idx, ws in enumerate(wb.worksheets, start=1):
                unit, ws_warnings, ws_unsupported = self._sheet(ws, cached[ws.title], idx)
                units.append(unit); warnings.extend(ws_warnings); unsupported.extend(ws_unsupported)
        finally:
            wb.close(); cached.close()
        assets = collect_ooxml_assets(path, detected.document_type)
        asset_by_sha = {asset.sha256: asset.asset_id for asset in assets if asset.sha256}
        for unit in units:
            for element in unit.elements:
                if element.element_type != ElementType.IMAGE:
                    continue
                image = element.data.get("image", {})
                if image.get("sha256") in asset_by_sha:
                    image["asset_id"] = asset_by_sha[image["sha256"]]
        return CanonicalDocument(
            metadata=metadata,
            units=units,
            warnings=warnings,
            unsupported_objects=unsupported,
            assets=assets,
        )

    def _workbook_metadata(self, wb: Any) -> dict[str, Any]:
        p = wb.properties
        props = {}
        for name in ("title", "subject", "creator", "keywords", "description", "lastModifiedBy", "created", "modified", "category", "contentStatus", "identifier", "language", "version", "revision", "lastPrinted"):
            v = _safe_attr(p, name)
            if v is not None:
                props[name] = v
        defined = []
        try:
            for item in wb.defined_names.values():
                defined.append({"name": _safe_attr(item, "name"), "value": _safe_attr(item, "attr_text"), "type": _safe_attr(item, "type"), "hidden": _safe_attr(item, "hidden"), "comment": _safe_attr(item, "comment"), "local_sheet_id": _safe_attr(item, "localSheetId")})
        except Exception:
            pass
        calc = _safe_attr(wb, "calculation")
        calc_meta = {}
        if calc is not None:
            for name in ("calcMode", "calcId", "fullCalcOnLoad", "forceFullCalc", "iterate"):
                v = _safe_attr(calc, name)
                if v is not None: calc_meta[name] = v
        return {"core_properties": props, "sheet_names": list(wb.sheetnames), "defined_names": defined, "calculation": calc_meta}

    def _sheet(self, ws: Any, cached_ws: Any, idx: int) -> tuple[DocumentUnit, list[ExtractionWarning], list[UnsupportedObject]]:
        source = SourceReference(unit_index=idx, unit_name=ws.title, sheet_name=ws.title)
        warnings: list[ExtractionWarning] = []; unsupported: list[UnsupportedObject] = []
        merged = [str(r) for r in ws.merged_cells.ranges]
        hidden_rows = sorted(i for i, d in ws.row_dimensions.items() if _safe_attr(d, "hidden") is True)
        hidden_cols = sorted(k for k, d in ws.column_dimensions.items() if _safe_attr(d, "hidden") is True)
        tables = []
        try:
            for t in ws.tables.values():
                tables.append({"name": _safe_attr(t, "name"), "display_name": _safe_attr(t, "displayName"), "ref": _safe_attr(t, "ref"), "header_row_count": _safe_attr(t, "headerRowCount"), "totals_row_count": _safe_attr(t, "totalsRowCount")})
        except Exception as exc:
            warnings.append(ExtractionWarning("xlsx.tables.partial", "One or more Excel table definitions could not be fully read.", source=source, details={"error": str(exc)}))
        validations = []
        try:
            for v in (_safe_attr(_safe_attr(ws, "data_validations"), "dataValidation", []) or []):
                validations.append({"type": _safe_attr(v, "type"), "operator": _safe_attr(v, "operator"), "ranges": str(_safe_attr(v, "sqref", "")), "formula1": _safe_attr(v, "formula1"), "formula2": _safe_attr(v, "formula2"), "allow_blank": _safe_attr(v, "allowBlank")})
        except Exception as exc:
            warnings.append(ExtractionWarning("xlsx.data_validations.partial", "One or more data validation rules could not be fully read.", source=source, details={"error": str(exc)}))
        def _header_footer(value: Any) -> dict[str, Any]:
            return {
                "left": _safe_attr(_safe_attr(value, "left"), "text"),
                "center": _safe_attr(_safe_attr(value, "center"), "text"),
                "right": _safe_attr(_safe_attr(value, "right"), "text"),
            }

        row_dimensions = {
            str(i): {"height": _safe_attr(d, "height"), "hidden": _safe_attr(d, "hidden"), "outline_level": _safe_attr(d, "outlineLevel")}
            for i, d in ws.row_dimensions.items()
            if _safe_attr(d, "height") is not None or _safe_attr(d, "hidden") or _safe_attr(d, "outlineLevel", 0)
        }
        column_dimensions = {
            str(k): {"width": _safe_attr(d, "width"), "hidden": _safe_attr(d, "hidden"), "outline_level": _safe_attr(d, "outlineLevel")}
            for k, d in ws.column_dimensions.items()
            if _safe_attr(d, "width") is not None or _safe_attr(d, "hidden") or _safe_attr(d, "outlineLevel", 0)
        }

        meta = {
            "state": ws.sheet_state, "max_row": ws.max_row, "max_column": ws.max_column,
            "merged_ranges": merged, "hidden_rows": hidden_rows, "hidden_columns": hidden_cols,
            "freeze_panes": str(ws.freeze_panes) if ws.freeze_panes else None,
            "auto_filter": _safe_attr(ws.auto_filter, "ref"), "print_area": str(ws.print_area) if ws.print_area else None,
            "print_title_rows": _safe_attr(ws, "print_title_rows"), "print_title_cols": _safe_attr(ws, "print_title_cols"),
            "tables": tables, "data_validations": validations,
            "headers_footers": {
                "odd_header": _header_footer(ws.oddHeader),
                "odd_footer": _header_footer(ws.oddFooter),
                "even_header": _header_footer(ws.evenHeader),
                "even_footer": _header_footer(ws.evenFooter),
                "first_header": _header_footer(ws.firstHeader),
                "first_footer": _header_footer(ws.firstFooter),
            },
            "row_dimensions": row_dimensions,
            "column_dimensions": column_dimensions,
            "sheet_view": {
                "show_grid_lines": _safe_attr(ws.sheet_view, "showGridLines"),
                "zoom_scale": _safe_attr(ws.sheet_view, "zoomScale"),
                "right_to_left": _safe_attr(ws.sheet_view, "rightToLeft"),
            },
        }
        elements = [DocumentElement(f"sheet-{idx}-metadata", ElementType.METADATA, 0, data=meta, source=source)]
        order = 1
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell, MergedCell) or not (cell.value is not None or cell.comment is not None or cell.hyperlink is not None):
                    continue
                formula = cell.value if cell.data_type == "f" else None
                cache_val = cached_ws[cell.coordinate].value if formula is not None else None
                h = cell.hyperlink
                c = cell.comment
                data = {
                    "coordinate": cell.coordinate, "row": cell.row, "column": cell.column, "value": cell.value,
                    "formula": formula, "cached_value": cache_val, "data_type": cell.data_type,
                    "number_format": cell.number_format, "style_id": cell.style_id, "is_date": bool(_safe_attr(cell, "is_date", False)),
                    "hyperlink": None if h is None else {"target": _safe_attr(h, "target"), "location": _safe_attr(h, "location"), "display": _safe_attr(h, "display"), "tooltip": _safe_attr(h, "tooltip")},
                    "comment": None if c is None else {"text": c.text, "author": c.author, "width": _safe_attr(c, "width"), "height": _safe_attr(c, "height")},
                    "row_hidden": cell.row in hidden_rows, "column_hidden": cell.column_letter in hidden_cols,
                }
                elements.append(DocumentElement(f"sheet-{idx}-cell-{cell.coordinate}", ElementType.CELL, order, None if cell.value is None else str(cell.value), data=data, source=SourceReference(unit_index=idx, unit_name=ws.title, sheet_name=ws.title, row=cell.row, column=cell.column, cell=cell.coordinate)))
                order += 1
        for t_idx, t in enumerate(tables, start=1):
            elements.append(DocumentElement(f"sheet-{idx}-table-{t_idx}", ElementType.TABLE, order, data=t, source=source)); order += 1
        for image_idx, image in enumerate(list(_safe_attr(ws, "_images", []) or []), start=1):
            image_meta = {
                "index": image_idx,
                "format": _safe_attr(image, "format"),
                "width": _safe_attr(image, "width"),
                "height": _safe_attr(image, "height"),
                **_anchor_metadata(_safe_attr(image, "anchor")),
            }
            try:
                payload = image._data()
                image_meta["sha256"] = hashlib.sha256(payload).hexdigest()
            except Exception:
                pass
            elements.append(DocumentElement(
                f"sheet-{idx}-image-{image_idx}",
                ElementType.IMAGE,
                order,
                data={"image": image_meta},
                source=source,
            ))
            order += 1
            unsupported.append(UnsupportedObject(
                "xlsx_image",
                "asset_extracted_structure_partial",
                "Worksheet image bytes are extracted and anchor/layout is recorded; image semantics are not interpreted.",
                source=source,
                metadata=image_meta,
            ))
        for chart_idx, chart in enumerate(list(_safe_attr(ws, "_charts", []) or []), start=1):
            unsupported.append(UnsupportedObject("xlsx_chart", "detected_partially_parsed", "A worksheet chart was detected; chart rendering and full series normalization are not implemented yet.", source=source, metadata={"index": chart_idx, "style": _safe_attr(chart, "style"), **_anchor_metadata(_safe_attr(chart, "anchor"))}))
        return DocumentUnit(idx, UnitKind.SHEET, ws.title, elements, meta), warnings, unsupported
