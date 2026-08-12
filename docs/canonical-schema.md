# Canonical Document Schema v1.1

Every source format is normalized to the same top-level object.

```text
CanonicalDocument
├── schema_version
├── metadata
├── units[]
│   ├── index
│   ├── kind: document | page | sheet | slide
│   ├── name
│   ├── metadata
│   └── elements[]
├── assets[]
├── warnings[]
└── unsupported_objects[]
```

## Metadata

`metadata` identifies the original source rather than a temporary converted file. It includes source filename, extension/type, media type, byte size, SHA-256, extractor identity/version and format-specific properties.

## Units

A unit is the stable structural container of a source:

- PDF → `page`
- XLSX/XLSM → `sheet`
- PPTX/PPTM → `slide`
- DOCX/DOCM → `document` because native Word content is flow-based rather than page-bound

For Word, stored and LibreOffice-rendered page counts are preserved under `metadata.properties.word`; exact paragraph-to-rendered-page reconciliation is tracked separately from native block order.

## Elements

Each element has a globally unique `element_id`, an order within its unit, a broad `element_type`, optional text/Markdown, format-specific `data`, optional child elements and source provenance.

Element types include headings, paragraphs, lists, tables, cells, images, links, notes, formulas, code, metadata and other rich objects.

## Provenance

`SourceReference` can point to page, sheet, slide, row, column, cell coordinate, bounding box or an OOXML archive part. Bounding boxes include a coordinate-system label because PDF/layout engines can use different origins.

## Assets

An asset reference contains an ID, media type, original/output name, SHA-256, byte size and source metadata. The CLI materializes safe asset paths under the extraction output directory.

## Completeness

- `warnings` records recoverable extraction/fidelity limitations.
- `unsupported_objects` records detected rich content that is not fully normalized.

The engine's contract is that detectable unsupported content is reported rather than silently discarded.
