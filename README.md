# filesExctract

`files-extract` is a local-first extraction engine for PDF, Word, Excel and PowerPoint documents. It produces a canonical structured JSON representation plus Markdown while retaining source structure, provenance, embedded assets and explicit completeness warnings.

> The GitHub repository is currently named `filesExctract`. The installable Python package and CLI intentionally use the corrected names `files_extract` and `files-extract`.

## What it preserves

- **PDF:** page count, page order, semantic reading order with Docling, tables, OCR text, headers/footers/furniture, bounding boxes, annotations, links, form fields, outline, images and attachments.
- **Word:** native block order, paragraphs/runs/formatting, headings/lists, hyperlinks, tables and nested tables, comments, headers/footers, sections, footnotes/endnotes, text boxes, tracked changes, content controls, field instructions, Office Math text, embedded media and renderer-derived page boundaries.
- **Excel:** ordered/hidden sheets, cells and coordinates, values, formulas and cached values when present, number formats/styles, comments, hyperlinks, merged ranges, hidden rows/columns, tables, validation rules, headers/footers, row/column dimensions, filters, freeze panes, print metadata and embedded media.
- **PowerPoint:** ordered/hidden slides, shape z-order and geometry, text/runs/hyperlinks, tables, charts, pictures, speaker notes, accessibility text and inherited layout/master content.
- **Legacy Office:** `.doc`, `.xls` and `.ppt` are converted locally through LibreOffice and then passed through the same native extractors.
- **Rich/unsupported objects:** SmartArt, VBA, ActiveX, OLE/embedded packages, pivot/query/slicer definitions and similar components are detected instead of disappearing silently; binary/raw package parts are preserved as assets where practical.

## Output package

For `sample.xlsx`:

```text
sample_extracted/
├── document.json
├── document.md
├── manifest.json
└── assets/
    ├── media/
    ├── embeddings/
    ├── macros/
    └── package-parts/
```

`document.json` is the canonical machine-readable contract. `document.md` is generated from the same canonical object for humans, search, RAG and LLM workflows. `manifest.json` records output counts, file sizes and SHA-256 checksums.

## Requirements

- Python 3.11+
- LibreOffice is optional for modern Office files and required for `.doc/.xls/.ppt` plus Word rendered-pagination verification.
- Docling is optional but strongly recommended for semantic PDF layout, table extraction and OCR.
- Tesseract is preferred when available for Arabic/English OCR. The Docker image installs both `ara` and `eng` language data.

## Local installation

```bash
git clone https://github.com/a2sn2/filesExctract.git
cd filesExctract
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[full,dev]"
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[full,dev]"
```

If you only need the lightweight core, omit `full`:

```bash
pip install -e ".[dev]"
```

Check the local environment:

```bash
files-extract doctor --json
```

## CLI

Inspect a source without extracting it:

```bash
files-extract inspect report.xlsx
```

Extract one file:

```bash
files-extract extract report.xlsx
```

Choose an output directory:

```bash
files-extract extract contract.docx -o output/contract
```

Extract an encrypted PDF:

```bash
files-extract extract protected.pdf --password "your-password"
```

The password is used in memory and is not written to `document.json`, Markdown or the manifest.

Batch extraction:

```bash
files-extract batch ./documents -o ./output --recursive
```

Batch output includes `batch-summary.json`; one failed document does not stop the remaining documents.

Useful controls:

```text
--no-assets
--no-render-word-pages
--max-file-size-mb 512
--max-archive-uncompressed-mb 2048
--max-archive-members 100000
--max-archive-member-mb 1024
--libreoffice-timeout 180
```

## Word pagination

DOCX is a flow document; the final page boundaries depend on the renderer, installed fonts and page settings. `files-extract` therefore keeps two complementary views:

1. native ordered Word elements and tables;
2. when LibreOffice is available, a rendered PDF page count plus per-page extracted text stored under `metadata.properties.word.pagination` and appended to Markdown as a pagination reference.

This avoids pretending that OOXML itself contains a universally exact paragraph-to-page mapping.

## PDF strategy

When the `full` extra is installed, Docling is the primary PDF backend and performs layout analysis, table reconstruction and OCR. `pypdf` always augments the result with low-level PDF information such as annotations, form fields, images and attachments. If Docling is unavailable or fails, extraction falls back to `pypdf` and records the degradation under `warnings`.

The full Docker/CI path uses Tesseract Arabic + English when those language packs are available.

## Security and resource controls

- Processing is local by default; source documents are not uploaded by this project.
- Detection uses file signatures and OOXML package structure instead of trusting extensions alone.
- Modern password-protected Office containers are detected explicitly rather than misclassified as legacy files. Automatic Office decryption is not implemented in v0.3.0.
- PDF passwords are supported through `--password`.
- Source size and OOXML expanded-size/member limits protect against uncontrolled archive expansion.
- Asset paths are normalized and validated against path traversal.
- LibreOffice runs headless with an isolated temporary user profile and a timeout.
- Extracted VBA/ActiveX/OLE assets are marked as potentially active content; the engine never executes them.

## Tests

Fast/core tests:

```bash
pytest -m "not integration and not docling"
```

LibreOffice integration tests:

```bash
pytest -m integration
```

Full Docling/OCR smoke tests:

```bash
pytest -m docling
```

GitHub Actions tests Python 3.11, 3.12 and 3.13, LibreOffice legacy conversions, package building, real Docling/OCR conversion and Docker image construction.

## Completeness contract

The core rule is: **detected content must not silently disappear**.

Normalized content is stored in canonical elements. Raw binaries/package parts are extracted when practical. Features that cannot yet be faithfully normalized are listed in `unsupported_objects`, and recoverable degradation is listed in `warnings`.

See:

- [`docs/canonical-schema.md`](docs/canonical-schema.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/capability-matrix.md`](docs/capability-matrix.md)
- [`docs/release-checklist.md`](docs/release-checklist.md)
