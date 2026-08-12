from __future__ import annotations

import mimetypes
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidInputFileError

PDF_SIGNATURE = b"%PDF-"
OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")

OOXML_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "docm": "application/vnd.ms-word.document.macroEnabled.12",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pptm": "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
}


@dataclass(frozen=True, slots=True)
class DetectedFileType:
    document_type: str
    extension: str
    media_type: str | None
    is_legacy_office: bool = False
    is_macro_enabled: bool = False


def detect_file_type(path: str | Path) -> DetectedFileType:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise InvalidInputFileError(f"Input file does not exist or is not a file: {file_path}")

    extension = file_path.suffix.lower().lstrip(".")
    try:
        with file_path.open("rb") as handle:
            signature = handle.read(8)
    except OSError as exc:
        raise InvalidInputFileError(f"Unable to read input file: {file_path}") from exc

    if signature.startswith(PDF_SIGNATURE):
        return DetectedFileType("pdf", extension or "pdf", "application/pdf")

    if signature.startswith(OLE_SIGNATURE):
        legacy_type = extension if extension in {"doc", "xls", "ppt"} else "legacy_office"
        media_type, _ = mimetypes.guess_type(file_path.name)
        return DetectedFileType(
            legacy_type,
            extension,
            media_type,
            is_legacy_office=True,
        )

    if zipfile.is_zipfile(file_path):
        try:
            with zipfile.ZipFile(file_path) as archive:
                names = set(archive.namelist())
        except (OSError, zipfile.BadZipFile) as exc:
            raise InvalidInputFileError(f"Unable to inspect OOXML archive: {file_path}") from exc

        if any(name.startswith("word/") for name in names):
            family = "docm" if extension == "docm" else "docx"
        elif any(name.startswith("xl/") for name in names):
            family = "xlsm" if extension == "xlsm" else "xlsx"
        elif any(name.startswith("ppt/") for name in names):
            family = "pptm" if extension == "pptm" else "pptx"
        else:
            family = extension or "zip"

        return DetectedFileType(
            document_type=family,
            extension=extension,
            media_type=OOXML_MEDIA_TYPES.get(family),
            is_macro_enabled=family in {"docm", "xlsm", "pptm"},
        )

    media_type, _ = mimetypes.guess_type(file_path.name)
    return DetectedFileType(extension or "unknown", extension, media_type)
