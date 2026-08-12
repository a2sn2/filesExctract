FilesExtract v0.4.0 — Windows x64 Full
=======================================

This distribution is designed to run without a separate Python, Docling, Tesseract or LibreOffice installation.

It contains:
- FilesExtract.exe graphical desktop UI and CLI bridge
- private Python runtime and Office/PDF parsers
- Docling semantic PDF processing with ONNX Runtime CPU layout inference
- offline Docling layout/table artifacts
- Arabic + English Tesseract OCR
- private LibreOffice for legacy DOC/XLS/PPT and Word rendered pagination
- password-protected PDF and modern Office extraction
- integrity manifest, build information and exact Python runtime BOM

Use FilesExtract.exe without arguments for the graphical interface.

Command-line examples:
  FilesExtract.exe --version
  FilesExtract.exe doctor --json
  FilesExtract.exe extract "C:\path\document.pdf"
  FilesExtract.exe extract "C:\path\protected.xlsx" --password "password"
  FilesExtract.exe batch "C:\path\documents" -o "C:\path\output" --recursive

Security notes:
- the program never executes VBA, ActiveX or OLE content;
- detected rich/unsupported objects are reported rather than silently discarded;
- encrypted Office files are decrypted only into isolated temporary storage for extraction;
- passwords and decrypted intermediates are not written to output;
- the desktop UI does not put its password in the child extraction process command line;
- Docling models are bundled and used in offline mode.

Distribution signing:
The public repository does not contain a private Authenticode certificate. A tester build can therefore show an "unknown publisher" warning until a trusted signing certificate is configured externally for the release pipeline. Verify SHA256SUMS-WINDOWS-FULL.txt when distributing artifacts directly.
