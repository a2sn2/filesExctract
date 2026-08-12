from __future__ import annotations

import dataclasses
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Any


def to_json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            field.name: to_json_safe(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_json_safe(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return {"__bytes__": True, "length": len(value)}
    return value
