# Changelog

## 0.4.0 - 2026-08-13

Windows Full product release.

- Added a self-contained Windows x64 desktop application with WinForms UI and CLI bridge.
- Added a private embedded Python runtime so end users do not need Python installed.
- Bundled offline Docling layout/table artifacts and selected ONNX Runtime CPU layout inference to avoid a Visual C++ compiler dependency on target PCs.
- Bundled Arabic + English Tesseract OCR data.
- Bundled a private LibreOffice runtime for `.doc/.xls/.ppt` conversion and Word rendered pagination.
- Added password-protected modern Office decryption through `msoffcrypto-tool`; decrypted intermediates are temporary and passwords are not persisted.
- Changed the desktop password hand-off so the password does not appear in the extraction child process command line.
- Added checksum-pinned external Windows runtime downloads, pinned OCR data revision, exact embedded Python runtime BOM and distribution integrity manifests.
- Added final-product smoke tests for modern Office, normal/scanned PDF, encrypted PDF, encrypted Office, legacy Office, Word pagination and the actual GUI launcher.
- Added portable ZIP and per-user installer packaging; CI silently installs the produced installer and repeats the product smoke against the installed copy.

## 0.3.0 - 2026-08-12

First production-ready extraction-engine release candidate validated through the full automated QA matrix.

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
