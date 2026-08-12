from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .detection import DetectedFileType, detect_file_type
from .errors import ExtractionFailedError, InvalidInputFileError
from .libreoffice import converted_temp, find_libreoffice
from .models import (
    CanonicalDocument,
    DocumentMetadata,
    ExtractionWarning,
    Severity,
    SourceReference,
    UnitKind,
)
from .office_crypto import decrypted_office_temp
from .registry import ExtractorRegistry
from .security import ArchiveSafetyLimits, validate_zip_archive
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
    max_archive_members: int = 100_000
    max_archive_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    max_archive_single_member_bytes: int = 1024 * 1024 * 1024
    libreoffice_timeout_seconds: int = 180
    # Kept under the existing field name for API compatibility. v0.4 uses this
    # password for encrypted PDFs and encrypted modern Office documents.
    pdf_password: str | None = None


class ExtractionEngine:
    def __init__(self, registry: ExtractorRegistry | None = None, options: ExtractionOptions | None = None) -> None:
        self.options = options or ExtractionOptions()
        self.registry = registry or ExtractorRegistry(pdf_password=self.options.pdf_password)

    def inspect(self, path: str | Path) -> DetectedFileType:
        return detect_file_type(path)

    def _archive_limits(self) -> ArchiveSafetyLimits:
        return ArchiveSafetyLimits(
            max_members=self.options.max_archive_members,
            max_uncompressed_bytes=self.options.max_archive_uncompressed_bytes,
            max_single_member_bytes=self.options.max_archive_single_member_bytes,
        )

    def extract(self, path: str | Path) -> CanonicalDocument:
        source = Path(path).expanduser().resolve()
        detected = detect_file_type(source)
        size = source.stat().st_size
        if size > self.options.max_file_size_bytes:
            raise InvalidInputFileError(
                f"Input file is {size} bytes, exceeding the configured {self.options.max_file_size_bytes} byte limit."
            )

        if detected.is_encrypted_office:
            document = self._extract_encrypted_office(source, detected)
            self._ensure_provenance(document)
            validate_document(document)
            return document

        archive_stats: dict[str, int] | None = None
        if detected.document_type in {"docx", "docm", "xlsx", "xlsm", "pptx", "pptm"}:
            archive_stats = validate_zip_archive(source, self._archive_limits())

        if detected.is_legacy_office:
            document = self._extract_legacy(source, detected)
        else:
            document = self._extract_native(source, detected, original_source=source)
            if detected.document_type in {"docx", "docm"}:
                self._augment_word_pagination(source, document)

        if archive_stats is not None:
            document.metadata.properties.setdefault("source", {})["archive"] = archive_stats
        self._ensure_provenance(document)
        validate_document(document)
        return document

    def _extract_encrypted_office(
        self,
        source: Path,
        detected: DetectedFileType,
    ) -> CanonicalDocument:
        password = self.options.pdf_password
        if not password:
            raise ExtractionFailedError(
                "The Office document is encrypted and no password was supplied. "
                "Use --password or enter the password in the desktop application."
            )

        with decrypted_office_temp(
            source,
            password,
            extension=detected.extension,
        ) as decrypted:
            decrypted_type = detect_file_type(decrypted)
            if decrypted_type.document_type not in {
                "docx", "docm", "xlsx", "xlsm", "pptx", "pptm"
            }:
                raise ExtractionFailedError(
                    "The decrypted Office payload is not a supported modern Office document."
                )

            archive_stats = validate_zip_archive(decrypted, self._archive_limits())
            document = self._extract_native(
                decrypted,
                decrypted_type,
                original_source=source,
            )
            source_meta = document.metadata.properties.setdefault("source", {})
            source_meta["is_encrypted_office"] = True
            source_meta["archive"] = archive_stats
            document.metadata.properties["security"] = {
                "encrypted_source": True,
                "decrypted_for_extraction": True,
                "decryption_backend": "msoffcrypto-tool",
                "password_persisted": False,
            }
            document.warnings.append(
                ExtractionWarning(
                    code="office.encrypted.decrypted",
                    message=(
                        "The encrypted Office source was decrypted into an isolated "
                        "temporary file for extraction. The password and decrypted "
                        "intermediate are not written to the output package."
                    ),
                    severity=Severity.INFO,
                )
            )
            if decrypted_type.document_type in {"docx", "docm"}:
                self._augment_word_pagination(decrypted, document)
            return document

    def _metadata(
        self,
        original_source: Path,
        detected: DetectedFileType,
        extractor_name: str,
        extractor_version: str | None,
    ) -> DocumentMetadata:
        return DocumentMetadata(
            filename=original_source.name,
            extension=detected.extension,
            document_type=detected.document_type,
            media_type=detected.media_type,
            size_bytes=original_source.stat().st_size,
            sha256=_sha256(original_source),
            extractor=extractor_name,
            extractor_version=extractor_version,
            properties={
                "source": {
                    "is_legacy_office": detected.is_legacy_office,
                    "is_macro_enabled": detected.is_macro_enabled,
                    "is_encrypted_office": detected.is_encrypted_office,
                }
            },
        )

    def _extract_native(
        self,
        parse_source: Path,
        detected: DetectedFileType,
        *,
        original_source: Path,
    ) -> CanonicalDocument:
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
            validate_zip_archive(converted, self._archive_limits())
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
            for asset in document.assets:
                if asset.metadata.get("archive_member"):
                    asset.metadata["legacy_conversion_target"] = target
            document.warnings.append(
                ExtractionWarning(
                    code="office.legacy.converted",
                    message=(
                        f"Legacy {detected.document_type.upper()} was converted to "
                        f"{converted_type.document_type.upper()} with LibreOffice before extraction."
                    ),
                    severity=Severity.INFO,
                )
            )
            if target == "docx":
                self._augment_word_pagination(converted, document)
            return document

    def _augment_word_pagination(self, source: Path, document: CanonicalDocument) -> None:
        if not self.options.render_word_pages:
            document.warnings.append(
                ExtractionWarning(
                    code="docx.pagination.disabled",
                    message="Rendered Word page-count verification was disabled.",
                    severity=Severity.INFO,
                )
            )
            return
        if not find_libreoffice():
            document.warnings.append(
                ExtractionWarning(
                    code="docx.pagination.libreoffice_unavailable",
                    message=(
                        "LibreOffice is not installed, so rendered Word page verification could not run. "
                        "Stored page metadata is still preserved when present."
                    ),
                    severity=Severity.INFO,
                )
            )
            return
        try:
            with converted_temp(source, "pdf", timeout=self.options.libreoffice_timeout_seconds) as rendered:
                reader = PdfReader(rendered, strict=False)
                rendered_pages = []
                for page_number, page in enumerate(reader.pages, start=1):
                    try:
                        page_text = page.extract_text(extraction_mode="layout") or ""
                    except Exception:
                        page_text = page.extract_text() or ""
                    rendered_pages.append({"page_number": page_number, "text": page_text})
                rendered_count = len(reader.pages)
            word_meta = document.metadata.properties.setdefault("word", {})
            pagination = word_meta.setdefault("pagination", {})
            pagination["rendered_page_count"] = rendered_count
            pagination["renderer"] = "LibreOffice"
            pagination["rendered_pages"] = rendered_pages
            stored = word_meta.get("stored_page_count")
            if stored is not None and int(stored) != rendered_count:
                document.warnings.append(
                    ExtractionWarning(
                        code="docx.page_count.mismatch",
                        message="The page count stored in the DOCX differs from the current LibreOffice rendering.",
                        details={"stored_page_count": stored, "rendered_page_count": rendered_count},
                    )
                )
        except Exception as exc:
            document.warnings.append(
                ExtractionWarning(
                    code="docx.pagination.failed",
                    message=(
                        "LibreOffice rendering for Word page verification failed; "
                        "native content extraction is still available."
                    ),
                    details={"error": str(exc)},
                )
            )

    @staticmethod
    def _ensure_provenance(document: CanonicalDocument) -> None:
        """Fill a structural source reference for elements that a parser left untagged."""
        for unit in document.units:
            for element in unit.elements:
                if element.source is not None:
                    continue
                source = SourceReference(unit_index=unit.index, unit_name=unit.name)
                if unit.kind == UnitKind.PAGE:
                    source.page_number = unit.index
                elif unit.kind == UnitKind.SHEET:
                    source.sheet_name = unit.name
                elif unit.kind == UnitKind.SLIDE:
                    source.slide_number = unit.index
                element.source = source
