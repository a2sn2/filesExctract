FilesExtract v0.4.0 — Windows x64 Full
=======================================

This distribution is designed to run without a separate Python installation.
It contains the FilesExtract application, a private Python runtime, modern Office/PDF parsers, Docling PDF layout/table models, Arabic + English Tesseract OCR data, and a private LibreOffice copy for legacy Office conversion and Word rendered pagination.

Use FilesExtract.exe for the graphical interface.

Command-line usage is also available:
  FilesExtract.exe --version
  FilesExtract.exe doctor --json
  FilesExtract.exe extract "C:\path\document.pdf"
  FilesExtract.exe batch "C:\path\documents" -o "C:\path\output" --recursive

The program never executes VBA, ActiveX or OLE content. Detected rich/unsupported objects are reported rather than silently discarded.

For encrypted PDF files, enter the password in the UI or use --password on the command line. Modern encrypted Office documents are detected explicitly; automatic Office decryption is not part of v0.4.0.

The bundled Docling models are used in offline mode. FilesExtract does not require model downloads at first use.
