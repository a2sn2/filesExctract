from pathlib import Path

from openpyxl import Workbook

from files_extract.cli import main


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    output = tmp_path / "result"
    workbook = Workbook()
    workbook.active["A1"] = "hello"
    workbook.save(source)
    workbook.close()

    exit_code = main(["extract", str(source), "-o", str(output)])

    assert exit_code == 0
    assert (output / "document.json").exists()
    assert (output / "document.md").exists()
