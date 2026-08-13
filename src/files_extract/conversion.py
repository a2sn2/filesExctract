from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .errors import FilesExtractError, InvalidInputFileError
from .libreoffice import convert_office
from .visual_docx import image_to_visual_docx, pdf_to_visual_docx

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
_OFFICE_SUFFIXES = {".doc", ".docx", ".docm", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".pptm"}


@dataclass(slots=True)
class ConversionOptions:
    mode: str = "exact-layout"
    render_dpi: int = 216
    libreoffice_timeout_seconds: int = 180
    password: str | None = None


@dataclass(slots=True)
class ConversionResult:
    source: Path
    output: Path
    target: str
    mode: str
    pages: int | None = None
    warnings: list[str] = field(default_factory=list)


def convert_document(source: str | Path, output: str | Path, *, target: str, options: ConversionOptions | None = None) -> ConversionResult:
    opts = options or ConversionOptions()
    src = Path(source).expanduser().resolve()
    dst = Path(output).expanduser().resolve()
    if not src.is_file():
        raise InvalidInputFileError(f"Conversion source does not exist: {src}")

    target = target.lower().lstrip(".")
    if target not in {"docx", "pdf"}:
        raise FilesExtractError("Conversion target must be docx or pdf.")
    if opts.mode != "exact-layout":
        raise FilesExtractError("Editable reconstruction is not enabled in this build; use exact-layout.")

    dst.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()

    if target == "docx":
        if suffix == ".docx":
            if src != dst:
                shutil.copy2(src, dst)
            return ConversionResult(src, dst, target, opts.mode)
        if suffix == ".pdf":
            pages = pdf_to_visual_docx(src, dst, dpi=opts.render_dpi, password=opts.password)
            return ConversionResult(src, dst, target, opts.mode, pages=pages)
        if suffix in _IMAGE_SUFFIXES:
            pages = image_to_visual_docx(src, dst)
            return ConversionResult(src, dst, target, opts.mode, pages=pages)
        if suffix in _OFFICE_SUFFIXES:
            with tempfile.TemporaryDirectory(prefix="files-extract-convert-") as temp:
                pdf = convert_office(src, "pdf", Path(temp), timeout=opts.libreoffice_timeout_seconds)
                pages = pdf_to_visual_docx(pdf, dst, dpi=opts.render_dpi)
            return ConversionResult(src, dst, target, opts.mode, pages=pages, warnings=["Office source was rendered through LibreOffice before Word packaging to prevent reflow."])

    if target == "pdf":
        if suffix == ".pdf":
            if src != dst:
                shutil.copy2(src, dst)
            return ConversionResult(src, dst, target, opts.mode)
        if suffix in _IMAGE_SUFFIXES:
            with Image.open(src) as image:
                image.convert("RGB").save(dst, "PDF")
            return ConversionResult(src, dst, target, opts.mode, pages=1)
        if suffix in _OFFICE_SUFFIXES:
            with tempfile.TemporaryDirectory(prefix="files-extract-convert-") as temp:
                pdf = convert_office(src, "pdf", Path(temp), timeout=opts.libreoffice_timeout_seconds)
                shutil.copy2(pdf, dst)
            return ConversionResult(src, dst, target, opts.mode)

    raise FilesExtractError(f"Unsupported conversion source: {src.name}")
