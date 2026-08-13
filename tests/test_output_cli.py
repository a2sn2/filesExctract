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


def test_reextract_replaces_previous_owned_package(tmp_path: Path, xlsx_file: Path) -> None:
    out = tmp_path / "out"
    assert main(["extract", str(xlsx_file), "-o", str(out), "--no-render-word-pages"]) == 0
    assert (out / "document.md").is_file()
    assert (out / "assets").is_dir()

    stale = out / "assets" / "stale-from-old-run.bin"
    stale.write_bytes(b"stale")

    assert main([
        "extract", str(xlsx_file), "-o", str(out),
        "--format", "json", "--no-assets", "--no-render-word-pages",
    ]) == 0

    assert (out / "document.json").is_file()
    assert (out / "manifest.json").is_file()
    assert not (out / "document.md").exists()
    assert not (out / "assets").exists()
    assert not stale.exists()


def test_non_owned_output_directory_is_not_cleaned(tmp_path: Path, xlsx_file: Path) -> None:
    out = tmp_path / "user-directory"
    out.mkdir()
    keep = out / "keep-me.txt"
    keep.write_text("user data", encoding="utf-8")
    assets = out / "assets"
    assets.mkdir()
    unrelated = assets / "unrelated.bin"
    unrelated.write_bytes(b"user data")

    assert main([
        "extract", str(xlsx_file), "-o", str(out),
        "--format", "json", "--no-assets", "--no-render-word-pages",
    ]) == 0

    assert keep.read_text(encoding="utf-8") == "user data"
    assert unrelated.read_bytes() == b"user data"


def test_doctor_json(capsys) -> None:
    assert main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dependencies"]["openpyxl"]["available"] is True
    assert "libreoffice" in report["external_tools"]
    assert "tesseract" in report["external_tools"]


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
