# Windows EXE distribution

The Windows executable is built from the tested `files-extract` CLI with PyInstaller on a GitHub-hosted Windows runner.

## Build

Use the **Build Windows EXE** workflow (`.github/workflows/windows-exe.yml`) through `workflow_dispatch` or the packaging branch trigger.

The workflow:

1. installs the core package and PyInstaller;
2. builds `files-extract.exe` as a Windows x64 one-file executable;
3. smoke-tests `--version` and `doctor`;
4. creates and extracts generated XLSX, DOCX, PPTX and PDF fixtures through the EXE itself;
5. verifies canonical `document.json` and `manifest.json` output;
6. creates SHA-256 checksums;
7. uploads the EXE and portable ZIP as a GitHub Actions artifact.

## Runtime scope

The standalone core EXE embeds the Python runtime and native Python dependencies required for modern XLSX/XLSM, DOCX/DOCM, PPTX/PPTM and text-based PDF extraction.

LibreOffice, Tesseract and the full Docling/OCR backend are intentionally not embedded in the small standalone EXE. `files-extract.exe doctor --json` reports optional backend availability on the target machine.
