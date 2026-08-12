from pathlib import Path

from openpyxl import Workbook

from files_extract.detection import detect_file_type


def test_detects_xlsx_by_ooxml_contents(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    workbook = Workbook()
    workbook.save(path)
    workbook.close()

    detected = detect_file_type(path)

    assert detected.document_type == "xlsx"
    assert detected.extension == "xlsx"
    assert detected.media_type is not None
    assert detected.is_legacy_office is False
