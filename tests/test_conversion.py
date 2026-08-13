from pathlib import Path

import pytest

from files_extract.conversion import ConversionOptions, convert_document, main as convert_main
from files_extract.errors import FilesExtractError, InvalidInputFileError


def test_docx_copy_is_byte_identical(tmp_path: Path, docx_file: Path):
    out = tmp_path / "copy.docx"
    result = convert_document(docx_file, out, target="docx")
    assert result.mode == "exact-layout"
    assert out.read_bytes() == docx_file.read_bytes()


def test_image_to_pdf(tmp_path: Path, sample_image: Path):
    out = tmp_path / "image.pdf"
    result = convert_document(sample_image, out, target="pdf")
    assert result.pages == 1
    assert out.read_bytes().startswith(b"%PDF")


def test_invalid_conversion_requests(tmp_path: Path, sample_image: Path):
    with pytest.raises(InvalidInputFileError):
        convert_document(tmp_path / "missing.pdf", tmp_path / "out.docx", target="docx")
    with pytest.raises(FilesExtractError):
        convert_document(sample_image, tmp_path / "out.bin", target="bin")
    with pytest.raises(FilesExtractError, match="Editable reconstruction"):
        convert_document(sample_image, tmp_path / "editable.docx", target="docx", options=ConversionOptions(mode="editable"))


def test_conversion_cli(tmp_path: Path, docx_file: Path, capsys):
    out = tmp_path / "cli.docx"
    assert convert_main([str(docx_file), "-o", str(out), "--to", "docx"]) == 0
    assert out.is_file()
    assert "Mode: exact-layout" in capsys.readouterr().out
