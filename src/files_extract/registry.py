from __future__ import annotations

from .detection import DetectedFileType
from .errors import UnsupportedFileTypeError
from .extractors import BaseExtractor, XlsxExtractor


class ExtractorRegistry:
    def __init__(self, extractors: list[BaseExtractor] | None = None) -> None:
        self._extractors = extractors or [XlsxExtractor()]

    @property
    def extractors(self) -> tuple[BaseExtractor, ...]:
        return tuple(self._extractors)

    def get(self, detected: DetectedFileType) -> BaseExtractor:
        for extractor in self._extractors:
            if extractor.supports(detected):
                return extractor
        raise UnsupportedFileTypeError(
            f"No extractor is implemented yet for '{detected.document_type}'. "
            "Current milestone supports XLSX/XLSM; PDF, DOCX and PPTX are planned next."
        )
