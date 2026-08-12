from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from files_extract.engine import ExtractionEngine, ExtractionOptions

pytestmark = pytest.mark.docling


def _docling_available() -> bool:
    return importlib.util.find_spec("docling") is not None


def test_docling_is_actual_pdf_backend(pdf_file: Path) -> None:
    if not _docling_available():
        pytest.skip("Docling not installed")
    doc = ExtractionEngine(options=ExtractionOptions(render_word_pages=False)).extract(pdf_file)
    assert doc.metadata.properties["pdf"]["primary_backend"] == "docling"
    text = "\n".join(e.text or "" for u in doc.units for e in u.elements)
    assert "Hello PDF page one" in text


def test_docling_ocr_extracts_image_only_pdf(scanned_pdf_file: Path) -> None:
    if not _docling_available():
        pytest.skip("Docling not installed")
    doc = ExtractionEngine(options=ExtractionOptions(render_word_pages=False)).extract(scanned_pdf_file)
    assert doc.metadata.properties["pdf"]["primary_backend"] == "docling"
    text = "\n".join(e.text or "" for u in doc.units for e in u.elements).upper()
    assert "OCR" in text
    assert "123" in text
