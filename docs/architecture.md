# Architecture

## Pipeline

```text
input file
   ↓
signature / OLE / OOXML detection
   ↓
resource & archive safety checks
   ↓
legacy Office? ── yes ──→ isolated LibreOffice conversion
   ↓ no                    ↓
extractor registry ←───────┘
   ↓
PDF / DOCX / XLSX / PPTX extractor
   ↓
canonical document + assets + warnings
   ↓
provenance completion + validation
   ↓
document.json + document.md + assets/ + manifest.json
```

## Format strategy

### Excel

`openpyxl` reads the workbook twice: formula mode and data-only mode. This lets the canonical cell retain the formula together with a cached result when Excel stored one. Package inspection supplements the library for VBA, pivot/query/slicer and other rich parts.

### Word

`python-docx` supplies ordered body blocks, comments, sections, stories and high-level formatting. Direct OOXML inspection supplements it for footnotes/endnotes, text boxes, tracked changes, content controls, field instructions, Office Math and unsupported package parts. Run inner-content markers keep embedded pictures in run order. LibreOffice rendering provides renderer-derived page boundaries.

### PowerPoint

`python-pptx` supplies slide order, shapes, z-order, text, tables, charts, pictures and notes. The extractor also records accessibility text and inherited layout/master content. OOXML inspection detects SmartArt, comments, OLE and VBA.

### PDF

Docling is the preferred layout/OCR/table backend. `pypdf` is always used for low-level PDF features and as the fallback text backend. When Tesseract Arabic/English is installed, Docling is configured to prefer those OCR languages; otherwise Docling chooses an available OCR backend.

## Canonical model

All formats share:

- source metadata and SHA-256;
- ordered structural units;
- ordered elements with source provenance;
- asset references with hashes and archive/page provenance;
- warnings and unsupported-object declarations.

Format-specific detail remains in `data`/`metadata` so the common schema does not discard fidelity.

## Security boundaries

- no source-document upload is performed by the engine;
- file size and OOXML expanded-size/member limits are enforced before parsing;
- asset output paths are validated;
- LibreOffice runs headless in an isolated temporary profile with timeout;
- potentially active extracted content is marked and never executed;
- passwords are never serialized to canonical output.
