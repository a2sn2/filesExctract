class FilesExtractError(Exception):
    """Base error for the extraction engine."""


class UnsupportedFileTypeError(FilesExtractError):
    """Raised when no extractor is available for the detected file type."""


class InvalidInputFileError(FilesExtractError):
    """Raised when the input path is invalid or unreadable."""


class ExtractionFailedError(FilesExtractError):
    """Raised when an extractor fails to parse a supported file."""


class DocumentValidationError(FilesExtractError):
    """Raised when canonical output violates required invariants."""
