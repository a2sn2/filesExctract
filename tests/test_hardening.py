from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from files_extract.cli import main
from files_extract.detection import OLE_SIGNATURE, detect_file_type
from files_extract.engine import ExtractionEngine, ExtractionOptions
from files_extract.errors import ExtractionFailedError, InvalidInputFileError, UnsupportedFileTypeError
from files_extract.output import write_output_package


def test_file_size_limit_is_enforced(xlsx_file: Path) -> None:
    engine = ExtractionEngine(options=ExtractionOptions(render_word_pages=False, max_file_size_bytes=1))
    with pytest.raises(InvalidInputFileError):
        engine.extract(xlsx_file)


def test_ooxml_uncompressed_archive_limit_is_enforced(xlsx_file: Path) -> None:
    engine = ExtractionEngine(
        options=ExtractionOptions(render_word_pages=False, max_archive_uncompressed_bytes=1)
    )
    with pytest.raises(InvalidInputFileError):
        engine.extract(xlsx_file)


def test_macro_detection_uses_package_content_not_filename(xlsx_file: Path, tmp_path: Path) -> None:
    macro = tmp_path / "renamed.xlsx"
    with zipfile.ZipFile(xlsx_file) as src, zipfile.ZipFile(macro, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("xl/vbaProject.bin", b"fake-vba-for-detection-only")
    detected = detect_file_type(macro)
    assert detected.document_type == "xlsm"
    assert detected.is_macro_enabled is True


def test_encrypted_modern_office_container_is_detected_and_rejected_clearly(tmp_path: Path) -> None:
    path = tmp_path / "protected.docx"
    path.write_bytes(OLE_SIGNATURE + b"EncryptedPackage placeholder")
    detected = detect_file_type(path)
    assert detected.document_type == "encrypted_office"
    assert detected.is_encrypted_office is True
    with pytest.raises(UnsupportedFileTypeError, match="Password-protected modern Office"):
        ExtractionEngine().extract(path)


def test_encrypted_pdf_requires_password(encrypted_pdf_file: Path) -> None:
    with pytest.raises(ExtractionFailedError, match="password"):
        ExtractionEngine(options=ExtractionOptions(render_word_pages=False)).extract(encrypted_pdf_file)


def test_encrypted_pdf_extracts_with_password(encrypted_pdf_file: Path) -> None:
    engine = ExtractionEngine(
        options=ExtractionOptions(render_word_pages=False, pdf_password="secret")
    )
    doc = engine.extract(encrypted_pdf_file)
    text = "\n".join(e.text or "" for u in doc.units for e in u.elements)
    assert "Hello PDF page one" in text
    assert "password" not in json.dumps(doc.to_dict(), ensure_ascii=False).lower()
    assert "secret" not in json.dumps(doc.to_dict(), ensure_ascii=False)


def test_pdf_attachment_is_declared_and_materialized(
    tmp_path: Path, pdf_with_attachment: Path
) -> None:
    engine = ExtractionEngine(options=ExtractionOptions(render_word_pages=False))
    doc = engine.extract(pdf_with_attachment)
    attachments = [a for a in doc.assets if a.asset_type == "pdf_attachment"]
    assert len(attachments) == 1
    out = tmp_path / "attachment-out"
    manifest = write_output_package(pdf_with_attachment, doc, out)
    assert manifest["summary"]["assets_written"] >= 1
    attachment_paths = [
        out / str(item["path"])
        for item in manifest["files"]
        if "attachment" in str(item["path"])
    ]
    assert attachment_paths
    assert attachment_paths[0].read_bytes() == b"embedded attachment content"


def test_batch_same_stem_different_extensions_do_not_collide(
    tmp_path: Path, xlsx_file: Path, docx_file: Path
) -> None:
    source = tmp_path / "batch-collision"
    source.mkdir()
    (source / "same.xlsx").write_bytes(xlsx_file.read_bytes())
    (source / "same.docx").write_bytes(docx_file.read_bytes())
    out = tmp_path / "batch-collision-out"
    assert main(["batch", str(source), "-o", str(out), "--no-render-word-pages"]) == 0
    assert (out / "same__xlsx_extracted" / "document.json").exists()
    assert (out / "same__docx_extracted" / "document.json").exists()


def test_batch_records_corrupt_file_and_continues(tmp_path: Path, xlsx_file: Path) -> None:
    source = tmp_path / "batch-errors"
    source.mkdir()
    (source / "good.xlsx").write_bytes(xlsx_file.read_bytes())
    (source / "bad.pdf").write_bytes(b"%PDF-1.7\nnot-a-real-pdf")
    out = tmp_path / "batch-errors-out"
    assert main(["batch", str(source), "-o", str(out), "--no-render-word-pages"]) == 1
    summary = json.loads((out / "batch-summary.json").read_text(encoding="utf-8"))
    assert summary["failures"] == 1
    assert {item["status"] for item in summary["files"]} == {"ok", "error"}


def test_docx_body_elements_have_provenance(docx_file: Path) -> None:
    doc = ExtractionEngine(options=ExtractionOptions(render_word_pages=False)).extract(docx_file)
    assert doc.units[0].elements
    assert all(element.source is not None for element in doc.units[0].elements)
    assert all(element.source.unit_index == 1 for element in doc.units[0].elements)


def test_docx_header_footer_and_image_order_metadata(docx_file: Path) -> None:
    doc = ExtractionEngine(options=ExtractionOptions(render_word_pages=False)).extract(docx_file)
    roles = {element.data.get("role") for element in doc.units[0].elements if isinstance(element.data, dict)}
    assert "header" in roles
    assert "footer" in roles
    image_markers = []
    for element in doc.units[0].elements:
        for run in element.data.get("runs", []) if isinstance(element.data, dict) else []:
            image_markers.extend(item for item in run.get("inner_content", []) if item.get("type") == "image")
    assert image_markers
    assert image_markers[0].get("asset_id")


@pytest.mark.integration
def test_word_rendered_pagination_preserves_page_text(docx_file: Path) -> None:
    from files_extract.libreoffice import find_libreoffice

    if not find_libreoffice():
        pytest.skip("LibreOffice not installed")
    doc = ExtractionEngine().extract(docx_file)
    pagination = doc.metadata.properties["word"]["pagination"]
    assert pagination["rendered_page_count"] >= 2
    assert len(pagination["rendered_pages"]) == pagination["rendered_page_count"]
    assert any("SECOND PAGE MARKER" in page["text"] for page in pagination["rendered_pages"])
