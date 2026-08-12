# Canonical Document Schema

`files-extract` normalizes every supported source into the same top-level shape so downstream systems do not need format-specific logic.

## Top-level fields

- `schema_version`: version of the canonical representation.
- `metadata`: source identity, hash, detected type, extractor and source properties.
- `units`: ordered source units. A unit can be a page, sheet, slide or whole-document unit.
- `warnings`: extraction conditions that may affect completeness or interpretation.
- `unsupported_objects`: detected objects that are not fully represented yet. Nothing detectable should be silently discarded.
- `assets`: extracted binary assets and provenance references.

## Provenance

Every element may contain a `source` reference. Depending on source format it can include page number, sheet name, slide number, row, column, cell coordinate or a bounding box.

## Spreadsheet mapping

An XLSX workbook is represented as ordered `sheet` units. Each emitted cell is a `cell` element with its address, row/column coordinates, raw value, formula when present, cached formula value when available, data type, number format, hyperlink/comment metadata and hidden row/column state.

Worksheet-level metadata currently includes sheet state, dimensions, merged ranges, hidden rows/columns, freeze panes, filters, print settings, table definitions and data validations.
