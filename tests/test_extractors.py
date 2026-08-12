from __future__ import annotations

from pathlib import Path

from files_extract.engine import ExtractionEngine, ExtractionOptions
from files_extract.models import ElementType, UnitKind


def engine_no_render() -> ExtractionEngine:
    return ExtractionEngine(options=ExtractionOptions(render_word_pages=False))


def test_xlsx_full_structure(xlsx_file: Path) -> None:
    doc = engine_no_render().extract(xlsx_file)
    assert doc.metadata.document_type == "xlsx"
    assert len(doc.units) == 2
    assert doc.units[0].name == "بيانات"
    cells = [e for e in doc.units[0].elements if e.element_type == ElementType.CELL]
    assert any(e.data.get("formula") == "=B2*10" for e in cells)
    assert any((e.data.get("comment") or {}).get("text") == "ملاحظة" for e in cells)
    assert doc.assets
    assert any(u.object_type == "xlsx_image" for u in doc.unsupported_objects)


def test_docx_content_comments_tables_assets(docx_file: Path) -> None:
    doc = engine_no_render().extract(docx_file)
    assert doc.metadata.document_type == "docx"
    assert doc.units[0].kind == UnitKind.DOCUMENT
    texts = [e.text for e in doc.units[0].elements if e.text]
    assert "العنوان الرئيسي" in texts
    assert "فقرة عربية للاختبار" in texts
    assert "تعليق مراجعة" in texts
    tables = [e for e in doc.units[0].elements if e.element_type == ElementType.TABLE]
    assert tables and tables[0].data["row_count"] == 2
    assert doc.assets and doc.assets[0].media_type == "image/png"
    sections = doc.metadata.properties["word"]["sections"]
    assert sections[0]["header"]["blocks"][0]["text"] == "رأس الصفحة"


def test_pptx_slides_shapes_notes_assets(pptx_file: Path) -> None:
    doc = engine_no_render().extract(pptx_file)
    assert doc.metadata.document_type == "pptx"
    assert len(doc.units) == 2
    assert doc.units[1].metadata["hidden"] is True
    all_text = [e.text for u in doc.units for e in u.elements if e.text]
    assert "عنوان العرض" in all_text
    assert "نص داخل الشريحة" in all_text
    assert "ملاحظات المتحدث" in all_text
    charts = [e for e in doc.units[0].elements if e.data.get("role") == "chart"]
    assert charts and charts[0].data["chart"]["series"][0]["name"] == "Sales"
    assert doc.assets and any(a.media_type == "image/png" for a in doc.assets)


def test_pdf_pages_links_images_and_fallback_warning(pdf_file: Path) -> None:
    doc = engine_no_render().extract(pdf_file)
    assert doc.metadata.document_type == "pdf"
    assert len([u for u in doc.units if u.kind == UnitKind.PAGE]) == 2
    assert "Hello PDF page one" in (doc.units[0].elements[0].text or "")
    assert any(e.element_type == ElementType.LINK for e in doc.units[0].elements)
    assert any(a.asset_type == "pdf_image" for a in doc.assets)
    assert doc.metadata.properties["pdf"]["page_count"] == 2
