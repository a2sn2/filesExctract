from __future__ import annotations

import json
from pathlib import Path

from files_extract.cli import main


def test_extract_cli_writes_complete_package(tmp_path: Path, xlsx_file: Path) -> None:
    out = tmp_path / "out"
    code = main(["extract", str(xlsx_file), "-o", str(out), "--no-render-word-pages"])
    assert code == 0
    assert (out / "document.json").exists()
    assert (out / "document.md").exists()
    assert (out / "manifest.json").exists()
    assert (out / "assets").is_dir()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["assets_written"] >= 1


def test_doctor_json(capsys) -> None:
    assert main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dependencies"]["openpyxl"]["available"] is True
    assert "libreoffice" in report["external_tools"]


def test_batch_continues_and_writes_summary(tmp_path: Path, xlsx_file: Path, docx_file: Path) -> None:
    source = tmp_path / "batch"
    source.mkdir()
    (source / "a.xlsx").write_bytes(xlsx_file.read_bytes())
    (source / "b.docx").write_bytes(docx_file.read_bytes())
    out = tmp_path / "batch-out"
    assert main(["batch", str(source), "-o", str(out), "--no-render-word-pages"]) == 0
    summary = json.loads((out / "batch-summary.json").read_text(encoding="utf-8"))
    assert summary["failures"] == 0
    assert len(summary["files"]) == 2
