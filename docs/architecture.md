# Architecture

## Pipeline

```text
input file
   ↓
signature + OOXML detection
   ↓
legacy Office? ── yes ──→ LibreOffice local conversion
   ↓ no                    ↓
extractor registry ←───────┘
   ↓
PDF / DOCX / XLSX / PPTX native extractor
   ↓
canonical document model
   ↓
validation
   ↓
JSON + Markdown + assets + manifest
```

## Canonical model

Every result contains:

- `metadata`: source identity, SHA-256, format, extractor/version and source properties;
- `units`: ordered `page`, `sheet`, `slide` or `document` units;
- `elements`: ordered content objects with source provenance;
- `assets`: embedded media/attachment references and checksums;
- `warnings`: recoverable fidelity/processing limitations;
- `unsupported_objects`: detected rich objects not fully normalized yet.

The schema deliberately keeps format-specific information inside `data`/`metadata` while exposing a stable top-level model to downstream code.

## Format strategy

### XLSX/XLSM

`openpyxl` is used for native workbook fidelity. Formula and data-only workbooks are opened in parallel so formulas and cached results can both be retained when cached values are present.

### DOCX/DOCM

`python-docx` provides the high-level object model. Direct OOXML reads supplement it for content such as footnotes/endnotes, text boxes, tracked changes and package-part detection. LibreOffice is used only for renderer-dependent pagination verification and legacy conversion.

### PPTX/PPTM

`python-pptx` provides slide/shape order, text, tables, charts, pictures and notes. Package inspection detects unsupported SmartArt/OLE/comment parts and VBA.

### PDF

Docling is the preferred semantic/layout backend when installed. Its reading-order items and provenance are normalized by page. `pypdf` always supplies low-level page metadata, annotations/links, forms, images, attachments and a fallback text extractor.

## Security boundaries

- Processing is local by default; the engine does not upload documents.
- File type detection checks signatures/package structure rather than trusting extensions.
- File size is bounded (512 MiB by default, configurable via CLI).
- Asset output paths are validated against path traversal.
- LibreOffice is run headless with an isolated temporary user profile and a timeout.
- Temporary conversion directories are removed automatically.
