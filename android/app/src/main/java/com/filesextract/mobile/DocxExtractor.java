package com.filesextract.mobile;

import android.content.Context;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import java.io.File;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class DocxExtractor implements MobileExtractor {
    @Override
    public Models.DocumentResult extract(Context context, File input, String filename, Models.ExtractionOptions options) throws Exception {
        Models.DocumentResult out = new Models.DocumentResult();
        out.unitType = "document";
        out.metadata.put("format", "OOXML Wordprocessing Document");
        try (SafeZip zip = new SafeZip(input, options)) {
            byte[] mainXml = zip.read("word/document.xml");
            if (mainXml == null) throw new IllegalArgumentException("Invalid DOCX: word/document.xml is missing.");
            Map<String, OoxmlRelations.Rel> rels = OoxmlRelations.parse(zip.read("word/_rels/document.xml.rels"));
            Models.Unit unit = new Models.Unit(1, "Document");
            int order = parseBody(XmlUtil.parse(mainXml), unit, rels);
            out.units.add(unit);

            order = appendRelatedParts(zip, rels, unit, order, out);
            appendStoredProperties(zip, out);
            XlsxExtractor.collectAssets(zip, "word/media/", out);

            if (zip.has("word/vbaProject.bin")) out.unsupportedObjects.add("VBA project detected (preserved in source, not executed or parsed on Android).");
            if (!zip.namesWithPrefix("word/embeddings/").isEmpty()) {
                out.unsupportedObjects.add("Embedded OLE/package objects detected under word/embeddings; binary payload is not interpreted on Android.");
            }
            out.warnings.add("DOCX page count is preserved from document properties when available; exact rendered paragraph-to-page mapping requires a desktop layout engine and is not fabricated on Android.");
        }
        return out;
    }

    private int parseBody(Document doc, Models.Unit unit, Map<String, OoxmlRelations.Rel> rels) {
        List<Element> bodies = XmlUtil.descendants(doc.getDocumentElement(), "body");
        if (bodies.isEmpty()) return 0;
        Element body = bodies.get(0);
        int order = 0;
        NodeList nodes = body.getChildNodes();
        for (int i = 0; i < nodes.getLength(); i++) {
            Node n = nodes.item(i);
            if (!(n instanceof Element)) continue;
            String local = XmlUtil.local(n);
            if ("p".equals(local)) {
                Models.Element p = paragraph((Element) n, ++order, rels);
                unit.elements.add(p);
            } else if ("tbl".equals(local)) {
                unit.elements.add(table((Element) n, ++order, rels));
            } else if ("sectPr".equals(local)) {
                Models.Element s = new Models.Element(++order, "section_properties", "");
                fillSectionProperties((Element) n, s);
                unit.elements.add(s);
            }
        }
        return order;
    }

    private Models.Element paragraph(Element p, int order, Map<String, OoxmlRelations.Rel> rels) {
        StringBuilder text = new StringBuilder();
        List<Map<String, Object>> runs = new ArrayList<>();
        boolean pageBreak = false;
        for (Element r : XmlUtil.descendants(p, "r")) {
            StringBuilder runText = new StringBuilder();
            for (Element t : XmlUtil.descendants(r, "t")) runText.append(t.getTextContent());
            for (Element tab : XmlUtil.descendants(r, "tab")) runText.append('\t');
            for (Element br : XmlUtil.descendants(r, "br")) {
                String type = XmlUtil.attr(br, "type");
                if ("page".equals(type)) pageBreak = true;
                runText.append('\n');
            }
            String value = runText.toString();
            text.append(value);
            if (!value.isEmpty()) {
                Map<String, Object> rd = new LinkedHashMap<>();
                rd.put("text", value);
                Element rPr = XmlUtil.firstChild(r, "rPr");
                if (rPr != null) {
                    rd.put("bold", !XmlUtil.children(rPr, "b").isEmpty());
                    rd.put("italic", !XmlUtil.children(rPr, "i").isEmpty());
                    rd.put("underline", !XmlUtil.children(rPr, "u").isEmpty());
                    Element color = XmlUtil.firstChild(rPr, "color");
                    if (color != null) rd.put("color", XmlUtil.attr(color, "val"));
                    Element sz = XmlUtil.firstChild(rPr, "sz");
                    if (sz != null) rd.put("size_half_points", XmlUtil.attr(sz, "val"));
                }
                runs.add(rd);
            }
        }
        Models.Element e = new Models.Element(order, "paragraph", text.toString());
        e.data.put("runs", runs);
        Element pPr = XmlUtil.firstChild(p, "pPr");
        if (pPr != null) {
            Element style = XmlUtil.firstChild(pPr, "pStyle");
            if (style != null) e.data.put("style", XmlUtil.attr(style, "val"));
            Element numPr = XmlUtil.firstChild(pPr, "numPr");
            if (numPr != null) {
                Element ilvl = XmlUtil.firstChild(numPr, "ilvl");
                Element numId = XmlUtil.firstChild(numPr, "numId");
                if (ilvl != null) e.data.put("list_level", XmlUtil.attr(ilvl, "val"));
                if (numId != null) e.data.put("list_id", XmlUtil.attr(numId, "val"));
            }
            Element jc = XmlUtil.firstChild(pPr, "jc");
            if (jc != null) e.data.put("alignment", XmlUtil.attr(jc, "val"));
        }
        if (pageBreak) e.data.put("explicit_page_break", true);

        List<Map<String, String>> links = new ArrayList<>();
        for (Element h : XmlUtil.descendants(p, "hyperlink")) {
            String rid = XmlUtil.relationshipId(h);
            String anchor = XmlUtil.attr(h, "anchor");
            Map<String, String> link = new LinkedHashMap<>();
            link.put("text", XmlUtil.descendantText(h, "t"));
            if (!anchor.isEmpty()) link.put("anchor", anchor);
            if (!rid.isEmpty() && rels.containsKey(rid)) link.put("target", rels.get(rid).target);
            links.add(link);
        }
        if (!links.isEmpty()) e.data.put("hyperlinks", links);
        return e;
    }

    private Models.Element table(Element tbl, int order, Map<String, OoxmlRelations.Rel> rels) {
        Models.Element e = new Models.Element(order, "table", "");
        List<List<String>> rows = new ArrayList<>();
        for (Element tr : XmlUtil.children(tbl, "tr")) {
            List<String> cells = new ArrayList<>();
            for (Element tc : XmlUtil.children(tr, "tc")) {
                StringBuilder cell = new StringBuilder();
                NodeList children = tc.getChildNodes();
                for (int i = 0; i < children.getLength(); i++) {
                    Node n = children.item(i);
                    if (!(n instanceof Element)) continue;
                    if ("p".equals(XmlUtil.local(n))) {
                        if (cell.length() > 0) cell.append('\n');
                        cell.append(paragraph((Element) n, 0, rels).text);
                    } else if ("tbl".equals(XmlUtil.local(n))) {
                        if (cell.length() > 0) cell.append('\n');
                        cell.append("[nested table: ").append(XmlUtil.descendantText((Element) n, "t")).append(']');
                    }
                }
                cells.add(cell.toString());
            }
            rows.add(cells);
        }
        e.data.put("rows", rows);
        e.data.put("row_count", rows.size());
        int maxCols = 0;
        for (List<String> r : rows) maxCols = Math.max(maxCols, r.size());
        e.data.put("column_count", maxCols);
        StringBuilder flat = new StringBuilder();
        for (List<String> row : rows) {
            if (flat.length() > 0) flat.append('\n');
            flat.append(String.join(" | ", row));
        }
        e.text = flat.toString();
        return e;
    }

    private int appendRelatedParts(SafeZip zip, Map<String, OoxmlRelations.Rel> rels, Models.Unit unit, int order, Models.DocumentResult out) throws Exception {
        for (OoxmlRelations.Rel rel : rels.values()) {
            if (rel.type == null || "External".equalsIgnoreCase(rel.targetMode)) continue;
            String part = SafeZip.resolve("word/document.xml", rel.target);
            if (rel.type.endsWith("/header")) order = appendSimplePart(zip, part, "header", unit, order);
            else if (rel.type.endsWith("/footer")) order = appendSimplePart(zip, part, "footer", unit, order);
            else if (rel.type.endsWith("/comments")) order = appendComments(zip, part, unit, order);
            else if (rel.type.endsWith("/footnotes")) order = appendNotes(zip, part, "footnote", unit, order);
            else if (rel.type.endsWith("/endnotes")) order = appendNotes(zip, part, "endnote", unit, order);
            else if (rel.type.contains("oleObject") || rel.type.contains("package")) out.unsupportedObjects.add("Embedded relationship detected: " + rel.type);
        }
        return order;
    }

    private int appendSimplePart(SafeZip zip, String path, String type, Models.Unit unit, int order) throws Exception {
        byte[] xml = zip.read(path);
        if (xml == null) return order;
        Document doc = XmlUtil.parse(xml);
        String text = XmlUtil.descendantText(doc.getDocumentElement(), "t");
        Models.Element e = new Models.Element(++order, type, text);
        e.data.put("source_part", path);
        unit.elements.add(e);
        return order;
    }

    private int appendComments(SafeZip zip, String path, Models.Unit unit, int order) throws Exception {
        byte[] xml = zip.read(path);
        if (xml == null) return order;
        Document doc = XmlUtil.parse(xml);
        for (Element c : XmlUtil.descendants(doc.getDocumentElement(), "comment")) {
            Models.Element e = new Models.Element(++order, "comment", XmlUtil.descendantText(c, "t"));
            e.data.put("id", XmlUtil.attr(c, "id"));
            e.data.put("author", XmlUtil.attr(c, "author"));
            e.data.put("date", XmlUtil.attr(c, "date"));
            unit.elements.add(e);
        }
        return order;
    }

    private int appendNotes(SafeZip zip, String path, String type, Models.Unit unit, int order) throws Exception {
        byte[] xml = zip.read(path);
        if (xml == null) return order;
        Document doc = XmlUtil.parse(xml);
        for (Element note : XmlUtil.descendants(doc.getDocumentElement(), type)) {
            String id = XmlUtil.attr(note, "id");
            if (id.startsWith("-")) continue;
            Models.Element e = new Models.Element(++order, type, XmlUtil.descendantText(note, "t"));
            e.data.put("id", id);
            unit.elements.add(e);
        }
        return order;
    }

    private void appendStoredProperties(SafeZip zip, Models.DocumentResult out) throws Exception {
        byte[] app = zip.read("docProps/app.xml");
        if (app != null) {
            Document doc = XmlUtil.parse(app);
            String pages = XmlUtil.descendantText(doc.getDocumentElement(), "Pages");
            String words = XmlUtil.descendantText(doc.getDocumentElement(), "Words");
            String paragraphs = XmlUtil.descendantText(doc.getDocumentElement(), "Paragraphs");
            if (!pages.isEmpty()) out.metadata.put("stored_page_count", pages);
            if (!words.isEmpty()) out.metadata.put("stored_word_count", words);
            if (!paragraphs.isEmpty()) out.metadata.put("stored_paragraph_count", paragraphs);
        }
        byte[] core = zip.read("docProps/core.xml");
        if (core != null) {
            Document doc = XmlUtil.parse(core);
            putText(out, doc, "title", "title");
            putText(out, doc, "subject", "subject");
            putText(out, doc, "creator", "creator");
            putText(out, doc, "last_modified_by", "lastModifiedBy");
            putText(out, doc, "created", "created");
            putText(out, doc, "modified", "modified");
        }
    }

    private void putText(Models.DocumentResult out, Document doc, String key, String local) {
        String value = XmlUtil.descendantText(doc.getDocumentElement(), local);
        if (!value.isEmpty()) out.metadata.put(key, value);
    }

    private void fillSectionProperties(Element sect, Models.Element e) {
        Element pgSz = XmlUtil.firstChild(sect, "pgSz");
        if (pgSz != null) {
            e.data.put("page_width_twips", XmlUtil.attr(pgSz, "w"));
            e.data.put("page_height_twips", XmlUtil.attr(pgSz, "h"));
            e.data.put("orientation", XmlUtil.attr(pgSz, "orient"));
        }
        Element pgMar = XmlUtil.firstChild(sect, "pgMar");
        if (pgMar != null) {
            Map<String, String> margins = new LinkedHashMap<>();
            for (String key : new String[]{"top", "right", "bottom", "left", "header", "footer", "gutter"}) margins.put(key, XmlUtil.attr(pgMar, key));
            e.data.put("margins_twips", margins);
        }
    }
}
