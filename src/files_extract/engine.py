from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .detection import DetectedFileType, detect_file_type
from .errors import InvalidInputFileError
from .libreoffice import converted_temp, find_libreoffice
from .models import CanonicalDocument, DocumentMetadata, ExtractionWarning, Severity
from .registry import ExtractorRegistry
from .validation import validate_document


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(slots=True)
class ExtractionOptions:
    render_word_pages: bool = True
    max_file_size_bytes: int = 512 * 1024 * 1024
    libreoffice_timeout_seconds: int = 180


class ExtractionEngine:
    def __init__(self, registry: ExtractorRegistry | None = None, options: ExtractionOptions | None = None) -> None:
        self.registry = registry or ExtractorRegistry()
        self.options = options or ExtractionOptions()

    def inspect(self, path: str | Path) -> DetectedFileType:
        return detect_file_type(path)

    def extract(self, path: str | Path) -> CanonicalDocument:
        source = Path(path).expanduser().resolve()
        detected = detect_file_type(source)
        size = source.stat().st_size
        if size > self.options.max_file_size_bytes:
            raise InvalidInputFileError(
                f"Input file is {size} bytes, exceeding the configured {self.options.max_file_size_bytes} byte limit."
            )
        if detected.is_legacy_office:
            return self._extract_legacy(source, detected)
        document = self._extract_native(source, detected, original_source=source)
        if detected.document_type in {"docx", "docm"}:
            self._augment_word_pagination(source, document)
        validate_document(document)
        return document

    def _metadata(self, original_source: Path, detected: DetectedFileType, extractor_name: str, extractor_version: str | None) -> DocumentMetadata:
        return DocumentMetadata(
            filename=original_source.name,
            extension=detected.extension,
            document_type=detected.document_type,
            media_type=detected.media_type,
            size_bytes=original_source.stat().st_size,
            sha256=_sha256(original_source),
            extractor=extractor_name,
            extractor_version=extractor_version,
            properties={"source": {"is_legacy_office": detected.is_legacy_office, "is_macro_enabled": detected.is_macro_enabled}},
        )

    def _extract_native(self, parse_source: Path, detected: DetectedFileType, *, original_source: Path) -> CanonicalDocument:
        extractor = self.registry.get(detected)
        metadata = self._metadata(original_source, detected, extractor.name, extractor.version)
        return extractor.extract(parse_source, detected, metadata)

    def _extract_legacy(self, source: Path, detected: DetectedFileType) -> CanonicalDocument:
        mapping = {"doc": "docx", "xls": "xlsx", "ppt": "pptx"}
        target = mapping.get(detected.document_type)
        if target is None:
            raise InvalidInputFileError(f"Cannot determine legacy Office family for: {source.name}")
        with converted_temp(source, target, timeout=self.options.libreoffice_timeout_seconds) as converted:
            converted_type = detect_file_type(converted)
            document = self._extract_native(converted, converted_type, original_source=source)
            document.metadata.document_type = detected.document_type
            document.metadata.extension = detected.extension
            document.metadata.media_type = detected.media_type
            document.metadata.properties["source"]["is_legacy_office"] = True
            document.metadata.properties["conversion"] = {
                "tool": "LibreOffice",
                "from": detected.document_type,
                "to": converted_type.document_type,
                "intermediate_filename": converted.name,
            }
            # OOXML assets are referenced by archive member. The temporary converted
            # package is deleted when this context exits, so record the conversion
            # target on each asset. The output layer can re-create the same temporary
            # package from the original legacy file when asset bytes are materialized.
            for asset in document.assets:
                if asset.metadata.get("archive_member"):
                    asset.metadata["legacy_conversion_target"] = target
            document.warnings.append(ExtractionWarning(
                code="office.legacy.converted",
                message=f"Legacy {detected.document_type.upper()} was converted to {converted_type.document_type.upper()} with LibreOffice before extraction.",
                severity=Severity.INFO,
            ))
            if target == "docx":
                self._augment_word_pagination(converted, document)
            validate_document(document)
            return document

    def _augment_word_pagination(self, source: Path, document: CanonicalDocument) -> None:
        if not self.options.render_word_pages:
            document.warnings.append(ExtractionWarning(
                code="docx.pagination.disabled",
                message="Exact rendered page-count verification was disabled.",
                severity=Severity.INFO,
            ))
            return
        if not find_libreoffice():
            document.warnings.append(ExtractionWarning(
                code="docx.pagination.libreoffice_unavailable",
                message="LibreOffice is not installed, so rendered Word page-count verification could not run. Stored page metadata is still preserved when present.",
                severity=Severity.INFO,
            ))
            return
        try:
            with converted_temp(source, "pdf", timeout=self.options.libreoffice_timeout_seconds) as rendered:
                rendered_count = len(PdfReader(rendered, strict=False).pages)
            word_meta = document.metadata.properties.setdefault("word", {})
            pagination = word_meta.setdefault("pagination", {})
            pagination["rendered_page_count"] = rendered_count
            pagination["renderer"] = "LibreOffice"
            stored = word_meta.get("stored_page_count")
            if stored is not None and int(stored) != rendered_count:
                document.warnings.append(ExtractionWarning(
                    code="docx.page_count.mismatch",
                    message="The page count stored in the DOCX differs from the current LibreOffice rendering.",
                    details={"stored_page_count": stored, "rendered_page_count": rendered_count},
                ))
        except Exception as exc:
            document.warnings.append(ExtractionWarning(
                code="docx.pagination.failed",
                message="LibreOffice rendering for Word page-count verification failed; native content extraction is still available.",
                details={"error": str(exc)},
            ))
