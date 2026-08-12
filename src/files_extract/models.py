from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .serialization import to_json_safe

SCHEMA_VERSION = "1.0"


class UnitKind(str, Enum):
    DOCUMENT = "document"
    PAGE = "page"
    SHEET = "sheet"
    SLIDE = "slide"


class ElementType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    CELL = "cell"
    IMAGE = "image"
    LINK = "link"
    NOTE = "note"
    METADATA = "metadata"
    OTHER = "other"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float
    coordinate_system: str | None = None


@dataclass(slots=True)
class SourceReference:
    unit_index: int | None = None
    unit_name: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None
    slide_number: int | None = None
    row: int | None = None
    column: int | None = None
    cell: str | None = None
    bbox: BoundingBox | None = None


@dataclass(slots=True)
class ExtractionWarning:
    code: str
    message: str
    severity: Severity = Severity.WARNING
    source: SourceReference | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UnsupportedObject:
    object_type: str
    status: str
    description: str | None = None
    source: SourceReference | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AssetReference:
    asset_id: str
    asset_type: str
    original_name: str | None = None
    output_path: str | None = None
    media_type: str | None = None
    source: SourceReference | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentElement:
    element_id: str
    element_type: ElementType
    order: int
    text: str | None = None
    markdown: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    source: SourceReference | None = None
    children: list["DocumentElement"] = field(default_factory=list)


@dataclass(slots=True)
class DocumentUnit:
    index: int
    kind: UnitKind
    name: str | None = None
    elements: list[DocumentElement] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentMetadata:
    filename: str
    extension: str
    document_type: str
    media_type: str | None
    size_bytes: int
    sha256: str
    extractor: str
    extractor_version: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalDocument:
    metadata: DocumentMetadata
    units: list[DocumentUnit]
    schema_version: str = SCHEMA_VERSION
    warnings: list[ExtractionWarning] = field(default_factory=list)
    unsupported_objects: list[UnsupportedObject] = field(default_factory=list)
    assets: list[AssetReference] = field(default_factory=list)

    @property
    def unit_count(self) -> int:
        return len(self.units)

    def to_dict(self) -> dict[str, Any]:
        return to_json_safe(self)
