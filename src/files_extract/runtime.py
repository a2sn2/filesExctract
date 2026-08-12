from __future__ import annotations

import os
import sys
from pathlib import Path


def _prepend_path(path: Path) -> None:
    if not path.exists():
        return
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    value = str(path)
    if value.lower() not in {p.lower() for p in parts}:
        os.environ["PATH"] = value + (os.pathsep + current if current else "")


def find_bundle_root() -> Path | None:
    configured = os.environ.get("FILES_EXTRACT_BUNDLE_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
        if root.exists():
            return root

    executable = Path(sys.executable).resolve()
    candidates = [
        executable.parent,
        executable.parent.parent,
        executable.parent.parent.parent,
    ]
    for candidate in candidates:
        if (candidate / "runtime" / "python").exists() and (candidate / "tools").exists():
            return candidate
    return None


def configure_runtime() -> Path | None:
    """Configure paths for a self-contained desktop distribution.

    Source installs are left untouched. A packaged runtime advertises itself with
    FILES_EXTRACT_BUNDLE_ROOT or by containing runtime/python and tools next to
    the application launcher.
    """

    root = find_bundle_root()
    if root is None:
        return None

    os.environ["FILES_EXTRACT_BUNDLE_ROOT"] = str(root)

    libreoffice_program = root / "tools" / "libreoffice" / "program"
    tesseract_root = root / "tools" / "tesseract"
    _prepend_path(libreoffice_program)
    _prepend_path(tesseract_root)

    tessdata = tesseract_root / "tessdata"
    if tessdata.exists():
        os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))

    models = root / "models"
    if models.exists():
        # Docling itself has used both names across integrations. Set both and
        # keep the runtime offline so a packaged build never depends on a model
        # download from the target PC.
        os.environ.setdefault("DOCLING_ARTIFACTS_PATH", str(models))
        os.environ.setdefault("DOCLING_SERVE_ARTIFACTS_PATH", str(models))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    return root
