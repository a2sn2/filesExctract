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

final class PptxExtractor implements MobileExtractor {
    @Override
    public Models.DocumentResult extract(Context context, File input, String filename, Models.ExtractionOptions options) throws Exception {
        Models.DocumentResult out = new Models.DocumentResult();
        out.unitType = "slide";
        out.metadata.put("format", "OOXML Presentation");
        try (SafeZip zip = new SafeZip(input, options)) {
            byte[] presXml = zip.read("ppt/presentation.xml");
            if (presXml == null) throw new IllegalArgumentException("Invalid PPTX: ppt/presentation.xml is missing.");
            Map<String, OoxmlRelations.Rel> presRels = OoxmlRelations.parse(zip.read("ppt/_rels/presentation.xml.rels"));
            Document pres = XmlUtil.parse(presXml);
            int index = 0;
            for (Element sldId : XmlUtil.descendants(pres.getDocumentElement(), "sldId")) {
                index++;
                String rid = XmlUtil.attr(sldId, "id");
                OoxmlRelations.Rel rel = presRels.get(rid);
                if (rel == null) {
                    out.warnings.add("Slide relationship missing at index " + index);
                    continue;
                }
                String slidePath = SafeZip.resolve("ppt/presentation.xml", rel.target);
                byte[] slideXml = zip.read(slidePath);
                if (slideXml == null) {
                    out.warnings.add("Slide XML missing at index " + index);
                    continue;
                }
                out.units.add(parseSlide(zip, slidePath, slideXml, index, out));
            }
            appendProperties(zip, out);
            XlsxExtractor.collectAssets(zip, "ppt/media/", out);
            if (!zip.namesWithPrefix("ppt/embeddings/").isEmpty()) {
                out.unsupportedObjects.add("Embedded OLE/package objects detected under ppt/embeddings; binary payload is not interpreted on Android.");
            }
        }
        return out;
    }

    private Models.Unit parseSlide(SafeZip zip, String slidePath, byte[] xml, int index, Models.DocumentResult out) throws Exception {
        Models.Unit unit = new Models.Unit(index, "Slide " + index);
        Document doc = XmlUtil.parse(xml);
        Element root = doc.getDocumentElement();
        Map<String, OoxmlRelations.Rel> rels = OoxmlRelations.parse(zip.read(relsPath(slidePath)));
        int order = 0;

        List<Element> spTrees = XmlUtil.descendants(root, "spTree");
        if (!spTrees.isEmpty()) {
            NodeList children = spTrees.get(0).getChildNodes();
            for (int i = 0; i < children.getLength(); i++) {
                Node n = children.item(i);
                if (!(n instanceof Element)) continue;
                Element e = (Element) n;
                String local = XmlUtil.local(e);
                if ("sp".equals(local) || "cxnSp".equals(local)) {
                    Models.Element shape = parseShape(e, ++order, rels);
                    if (!shape.text.isEmpty() || !shape.data.isEmpty()) unit.elements.add(shape);
                } else if ("graphicFrame".equals(local)) {
                    Models.Element gf = parseGraphicFrame(e, ++order, rels);
                    unit.elements.add(gf);
                } else if ("pic".equals(local)) {
                    Models.Element pic = parsePicture(e, ++order, rels);
                    unit.elements.add(pic);
                } else if ("grpSp".equals(local)) {
                    Models.Element group = new Models.Element(++order, "group", XmlUtil.descendantText(e, "t"));
                    group.data.put("shape_count", XmlUtil.descendants(e, "sp").size());
                    unit.elements.add(group);
                }
            }
        }

        for (OoxmlRelations.Rel rel : rels.values()) {
            if (rel.type == null) continue;
            if (rel.type.endsWith("/notesSlide")) {
                String notesPath = SafeZip.resolve(slidePath, rel.target);
                byte[] notes = zip.read(notesPath);
                if (notes != null) {
                    Document nd = XmlUtil.parse(notes);
                    String text = XmlUtil.descendantText(nd.getDocumentElement(), "t");
                    Models.Element note = new Models.Element(++order, "speaker_notes", text);
                    note.data.put("source_part", notesPath);
                    unit.elements.add(note);
                }
            }
            if (rel.type.endsWith("/chart")) {
                String chartPath = SafeZip.resolve(slidePath, rel.target);
                byte[] chart = zip.read(chartPath);
                if (chart != null) {
                    Models.Element ce = parseChart(chart, ++order, chartPath);
                    unit.elements.add(ce);
                }
            }
        }
        return unit;
    }

    private Models.Element parseShape(Element shape, int order, Map<String, OoxmlRelations.Rel> rels) {
        String text = XmlUtil.descendantText(shape, "t");
        Models.Element e = new Models.Element(order, "shape_text", text);
        Element cNvPr = firstDesc(shape, "cNvPr");
        if (cNvPr != null) {
            e.data.put("shape_id", XmlUtil.attr(cNvPr, "id"));
            e.data.put("name", XmlUtil.attr(cNvPr, "name"));
            String descr = XmlUtil.attr(cNvPr, "descr");
            if (!descr.isEmpty()) e.data.put("alt_text", descr);
            String title = XmlUtil.attr(cNvPr, "title");
            if (!title.isEmpty()) e.data.put("title", title);
        }
        List<Map<String, Object>> paragraphs = new ArrayList<>();
        for (Element p : XmlUtil.descendants(shape, "p")) {
            Map<String, Object> pd = new LinkedHashMap<>();
            pd.put("text", XmlUtil.descendantText(p, "t"));
            Element pPr = XmlUtil.firstChild(p, "pPr");
            if (pPr != null) {
                String lvl = XmlUtil.attr(pPr, "lvl");
                if (!lvl.isEmpty()) pd.put("level", lvl);
            }
            paragraphs.add(pd);
        }
        if (!paragraphs.isEmpty()) e.data.put("paragraphs", paragraphs);
        return e;
    }

