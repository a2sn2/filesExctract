# Release checklist

Version `0.3.0` is release-ready when all checks below pass on the release commit and again on `main` after merge.

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
- [x] real Docling PDF smoke on clean CI
- [x] image-only OCR smoke on clean CI
- [x] Docker image build + doctor smoke

The checklist records the capabilities validated before the final release-doc commit. The same full GitHub Actions workflow must remain green for this commit and for the resulting `main` merge commit before the release is handed off for real-world user testing.
