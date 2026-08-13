from __future__ import annotations

import argparse
import os
import shutil
import sys
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="files-convert", description="Layout-preserving document conversion.")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--to", choices=("docx", "pdf"), required=True, dest="target")
    parser.add_argument("--mode", choices=("exact-layout", "editable"), default="exact-layout")
    parser.add_argument("--render-dpi", type=int, default=216)
    parser.add_argument("--libreoffice-timeout", type=int, default=180)
    parser.add_argument("--password")
    args = parser.parse_args(argv)
    try:
        result = convert_document(
            args.input,
            args.output,
            target=args.target,
            options=ConversionOptions(
                mode=args.mode,
                render_dpi=args.render_dpi,
                libreoffice_timeout_seconds=args.libreoffice_timeout,
                password=args.password or os.environ.get("FILES_EXTRACT_PASSWORD"),
            ),
        )
        print(f"Converted: {result.source}")
        print(f"Target: {result.target} | Mode: {result.mode}")
        if result.pages is not None:
            print(f"Pages: {result.pages}")
        print(f"Output: {result.output}")
        for warning in result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        return 0
    except FilesExtractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
