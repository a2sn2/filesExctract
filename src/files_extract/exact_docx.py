from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .errors import FilesExtractError

_MAX_POINTS = 22.0 * 72.0


@dataclass(slots=True)
class VisualPage:
    index: int
    width_pt: float
    height_pt: float
    png: bytes


def pdf_to_exact_docx(source: Path, output: Path, *, dpi: int = 216, password: str | None = None) -> int:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(str(source), password=password)
    except Exception as exc:
        raise FilesExtractError(f"Could not open PDF for conversion: {source.name}: {exc}") from exc

    pages: list[VisualPage] = []
    scale = max(72, min(int(dpi), 600)) / 72.0
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            width, height = page.get_size()
            bitmap = page.render(scale=min(scale, 6000.0 / max(width, height)))
            image = bitmap.to_pil()
            stream = io.BytesIO()
            image.save(stream, "PNG")
            image.close()
            pages.append(VisualPage(index + 1, float(width), float(height), stream.getvalue()))
    finally:
        pdf.close()

    _write_docx(pages, output)
    return len(pages)


def image_to_exact_docx(source: Path, output: Path) -> int:
    with Image.open(source) as image:
        image.load()
        dpi = image.info.get("dpi", (96.0, 96.0))
        try:
            x, y = float(dpi[0]), float(dpi[1])
            if x <= 1 or y <= 1:
                raise ValueError
        except Exception:
            x = y = 96.0
        width = image.width * 72.0 / x
        height = image.height * 72.0 / y
        converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        stream = io.BytesIO()
        converted.save(stream, "PNG")
        converted.close()
    _write_docx([VisualPage(1, width, height, stream.getvalue())], output)
    return 1


def _normalized(width: float, height: float) -> tuple[float, float]:
    factor = min(1.0, _MAX_POINTS / max(width, height))
    return width * factor, height * factor


def _write_docx(pages: list[VisualPage], output: Path) -> None:
    if not pages:
        raise FilesExtractError("No pages were available for Word conversion.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", _content_types())
        package.writestr("_rels/.rels", _root_rels())
        package.writestr("word/_rels/document.xml.rels", _document_rels(pages))
        package.writestr("word/document.xml", _document_xml(pages))
        for page in pages:
            package.writestr(f"word/media/page_{page.index}.png", page.png)


def _content_types() -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="png" ContentType="image/png"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>')


def _root_rels() -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')


def _document_rels(pages: list[VisualPage]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for page in pages:
        parts.append(f'<Relationship Id="rIdImage{page.index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/page_{page.index}.png"/>')
    parts.append('</Relationships>')
    return ''.join(parts)


def _section(width: int, height: int, *, next_page: bool) -> str:
    kind = '<w:type w:val="nextPage"/>' if next_page else ''
    orient = ' w:orient="landscape"' if width > height else ''
    return (f'<w:sectPr>{kind}<w:pgSz w:w="{width}" w:h="{height}"{orient}/>'
            '<w:pgMar w:top="0" w:right="0" w:bottom="0" w:left="0" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>')


def _document_xml(pages: list[VisualPage]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
             'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
             'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
             'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
             'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>']
    sizes = []
    for page in pages:
        width, height = _normalized(page.width_pt, page.height_pt)
        sizes.append((width, height))
        cx, cy = round(width * 12700), round(height * 12700)
        tw, th = round(width * 20), round(height * 20)
        parts.append('<w:p><w:pPr><w:spacing w:before="0" w:after="0"/>')
        if page.index < len(pages):
            parts.append(_section(tw, th, next_page=True))
        parts.append('</w:pPr><w:r><w:drawing>')
        parts.append('<wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="1" behindDoc="0" locked="1" layoutInCell="1" allowOverlap="1">')
        parts.append('<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH><wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>')
        parts.append(f'<wp:extent cx="{cx}" cy="{cy}"/><wp:wrapNone/><wp:docPr id="{page.index}" name="Source page {page.index}"/>')
        parts.append('<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr>')
        parts.append(f'<pic:cNvPr id="{page.index}" name="page_{page.index}.png"/><pic:cNvPicPr/></pic:nvPicPr>')
        parts.append(f'<pic:blipFill><a:blip r:embed="rIdImage{page.index}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>')
        parts.append(f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>')
        parts.append('</pic:pic></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r></w:p>')
    last_w, last_h = sizes[-1]
    parts.append(_section(round(last_w * 20), round(last_h * 20), next_page=False))
    parts.append('</w:body></w:document>')
    return ''.join(parts)