    private Models.Element parseGraphicFrame(Element frame, int order, Map<String, OoxmlRelations.Rel> rels) {
        List<Element> tables = XmlUtil.descendants(frame, "tbl");
        if (!tables.isEmpty()) {
            List<List<String>> rows = new ArrayList<>();
            for (Element tr : XmlUtil.children(tables.get(0), "tr")) {
                List<String> row = new ArrayList<>();
                for (Element tc : XmlUtil.children(tr, "tc")) row.add(XmlUtil.descendantText(tc, "t"));
                rows.add(row);
            }
            Models.Element e = new Models.Element(order, "table", "");
            e.data.put("rows", rows);
            e.data.put("row_count", rows.size());
            StringBuilder flat = new StringBuilder();
            for (List<String> row : rows) {
                if (flat.length() > 0) flat.append('\n');
                flat.append(String.join(" | ", row));
            }
            e.text = flat.toString();
            return e;
        }
        String chartRid = "";
        Element chart = firstDesc(frame, "chart");
        if (chart != null) chartRid = XmlUtil.attr(chart, "id");
        Models.Element e = new Models.Element(order, chart == null ? "graphic" : "chart_reference", XmlUtil.descendantText(frame, "t"));
        if (!chartRid.isEmpty() && rels.containsKey(chartRid)) e.data.put("target", rels.get(chartRid).target);
        return e;
    }

    private Models.Element parsePicture(Element pic, int order, Map<String, OoxmlRelations.Rel> rels) {
        Models.Element e = new Models.Element(order, "picture", "");
        Element cNvPr = firstDesc(pic, "cNvPr");
        if (cNvPr != null) {
            e.text = XmlUtil.attr(cNvPr, "name");
            e.data.put("name", XmlUtil.attr(cNvPr, "name"));
            String descr = XmlUtil.attr(cNvPr, "descr");
            if (!descr.isEmpty()) e.data.put("alt_text", descr);
        }
        Element blip = firstDesc(pic, "blip");
        if (blip != null) {
            String rid = XmlUtil.attr(blip, "embed");
            if (!rid.isEmpty() && rels.containsKey(rid)) e.data.put("target", rels.get(rid).target);
        }
        return e;
    }

    private Models.Element parseChart(byte[] xml, int order, String source) throws Exception {
        Document doc = XmlUtil.parse(xml);
        Element root = doc.getDocumentElement();
        Models.Element e = new Models.Element(order, "chart", XmlUtil.descendantText(root, "t"));
        e.data.put("source_part", source);
        List<String> formulas = new ArrayList<>();
        for (Element f : XmlUtil.descendants(root, "f")) {
            String v = f.getTextContent();
            if (v != null && !v.trim().isEmpty()) formulas.add(v.trim());
        }
        if (!formulas.isEmpty()) e.data.put("data_formulas", formulas);
        List<String> cachedValues = new ArrayList<>();
        for (Element v : XmlUtil.descendants(root, "v")) {
            String text = v.getTextContent();
            if (text != null && !text.trim().isEmpty()) cachedValues.add(text.trim());
        }
        if (!cachedValues.isEmpty()) e.data.put("cached_values", cachedValues);
        return e;
    }

    private void appendProperties(SafeZip zip, Models.DocumentResult out) throws Exception {
        byte[] app = zip.read("docProps/app.xml");
        if (app != null) {
            Document doc = XmlUtil.parse(app);
            String slides = XmlUtil.descendantText(doc.getDocumentElement(), "Slides");
            String notes = XmlUtil.descendantText(doc.getDocumentElement(), "Notes");
            if (!slides.isEmpty()) out.metadata.put("stored_slide_count", slides);
            if (!notes.isEmpty()) out.metadata.put("stored_notes_count", notes);
        }
        byte[] core = zip.read("docProps/core.xml");
        if (core != null) {
            Document doc = XmlUtil.parse(core);
            String title = XmlUtil.descendantText(doc.getDocumentElement(), "title");
            String creator = XmlUtil.descendantText(doc.getDocumentElement(), "creator");
            if (!title.isEmpty()) out.metadata.put("title", title);
            if (!creator.isEmpty()) out.metadata.put("creator", creator);
        }
    }

    private static String relsPath(String partPath) {
        int slash = partPath.lastIndexOf('/');
        String dir = slash >= 0 ? partPath.substring(0, slash + 1) : "";
        String name = slash >= 0 ? partPath.substring(slash + 1) : partPath;
        return dir + "_rels/" + name + ".rels";
    }

    private static Element firstDesc(Element root, String localName) {
        List<Element> all = XmlUtil.descendants(root, localName);
        return all.isEmpty() ? null : all.get(0);
    }
}
