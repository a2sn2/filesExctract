from __future__ import annotations

from .detection import DetectedFileType
from .errors import UnsupportedFileTypeError
from .extractors import BaseExtractor, DocxExtractor, PdfExtractor, PptxExtractor, XlsxExtractor


class ExtractorRegistry:
    def __init__(
        self,
        extractors: list[BaseExtractor] | None = None,
        *,
        pdf_password: str | None = None,
    ) -> None:
        self._extractors = extractors or [
            XlsxExtractor(),
            DocxExtractor(),
            PptxExtractor(),
            PdfExtractor(password=pdf_password),
        ]

    @property
    def extractors(self) -> tuple[BaseExtractor, ...]:
        return tuple(self._extractors)

    def get(self, detected: DetectedFileType) -> BaseExtractor:
        for extractor in self._extractors:
            if extractor.supports(detected):
                return extractor
        raise UnsupportedFileTypeError(
            f"No extractor is available for '{detected.document_type}'. Supported native types: "
            "PDF, DOCX/DOCM, XLSX/XLSM, PPTX/PPTM. Legacy DOC/XLS/PPT require LibreOffice conversion."
        )
