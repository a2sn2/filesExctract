from __future__ import annotations

import hashlib
from pathlib import Path

from .detection import DetectedFileType, detect_file_type
from .models import CanonicalDocument, DocumentMetadata
from .registry import ExtractorRegistry
from .validation import validate_document


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


class ExtractionEngine:
    def __init__(self, registry: ExtractorRegistry | None = None) -> None:
        self.registry = registry or ExtractorRegistry()

    def inspect(self, path: str | Path) -> DetectedFileType:
        return detect_file_type(path)

    def extract(self, path: str | Path) -> CanonicalDocument:
        source = Path(path).expanduser().resolve()
        detected = detect_file_type(source)
        extractor = self.registry.get(detected)

        metadata = DocumentMetadata(
            filename=source.name,
            extension=detected.extension,
            document_type=detected.document_type,
            media_type=detected.media_type,
            size_bytes=source.stat().st_size,
            sha256=_sha256(source),
            extractor=extractor.name,
            extractor_version=extractor.version,
            properties={
                "source": {
                    "is_legacy_office": detected.is_legacy_office,
                    "is_macro_enabled": detected.is_macro_enabled,
                }
            },
        )

        document = extractor.extract(source, detected, metadata)
        validate_document(document)
        return document
