from __future__ import annotations

import importlib
import platform
import sys
from typing import Any

from .libreoffice import find_libreoffice, libreoffice_version


def _module_version(module_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        return {"available": True, "version": getattr(module, "__version__", None)}
    except Exception as exc:
        return {"available": False, "version": None, "error": str(exc)}


def environment_report() -> dict[str, Any]:
    lo = find_libreoffice()
    return {
        "python": {"version": platform.python_version(), "executable": sys.executable, "platform": platform.platform()},
        "dependencies": {
            "openpyxl": _module_version("openpyxl"),
            "python-docx": _module_version("docx"),
            "python-pptx": _module_version("pptx"),
            "pypdf": _module_version("pypdf"),
            "docling": _module_version("docling"),
        },
        "external_tools": {
            "libreoffice": {"available": bool(lo), "path": lo, "version": libreoffice_version() if lo else None},
        },
    }
