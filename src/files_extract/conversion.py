from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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
