# Capability matrix

Legend: **Yes** = normalized, **Asset** = raw binary is preserved/extracted, **Partial** = detected and recorded but not fully normalized.

| Capability | PDF | DOCX | XLSX | PPTX |
|---|---:|---:|---:|---:|
| Unit count | Yes pages | stored + rendered page count | Yes sheets | Yes slides |
| Reading/source order | Docling / fallback page text | Yes body block order | Yes row/cell order | Yes slide + shape z-order |
| Text | Yes | Yes | Yes | Yes |
| Tables | Docling | Yes incl. nested | Excel table definitions + cells | Yes |
| Formulas | Docling when recognized | text/equation objects remain text/OOXML | Yes | chart values/text |
| Comments/notes | annotations | Yes comments + foot/endnotes | Yes cell comments | Yes speaker notes; package comments Partial |
| Hyperlinks | Yes annotations | Yes paragraph hyperlinks | Yes cells | Yes run hyperlinks |
| Images/media | Asset | Asset | Asset | Asset |
| Charts | Docling where detected | Partial | Partial | Yes basic series/categories |
| SmartArt | n/a | Partial | n/a | Partial |
| OLE/embedded packages | PDF attachments Asset | Partial/detected | Partial/detected | Partial/detected |
| VBA | n/a | detected | detected | detected |
| OCR | Docling full install | via rendered PDF path not default | n/a | n/a |
| Legacy binary format | n/a | DOC via LibreOffice | XLS via LibreOffice | PPT via LibreOffice |

## Remaining fidelity work before a stable 1.0

- deeper chart normalization for Word/Excel;
- SmartArt graph normalization;
- richer OOXML object-to-asset relationship mapping;
- exact DOCX paragraph-to-rendered-page reconciliation rather than only page-count verification;
- password input support for encrypted PDFs/Office documents;
- performance/regression corpus using large real-world documents;
- Docker image smoke test with full Docling OCR models.
