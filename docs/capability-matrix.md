# Capability matrix

Legend: **Yes** = normalized, **Asset** = raw content preserved, **Partial** = detected/preserved but not fully normalized.

| Capability | PDF | DOCX/DOCM | XLSX/XLSM | PPTX/PPTM |
|---|---:|---:|---:|---:|
| Structural units | Yes pages | Yes document + rendered page map | Yes sheets | Yes slides |
| Native/source order | Yes | Yes body blocks/runs | Yes sheets/cells | Yes slides/shape z-order |
| Text | Yes | Yes | Yes | Yes |
| Tables | Docling | Yes + nested | Cells + Excel table definitions | Yes |
| Formulas/equations | Docling labels when recognized | Office Math text + raw XML context | Yes formulas + cached values | Chart values/text |
| Comments/notes | PDF annotations | Comments + foot/endnotes | Cell comments; threaded Partial | Speaker notes; package comments Partial |
| Hyperlinks | Yes | Yes | Yes | Yes |
| Headers/footers | Docling furniture + PDF page content | Yes | Yes | Master/layout/footer content retained |
| Images/media | Asset + page refs | Asset + run-order markers | Asset + anchors | Asset + shape refs |
| Charts | Docling where recognized | Partial + raw package part | Partial + raw package part | Basic chart normalization + raw part |
| SmartArt/diagrams | n/a | Partial + raw part | n/a | Partial + raw part |
| OLE/embedded packages | Attachments Asset | Asset + Partial semantics | Asset + Partial semantics | Asset + Partial semantics |
| VBA / ActiveX | n/a | Asset + detected | Asset + detected | Asset + detected |
| Forms | Yes PDF fields | Field instructions retained | Data validation rules | n/a |
| OCR | Docling + bundled Tesseract ara/eng in Windows Full | renderer path is not OCR by default | n/a | n/a |
| Legacy binary | n/a | DOC via LibreOffice | XLS via LibreOffice | PPT via LibreOffice |
| Encrypted input | Yes, password | Yes, password via msoffcrypto | Yes, password via msoffcrypto | Yes, password via msoffcrypto |

## Known semantic boundaries in v0.4.0

The engine does not claim semantic interpretation of every proprietary rich object. In particular, SmartArt graphs, VBA logic, ActiveX behavior, OLE application semantics, Excel pivot/slicer/query behavior and some chart models are preserved/detected but not fully normalized. This is explicit in `unsupported_objects` and raw assets rather than silently omitted.

Word native OOXML does not provide renderer-independent page boundaries. The engine retains native structure plus LibreOffice-rendered page text/count when available.
