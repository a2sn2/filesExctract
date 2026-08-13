from __future__ import annotations

from pathlib import Path


def pdf_to_visual_docx(source: Path, output: Path, *, dpi: int = 216, password: str | None = None) -> int:
    raise NotImplementedError


def image_to_visual_docx(source: Path, output: Path) -> int:
    raise NotImplementedError
