from __future__ import annotations

import json
from pathlib import Path

from msoffcrypto.format.ooxml import OOXMLFile
from openpyxl import Workbook

from files_extract.cli import main


def test_cli_private_password_environment_decrypts_office_without_persisting_secret(
    tmp_path: Path, monkeypatch
) -> None:
    plain = tmp_path / "plain.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet["A1"] = "secret data"
    workbook.save(plain)

    protected = tmp_path / "protected.xlsx"
    with plain.open("rb") as source, protected.open("wb") as destination:
        OOXMLFile(source).encrypt("environment-secret", destination)

    output = tmp_path / "out"
    monkeypatch.setenv("FILES_EXTRACT_PASSWORD", "environment-secret")
    assert main([
        "extract",
        str(protected),
        "-o",
        str(output),
        "--no-render-word-pages",
    ]) == 0

    serialized = (output / "document.json").read_text(encoding="utf-8")
    assert "environment-secret" not in serialized
    payload = json.loads(serialized)
    security = payload["metadata"]["properties"]["security"]
    assert security["encrypted_source"] is True
    assert security["decrypted_for_extraction"] is True
    assert security["password_persisted"] is False
