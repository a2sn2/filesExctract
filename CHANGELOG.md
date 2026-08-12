# Changelog

## 0.3.0 - 2026-08-12

First production-ready release candidate validated through the full automated QA matrix.

- Added native structured extraction for DOCX/DOCM and PPTX/PPTM.
- Added PDF extraction with Docling primary backend and pypdf fallback/augmentation.
- Added legacy DOC/XLS/PPT conversion through LibreOffice.
- Added Word renderer-derived page mapping.
- Added embedded media, PDF image/attachment and OOXML rich-part asset output.
- Added comments, notes, headers/footers, content controls, tracked changes, equations and accessibility metadata.
- Added PDF password support and explicit encrypted modern Office detection.
- Added source/archive resource limits and safe asset validation.
- Added batch extraction, environment diagnostics, manifest checksums and Docker support.
- Expanded CI across Python 3.11/3.12/3.13, LibreOffice, real Docling/OCR conversion and Docker.
