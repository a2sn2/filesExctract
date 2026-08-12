from __future__ import annotations

from .errors import DocumentValidationError
from .models import CanonicalDocument


def validate_document(document: CanonicalDocument) -> None:
    errors: list[str] = []

    if not document.schema_version:
        errors.append("schema_version is required")
    if not document.metadata.filename:
        errors.append("metadata.filename is required")
    if document.metadata.size_bytes < 0:
        errors.append("metadata.size_bytes must be >= 0")
    if len(document.metadata.sha256) != 64:
        errors.append("metadata.sha256 must be a 64-character hex digest")

    unit_indexes = [unit.index for unit in document.units]
    if any(index < 1 for index in unit_indexes):
        errors.append("unit indexes must start at 1")
    if len(set(unit_indexes)) != len(unit_indexes):
        errors.append("unit indexes must be unique")

    element_ids: set[str] = set()
    for unit in document.units:
        orders = [element.order for element in unit.elements]
        if len(orders) != len(set(orders)):
            errors.append(f"element orders must be unique within unit {unit.index}")
        for element in unit.elements:
            if not element.element_id:
                errors.append(f"element_id is required in unit {unit.index}")
            elif element.element_id in element_ids:
                errors.append(f"duplicate element_id: {element.element_id}")
            element_ids.add(element.element_id)
            if element.source and element.source.unit_index not in {None, unit.index}:
                errors.append(
                    f"element {element.element_id} points to unit {element.source.unit_index} "
                    f"but is stored in unit {unit.index}"
                )

    if errors:
        raise DocumentValidationError("Canonical document validation failed: " + "; ".join(errors))
