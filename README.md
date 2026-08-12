# filesExctract

`files-extract` is a local-first document extraction engine for PDF, Word, Excel and PowerPoint files. It converts source documents into a common structured JSON model plus Markdown while preserving source units (pages/sheets/slides), order, tables, cells, formulas, notes, links, metadata, embedded media references and explicit completeness warnings.

> The repository is currently named `filesExctract`. The Python package and command use the corrected names `files_extract` and `files-extract`.

## Supported formats

| Format | Native extraction | Structural unit | Notes |
|---|---|---|---|
| PDF | Yes | page | Docling when installed, pypdf fallback; images, links, forms, metadata, attachments |
| DOCX / DOCM | Yes | document | paragraphs, runs, headings, lists, tables/nested tables, comments, headers/footers, sections, foot/endnotes, text boxes, revisions, media |
| XLSX / XLSM | Yes | sheet | cells, formulas/cached values, comments, hyperlinks, merged ranges, hidden rows/columns/sheets, tables, validations, media |
| PPTX / PPTM | Yes | slide | shape z-order, text/runs, tables, charts, notes, pictures, hidden slides, media |
| DOC / XLS / PPT | Yes via LibreOffice | corresponding modern unit | converted locally before extraction |

## Output package

For `sample.xlsx`, the default output is:

```text
sample_extracted/
├── document.json
├── document.md
├── manifest.json
└── assets/
    └── ...embedded media and PDF attachments/images...
```

`document.json` is the canonical machine-readable result. `document.md` is derived from the same canonical object for humans, RAG and LLM workflows. `manifest.json` contains counts plus SHA-256 checksums for written outputs.

## Install

Python 3.11+ is required.

### Core

Core extraction works for all four modern families. PDF uses pypdf when Docling is not installed.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Full PDF/OCR backend

For semantic PDF layout/table processing and OCR support, install the full extra:

```bash
pip install -e ".[full,dev]"
```

Docling is used automatically when available. If it is absent or conversion fails, PDF extraction falls back to pypdf and records that fact in `warnings`.

### LibreOffice

LibreOffice is optional for modern files but required for:

- legacy `.doc`, `.xls`, `.ppt` conversion;
- rendered Word page-count verification.

Check the machine:

```bash
files-extract doctor
```

## CLI

Inspect only:

```bash
files-extract inspect sample.xlsx
```

Extract one file:

```bash
files-extract extract sample.xlsx
```

Choose an output directory:

```bash
files-extract extract sample.docx -o output/sample
```

Do not write embedded assets:

```bash
files-extract extract sample.pptx --no-assets
```

Skip LibreOffice Word page rendering:

```bash
files-extract extract sample.docx --no-render-word-pages
```

Batch extraction:

```bash
files-extract batch ./documents -o ./output --recursive
```

Environment diagnostics:

```bash
files-extract doctor --json
```

## Completeness contract

Detected content must not silently disappear. Content that can be represented is emitted as canonical elements/assets. Rich objects that are only partially normalized are listed under `unsupported_objects`; recoverable extraction limitations are listed under `warnings`.

Examples include VBA projects, unresolved external workbook links, SmartArt, OLE packages and cases where Docling/OCR is unavailable.

## Word pagination

DOCX is flow-based, so paragraph-to-page mapping is renderer-dependent. The extractor preserves Word's stored extended page count when present and, by default, asks LibreOffice to render the document to PDF and records the rendered page count. A mismatch is reported as a warning rather than hidden.

## Development and tests

```bash
pytest
```

Run only fast tests:

```bash
pytest -m "not integration"
```

Run LibreOffice integration tests:

```bash
pytest -m integration
```

The test corpus is generated during tests, so the repository does not need to ship private documents.

See `docs/architecture.md` and `docs/capability-matrix.md` for the internal design and fidelity status.
