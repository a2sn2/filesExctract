from __future__ import annotations

from pathlib import PurePosixPath

from .errors import DocumentValidationError
from .models import CanonicalDocument


def validate_document(document: CanonicalDocument) -> None:
    if not document.schema_version:
        raise DocumentValidationError("schema_version must not be empty")
    unit_indexes = [unit.index for unit in document.units]
    if len(unit_indexes) != len(set(unit_indexes)):
        raise DocumentValidationError("unit indexes must be unique")
    if any(index <= 0 for index in unit_indexes):
        raise DocumentValidationError("unit indexes must be positive")

    seen_element_ids: set[str] = set()
    valid_units = set(unit_indexes)
    for unit in document.units:
        orders: list[int] = []
        for element in unit.elements:
            if not element.element_id:
                raise DocumentValidationError("element_id must not be empty")
            if element.element_id in seen_element_ids:
                raise DocumentValidationError(f"duplicate element_id: {element.element_id}")
            seen_element_ids.add(element.element_id)
            orders.append(element.order)
            if element.source and element.source.unit_index is not None and element.source.unit_index not in valid_units:
                raise DocumentValidationError(f"element {element.element_id} references missing unit {element.source.unit_index}")
        if len(orders) != len(set(orders)):
            raise DocumentValidationError(f"element orders must be unique inside unit {unit.index}")

    asset_ids: set[str] = set()
    for asset in document.assets:
        if asset.asset_id in asset_ids:
            raise DocumentValidationError(f"duplicate asset_id: {asset.asset_id}")
        asset_ids.add(asset.asset_id)
        if asset.output_path:
            p = PurePosixPath(asset.output_path)
            if p.is_absolute() or ".." in p.parts:
                raise DocumentValidationError(f"unsafe asset output path: {asset.output_path}")
