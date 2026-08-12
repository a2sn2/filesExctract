from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..detection import DetectedFileType
from ..models import CanonicalDocument, DocumentMetadata


class BaseExtractor(ABC):
    name = "base"
    version: str | None = None
    supported_types: frozenset[str] = frozenset()

    def supports(self, detected: DetectedFileType) -> bool:
        return detected.document_type in self.supported_types

    @abstractmethod
    def extract(self, path: Path, detected: DetectedFileType, metadata: DocumentMetadata) -> CanonicalDocument:
        raise NotImplementedError
