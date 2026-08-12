# filesExctract

`files-extract` is a local-first extraction engine and desktop product for PDF, Word, Excel and PowerPoint documents. It produces canonical structured JSON plus Markdown while retaining source structure, provenance, embedded assets and explicit completeness warnings.

> The GitHub repository is currently named `filesExctract`. The Python package and CLI intentionally use the corrected names `files_extract` and `files-extract`.

## Windows Full v0.4

The full Windows x64 distribution is designed for end users and does **not** require a separate Python, LibreOffice, Tesseract or Docling installation. It includes:

- a WinForms desktop UI with drag/drop, multi-file extraction, output selection, diagnostics and logs;
- a private embedded Python 3.12 runtime;
- native XLSX/XLSM, DOCX/DOCM and PPTX/PPTM extraction;
- Docling semantic PDF extraction using an ONNX Runtime CPU layout backend so target PCs do not need Visual Studio/MSVC at runtime;
- offline Docling layout/table models;
- bundled Tesseract OCR with Arabic (`ara`) and English (`eng`) data;
- bundled private LibreOffice for legacy `.doc/.xls/.ppt` and Word rendered pagination;
- encrypted PDF and password-protected modern Office decryption;
- installer and portable ZIP outputs with SHA-256 integrity manifests and an exact embedded Python runtime BOM.

The desktop UI passes document passwords to its private extraction child through the process environment rather than placing the password in the child command line. Passwords and decrypted Office intermediates are not written to the output package.

## What it preserves

- **PDF:** page count/order, semantic reading order, tables, OCR text, headers/footers/furniture, bounding boxes, annotations, links, form fields, outline, images and attachments.
- **Word:** native block order, paragraphs/runs/formatting, headings/lists, hyperlinks, tables/nested tables, comments, headers/footers, sections, footnotes/endnotes, text boxes, tracked changes, content controls, field instructions, Office Math text, embedded media and renderer-derived page references.
- **Excel:** ordered/hidden sheets, cells/coordinates, values, formulas and cached values when present, number formats/styles, comments, hyperlinks, merged ranges, hidden rows/columns, tables, validation rules, headers/footers, dimensions, filters, freeze panes, print metadata and embedded media.
- **PowerPoint:** ordered/hidden slides, shape z-order/geometry, text/runs/hyperlinks, tables, charts, pictures, speaker notes, accessibility text and inherited layout/master content.
- **Legacy Office:** `.doc`, `.xls` and `.ppt` are converted locally through the bundled LibreOffice runtime, then passed through the corresponding native extraction path.
- **Rich/unsupported objects:** SmartArt, VBA, ActiveX, OLE/embedded packages, pivot/query/slicer definitions and similar components are detected rather than silently disappearing; raw binary/package parts are preserved as assets where practical. Active content is never executed.

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

## Windows usage

The full distribution provides `FilesExtract.exe`. Run it without arguments for the graphical interface. The same executable also exposes the CLI bridge:

```powershell
FilesExtract.exe --version
FilesExtract.exe doctor --json
FilesExtract.exe extract "C:\documents\report.xlsx"
FilesExtract.exe extract "C:\documents\protected.docx" --password "your-password"
FilesExtract.exe batch "C:\documents" -o "C:\output" --recursive
```

A public repository cannot safely store a private Authenticode signing certificate. Unless a trusted signing certificate is configured separately for the release pipeline, Windows may identify tester builds as an unknown publisher even though SHA-256 checksums are supplied. This is a distribution-signing boundary, not an extraction-runtime dependency.

## Source installation

Requirements for source/developer use:

- Python 3.11+
- LibreOffice for `.doc/.xls/.ppt` and rendered Word pagination
- Docling for semantic PDF layout/table/OCR
- Tesseract when using the preferred Arabic/English OCR path

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

Check the environment:

```bash
files-extract doctor --json
```

## CLI

```bash
files-extract inspect report.xlsx
files-extract extract report.xlsx
files-extract extract protected.pdf --password "your-password"
files-extract extract protected.xlsx --password "your-password"
files-extract batch ./documents -o ./output --recursive
```

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

DOCX is a flow document; final page boundaries depend on the renderer, installed fonts and page settings. `files-extract` therefore retains the native ordered Word model and, when LibreOffice is available, adds rendered page count/text under `metadata.properties.word.pagination`. It does not pretend OOXML contains a renderer-independent paragraph-to-page map.

## PDF strategy

With the `full` extra, Docling is the primary semantic PDF backend. FilesExtract configures the Heron layout model through ONNX Runtime on CPU for a portable runtime that does not require a C++ compiler on the target PC. `pypdf` augments the result with low-level PDF information such as annotations, forms, images and attachments. If the semantic backend fails, extraction can fall back to `pypdf` and records the degradation in warnings.

## Security and resource controls

- local processing by default; the extraction engine does not upload source documents;
- signature/OOXML-aware type detection rather than trusting extensions alone;
- password-protected PDF and modern Office support;
- encrypted Office intermediates are isolated in temporary storage and deleted after extraction;
- source size and OOXML expanded-size/member limits;
- safe asset paths and path-traversal checks;
- timeout-bound, isolated headless LibreOffice execution;
- VBA/ActiveX/OLE assets are marked as potentially active and never executed;
- desktop password delivery avoids child-process command-line exposure;
- Windows full bundle pins external binary downloads/checksums and records its runtime BOM.

## Tests

```bash
pytest -m "not integration and not docling"
pytest -m integration
pytest -m docling
```

CI covers Python 3.11/3.12/3.13, package build, LibreOffice integration, real Docling/OCR conversion, Docker, and the final Windows full product. The Windows full job builds the portable distribution, extracts generated XLSX/DOCX/PPTX/PDF fixtures, tests image-only OCR, encrypted PDF, encrypted Office, legacy DOC/XLS/PPT, launches the real GUI, builds the installer, silently installs it on a clean runner, and repeats the full product smoke against the installed copy.

## Completeness contract

The core rule is: **detected content must not silently disappear**. Normalized content is stored in canonical elements. Raw binaries/package parts are extracted when practical. Features that cannot yet be faithfully normalized are listed in `unsupported_objects`, and recoverable degradation is listed in `warnings`.

See:

- [`docs/canonical-schema.md`](docs/canonical-schema.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/capability-matrix.md`](docs/capability-matrix.md)
- [`docs/release-checklist.md`](docs/release-checklist.md)
