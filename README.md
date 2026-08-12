# filesExctract

Local-first document extraction engine for PDF, Word, Excel, and PowerPoint files.

The product goal is to extract document content while preserving structural context such as pages, sheets, slides, tables, cells, formulas, reading order, metadata and source references, then normalize the result into machine-friendly structured JSON and Markdown/text.

> Repository name is currently `filesExctract`. The installable Python package and CLI use the corrected product name `files-extract` / `files_extract`.

## Current milestone

The foundation and first native Excel extractor are implemented on the development branch.

Implemented now:

- Canonical document schema with provenance references.
- File type detection using signatures/OOXML package structure instead of extension alone.
- Extractor registry and validation layer.
- CLI with `inspect` and `extract` commands.
- JSON and Markdown renderers.
- XLSX/XLSM native extraction using openpyxl.
- Workbook/sheet metadata, ordered sheets and sheet visibility.
- Cell coordinates, values, formulas, cached formula values when present, data types and number formats.
- Comments and hyperlinks.
- Merged ranges, hidden rows/columns, freeze panes and filters.
- Excel table definitions and data validation rules.
- Detection/reporting of currently unsupported embedded charts/images, VBA projects and external workbook links rather than silently dropping them.
- Automated tests for detection, extraction and CLI output.

Planned next: asset extraction, deeper XLSX fidelity, DOCX, PPTX, PDF/Docling, OCR, LibreOffice conversion, Docker and CI.

## Requirements

- Python 3.11+

## Local setup

```bash
git clone https://github.com/a2sn2/filesExctract.git
cd filesExctract
git switch feat/foundation

python -m venv .venv
```

Activate the environment:

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### Linux/macOS

```bash
source .venv/bin/activate
```

Install the project:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

## Usage

Inspect a file:

```bash
files-extract inspect sample.xlsx
```

Extract a workbook:

```bash
files-extract extract sample.xlsx
```

By default the result is written next to the source file:

```text
sample_extracted/
├── document.json
└── document.md
```

Choose another output directory:

```bash
files-extract extract sample.xlsx -o output/sample
```

You can also run the CLI without the installed script entry point:

```bash
python -m files_extract extract sample.xlsx
```

## Output contract

`document.json` is the canonical machine-readable output. `document.md` is a human/LLM-friendly representation derived from the same canonical object.

The canonical JSON keeps source provenance so downstream code can trace extracted data back to a page/sheet/slide/cell. See [`docs/canonical-schema.md`](docs/canonical-schema.md).

## Completeness rule

Detected content that is not fully parsed must not disappear silently. The engine records partial or unsupported objects under `warnings` or `unsupported_objects`, which lets future validation and QA measure extraction completeness explicitly.
