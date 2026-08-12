from __future__ import annotations

from pathlib import Path

import pytest

from files_extract.detection import detect_file_type
from files_extract.errors import DocumentValidationError
from files_extract.models import AssetReference, CanonicalDocument, DocumentMetadata
from files_extract.validation import validate_document


def test_detection_uses_content_not_just_extension(xlsx_file: Path, tmp_path: Path) -> None:
    renamed = tmp_path / "wrong.bin"
    renamed.write_bytes(xlsx_file.read_bytes())
    detected = detect_file_type(renamed)
    assert detected.document_type == "xlsx"


def test_validation_rejects_asset_path_traversal() -> None:
    metadata = DocumentMetadata("x", "pdf", "pdf", "application/pdf", 1, "0" * 64, "test")
    doc = CanonicalDocument(metadata=metadata, units=[], assets=[AssetReference("a", "x", output_path="../escape")])
    with pytest.raises(DocumentValidationError):
        validate_document(doc)
