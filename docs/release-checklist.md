# Release checklist

A release candidate is acceptable only when all of the following are true.

## Functional

- [x] PDF page/text/link/image/attachment extraction
- [x] Docling layout/table/OCR implementation
- [x] DOCX ordered text/tables/comments/headers/footers/notes/media
- [x] XLSX sheets/cells/formulas/comments/links/tables/media
- [x] PPTX slides/z-order/text/tables/charts/notes/media
- [x] DOC/XLS/PPT LibreOffice conversion
- [x] Canonical JSON and Markdown
- [x] Asset materialization and manifest checksums
- [x] Batch extraction with per-file failure reporting

## Safety

- [x] content-based type detection
- [x] encrypted modern Office detection
- [x] encrypted PDF password path
- [x] source file-size limit
- [x] archive expanded-size/member limits
- [x] safe asset paths
- [x] isolated LibreOffice profile and timeout

## Automated QA

- [x] Python 3.11 matrix
- [x] Python 3.12 matrix
- [x] Python 3.13 matrix
- [x] package build
- [x] LibreOffice integration tests
- [ ] real Docling PDF smoke on clean CI
- [ ] image-only OCR smoke on clean CI
- [ ] Docker image build + doctor smoke

The last three boxes are checked only after the corresponding GitHub Actions jobs succeed for the release commit.
