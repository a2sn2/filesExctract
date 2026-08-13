# FilesExtract Mobile for Android

FilesExtract Mobile is the Android implementation of the document-extraction product. It is intentionally not a wrapper around the Windows executable.

## Supported inputs

- PDF (`.pdf`): per-page text extraction with PDFBox-Android and on-device ML Kit OCR fallback for scanned/blank-text pages.
- Word (`.docx`): paragraphs/runs, tables, hyperlinks, headers, footers, comments, footnotes/endnotes, stored page count, document properties, media assets and explicit page breaks.
- Excel (`.xlsx`, `.xlsm`): worksheets, cell coordinates/values/formulas, shared strings, merged ranges, hidden rows, hyperlinks, validations, comments, table definitions, workbook properties and media assets. VBA is detected but never executed.
- PowerPoint (`.pptx`): slide order, shapes/text, tables, pictures, charts/cached values, speaker notes, document properties and media assets.

Output is written as `document.json`, `document.md`, `manifest.txt` and an optional `assets/` directory.

## Safety

The app processes files locally and requests no network permission. It enforces mobile limits for input size, ZIP entries, total uncompressed OOXML data, PDF pages and OCR pages. XML DTD/external entities are disabled. Macros and embedded OLE/package objects are never executed.

## Fidelity note

Android has no Microsoft Office/LibreOffice layout engine. For DOCX, stored page count and explicit page breaks are preserved, but exact rendered paragraph-to-page mapping is not fabricated. For visually complex PDF tables/layouts, the desktop Docling engine remains the higher-fidelity path.

## Build

```bash
gradle -p android testDebugUnitTest lintDebug assembleRelease
```

The release branch is validated by `.github/workflows/android-full.yml`, including a real Android emulator extraction smoke test for PDF, DOCX, XLSX and PPTX.
