from __future__ import annotations

import os
from pathlib import Path

from files_extract.runtime import configure_runtime, find_bundle_root


def test_find_bundle_root_prefers_configured_root(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    monkeypatch.setenv("FILES_EXTRACT_BUNDLE_ROOT", str(root))

    assert find_bundle_root() == root.resolve()


def test_find_bundle_root_ignores_missing_configured_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FILES_EXTRACT_BUNDLE_ROOT", str(tmp_path / "missing"))
    monkeypatch.setattr("files_extract.runtime.sys.executable", str(tmp_path / "plain" / "python.exe"))

    assert find_bundle_root() is None


def test_configure_runtime_sets_bundled_tools_and_offline_models(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "bundle"
    python_dir = root / "runtime" / "python"
    lo_program = root / "tools" / "libreoffice" / "program"
    tess_root = root / "tools" / "tesseract"
    tessdata = tess_root / "tessdata"
    models = root / "models"
    for directory in (python_dir, lo_program, tessdata, models):
        directory.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("FILES_EXTRACT_BUNDLE_ROOT", str(root))
    monkeypatch.setenv("PATH", "original-path")
    for name in (
        "TESSDATA_PREFIX",
        "DOCLING_ARTIFACTS_PATH",
        "DOCLING_SERVE_ARTIFACTS_PATH",
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
    ):
        monkeypatch.delenv(name, raising=False)

    configured = configure_runtime()

    assert configured == root.resolve()
    path_parts = os.environ["PATH"].split(os.pathsep)
    assert str(lo_program) in path_parts
    assert str(tess_root) in path_parts
    assert os.environ["TESSDATA_PREFIX"] == str(tessdata)
    assert os.environ["DOCLING_ARTIFACTS_PATH"] == str(models)
    assert os.environ["DOCLING_SERVE_ARTIFACTS_PATH"] == str(models)
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"


def test_configure_runtime_is_noop_for_source_install(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("FILES_EXTRACT_BUNDLE_ROOT", raising=False)
    monkeypatch.setattr("files_extract.runtime.sys.executable", str(tmp_path / "plain" / "python.exe"))
    original_path = os.environ.get("PATH", "")

    assert configure_runtime() is None
    assert os.environ.get("PATH", "") == original_path
