package com.filesextract.mobile;

import android.content.Context;

import org.w3c.dom.Document;
import org.w3c.dom.Element;

import java.io.File;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class XlsxExtractor implements MobileExtractor {
    @Override
    public Models.DocumentResult extract(Context context, File input, String filename, Models.ExtractionOptions options) throws Exception {
        Models.DocumentResult out = new Models.DocumentResult();
        out.unitType = "sheet";
        out.metadata.put("format", "OOXML Spreadsheet");
        try (SafeZip zip = new SafeZip(input, options)) {
            byte[] workbookXml = zip.read("xl/workbook.xml");
            if (workbookXml == null) throw new IllegalArgumentException("Invalid XLSX: xl/workbook.xml is missing.");
            Map<String, OoxmlRelations.Rel> workbookRels = OoxmlRelations.parse(zip.read("xl/_rels/workbook.xml.rels"));
            List<String> sharedStrings = readSharedStrings(zip);
            Document workbook = XmlUtil.parse(workbookXml);

            int sheetIndex = 0;
            for (Element sheet : XmlUtil.descendants(workbook.getDocumentElement(), "sheet")) {
                sheetIndex++;
                String name = XmlUtil.attr(sheet, "name");
                String state = XmlUtil.attr(sheet, "state");
                String rid = XmlUtil.attr(sheet, "id");
                OoxmlRelations.Rel rel = workbookRels.get(rid);
                if (rel == null) {
                    out.warnings.add("Sheet relationship missing for: " + name);
                    continue;
                }
                String sheetPath = SafeZip.resolve("xl/workbook.xml", rel.target);
                byte[] sheetXml = zip.read(sheetPath);
                if (sheetXml == null) {
                    out.warnings.add("Worksheet XML missing for: " + name);
                    continue;
                }
                Models.Unit unit = parseSheet(zip, sheetPath, sheetXml, sharedStrings, sheetIndex, name, state, out);
                out.units.add(unit);
            }

            readWorkbookMetadata(zip, out);
            collectAssets(zip, "xl/media/", out);
            if (zip.has("xl/vbaProject.bin")) {
                out.unsupportedObjects.add("VBA project detected (preserved in source, not executed or parsed on Android).");
            }
        }
        return out;
    }

    private List<String> readSharedStrings(SafeZip zip) throws Exception {
        List<String> strings = new ArrayList<>();
        byte[] xml = zip.read("xl/sharedStrings.xml");
        if (xml == null) return strings;
        Document doc = XmlUtil.parse(xml);
        for (Element si : XmlUtil.descendants(doc.getDocumentElement(), "si")) {
            StringBuilder text = new StringBuilder();
            for (Element t : XmlUtil.descendants(si, "t")) text.append(t.getTextContent());
            strings.add(text.toString());
        }
        return strings;
    }

    private Models.Unit parseSheet(SafeZip zip, String sheetPath, byte[] xml, List<String> shared, int index, String name, String state, Models.DocumentResult out) throws Exception {
        Models.Unit unit = new Models.Unit(index, name == null || name.isEmpty() ? "Sheet " + index : name);
        unit.metadata.put("state", state == null || state.isEmpty() ? "visible" : state);
        Document doc = XmlUtil.parse(xml);
        Element root = doc.getDocumentElement();
        int order = 0;

        Element dimension = firstDesc(root, "dimension");
        if (dimension != null) unit.metadata.put("dimension", XmlUtil.attr(dimension, "ref"));
        Element autoFilter = firstDesc(root, "autoFilter");
        if (autoFilter != null) unit.metadata.put("auto_filter", XmlUtil.attr(autoFilter, "ref"));
        Element pane = firstDesc(root, "pane");
        if (pane != null) {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("xSplit", XmlUtil.attr(pane, "xSplit"));
            p.put("ySplit", XmlUtil.attr(pane, "ySplit"));
            p.put("topLeftCell", XmlUtil.attr(pane, "topLeftCell"));
            unit.metadata.put("pane", p);
        }

        for (Element row : XmlUtil.descendants(root, "row")) {
            String rowNumber = XmlUtil.attr(row, "r");
            boolean hidden = "1".equals(XmlUtil.attr(row, "hidden")) || "true".equalsIgnoreCase(XmlUtil.attr(row, "hidden"));
            for (Element c : XmlUtil.children(row, "c")) {
                String ref = XmlUtil.attr(c, "r");
                String type = XmlUtil.attr(c, "t");
                String style = XmlUtil.attr(c, "s");
                Element formulaNode = XmlUtil.firstChild(c, "f");
                Element valueNode = XmlUtil.firstChild(c, "v");
                String formula = formulaNode == null ? "" : formulaNode.getTextContent();
                String raw = valueNode == null ? "" : valueNode.getTextContent();
                String value = decodeValue(c, type, raw, shared);
                Models.Element e = new Models.Element(++order, "cell", value);
                e.data.put("address", ref);
                e.data.put("row", rowNumber);
                e.data.put("cell_type", type);
                if (!style.isEmpty()) e.data.put("style_index", style);
                if (!formula.isEmpty()) e.data.put("formula", "=" + formula);
                if (!raw.isEmpty()) e.data.put("raw_value", raw);
                if (hidden) e.data.put("row_hidden", true);
                unit.elements.add(e);
            }
        }

        List<String> merges = new ArrayList<>();
        for (Element merge : XmlUtil.descendants(root, "mergeCell")) {
            String ref = XmlUtil.attr(merge, "ref");
            if (!ref.isEmpty()) merges.add(ref);
        }
        if (!merges.isEmpty()) unit.metadata.put("merged_ranges", merges);

        Map<String, OoxmlRelations.Rel> sheetRels = OoxmlRelations.parse(zip.read(relsPath(sheetPath)));
        for (Element link : XmlUtil.descendants(root, "hyperlink")) {
            Models.Element e = new Models.Element(++order, "hyperlink", XmlUtil.attr(link, "ref"));
            e.data.put("cell_range", XmlUtil.attr(link, "ref"));
            String location = XmlUtil.attr(link, "location");
            String rid = XmlUtil.attr(link, "id");
            if (!location.isEmpty()) e.data.put("location", location);
            if (!rid.isEmpty() && sheetRels.containsKey(rid)) e.data.put("target", sheetRels.get(rid).target);
            unit.elements.add(e);
        }

        for (Element validation : XmlUtil.descendants(root, "dataValidation")) {
            Models.Element e = new Models.Element(++order, "data_validation", XmlUtil.attr(validation, "sqref"));
            e.data.put("range", XmlUtil.attr(validation, "sqref"));
            e.data.put("validation_type", XmlUtil.attr(validation, "type"));
            String f1 = XmlUtil.descendantText(validation, "formula1");
            String f2 = XmlUtil.descendantText(validation, "formula2");
            if (!f1.isEmpty()) e.data.put("formula1", f1);
            if (!f2.isEmpty()) e.data.put("formula2", f2);
            unit.elements.add(e);
        }

        for (OoxmlRelations.Rel rel : sheetRels.values()) {
            if (rel.type != null && rel.type.endsWith("/comments")) {
                String path = SafeZip.resolve(sheetPath, rel.target);
                byte[] comments = zip.read(path);
                if (comments != null) order = appendComments(comments, unit, order);
            }
            if (rel.type != null && rel.type.endsWith("/table")) {
                String path = SafeZip.resolve(sheetPath, rel.target);
                byte[] table = zip.read(path);
                if (table != null) order = appendTable(table, unit, order);
            }
            if (rel.type != null && (rel.type.endsWith("/drawing") || rel.type.endsWith("/chart"))) {
                out.warnings.add("Sheet '" + unit.name + "' contains drawing/chart relationships; media files are exported as assets and chart structure may be partial.");
            }
        }
        return unit;
    }

    private String decodeValue(Element cell, String type, String raw, List<String> shared) {
        if ("s".equals(type)) {
            try {
                int i = Integer.parseInt(raw);
                return i >= 0 && i < shared.size() ? shared.get(i) : raw;
            } catch (Exception ignored) { return raw; }
        }
        if ("inlineStr".equals(type)) return XmlUtil.descendantText(cell, "t");
        if ("b".equals(type)) return "1".equals(raw) ? "TRUE" : "FALSE";
        return raw;
    }

    private int appendComments(byte[] xml, Models.Unit unit, int order) throws Exception {
        Document doc = XmlUtil.parse(xml);
        for (Element c : XmlUtil.descendants(doc.getDocumentElement(), "comment")) {
            Models.Element e = new Models.Element(++order, "comment", XmlUtil.descendantText(c, "t"));
            e.data.put("cell", XmlUtil.attr(c, "ref"));
            e.data.put("author_id", XmlUtil.attr(c, "authorId"));
            unit.elements.add(e);
        }
        return order;
    }

    private int appendTable(byte[] xml, Models.Unit unit, int order) throws Exception {
        Document doc = XmlUtil.parse(xml);
        Element table = doc.getDocumentElement();
        Models.Element e = new Models.Element(++order, "table_definition", XmlUtil.attr(table, "name"));
        e.data.put("name", XmlUtil.attr(table, "name"));
        e.data.put("display_name", XmlUtil.attr(table, "displayName"));
        e.data.put("range", XmlUtil.attr(table, "ref"));
        List<String> columns = new ArrayList<>();
        for (Element col : XmlUtil.descendants(table, "tableColumn")) columns.add(XmlUtil.attr(col, "name"));
        e.data.put("columns", columns);
        unit.elements.add(e);
        return order;
    }

    private void readWorkbookMetadata(SafeZip zip, Models.DocumentResult out) throws Exception {
        byte[] props = zip.read("docProps/app.xml");
        if (props != null) {
            Document doc = XmlUtil.parse(props);
            String app = XmlUtil.descendantText(doc.getDocumentElement(), "Application");
            if (!app.isEmpty()) out.metadata.put("application", app);
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

    static void collectAssets(SafeZip zip, String prefix, Models.DocumentResult out) throws Exception {
        for (String path : zip.namesWithPrefix(prefix)) {
            byte[] bytes = zip.read(path);
            if (bytes == null) continue;
            Models.Asset a = new Models.Asset();
            a.name = path.substring(path.lastIndexOf('/') + 1);
            a.source = path;
            a.mimeType = mime(a.name);
            a.size = bytes.length;
            a.sha256 = Hashing.sha256(bytes);
            a.bytes = bytes;
            out.assets.add(a);
        }
    }

    private static String mime(String name) {
        String lower = name.toLowerCase();
        if (lower.endsWith(".png")) return "image/png";
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".gif")) return "image/gif";
        if (lower.endsWith(".svg")) return "image/svg+xml";
        if (lower.endsWith(".emf")) return "image/emf";
        return "application/octet-stream";
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
