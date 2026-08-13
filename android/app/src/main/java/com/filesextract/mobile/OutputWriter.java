package com.filesextract.mobile;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

final class OutputWriter {
    private OutputWriter() {}

    static Models.ExtractionOutput write(Models.DocumentResult result, File outDir) throws Exception {
        File assetsDir = new File(outDir, "assets");
        if (!result.assets.isEmpty() && !assetsDir.mkdirs() && !assetsDir.exists()) throw new IllegalStateException("Could not create assets directory.");
        int assetIndex = 0;
        for (Models.Asset asset : result.assets) {
            assetIndex++;
            if (asset.bytes == null) continue;
            String safeName = asset.name == null ? "asset_" + assetIndex : asset.name.replaceAll("[^A-Za-z0-9._-]", "_");
            File target = uniqueFile(assetsDir, String.format("%03d_%s", assetIndex, safeName));
            try (FileOutputStream out = new FileOutputStream(target)) { out.write(asset.bytes); }
            asset.outputPath = "assets/" + target.getName();
            asset.bytes = null;
        }
        File json = new File(outDir, "document.json");
        Gson gson = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
        try (Writer writer = new OutputStreamWriter(new FileOutputStream(json), StandardCharsets.UTF_8)) { gson.toJson(result, writer); }
        File md = new File(outDir, "document.md");
        try (Writer writer = new OutputStreamWriter(new FileOutputStream(md), StandardCharsets.UTF_8)) { writer.write(renderMarkdown(result)); }
        File manifest = new File(outDir, "manifest.txt");
        try (Writer writer = new OutputStreamWriter(new FileOutputStream(manifest), StandardCharsets.UTF_8)) {
            writer.write(Hashing.sha256(json) + "  document.json\n");
            writer.write(Hashing.sha256(md) + "  document.md\n");
            for (Models.Asset asset : result.assets) if (asset.outputPath != null) writer.write(asset.sha256 + "  " + asset.outputPath + "\n");
        }
        Models.ExtractionOutput output = new Models.ExtractionOutput();
        output.result = result;
        output.directory = outDir;
        output.jsonFile = json;
        output.markdownFile = md;
        return output;
    }

    private static File uniqueFile(File dir, String name) {
        File f = new File(dir, name);
        if (!f.exists()) return f;
        int dot = name.lastIndexOf('.');
        String stem = dot > 0 ? name.substring(0, dot) : name;
        String ext = dot > 0 ? name.substring(dot) : "";
        int i = 2;
        while (true) {
            f = new File(dir, stem + "_" + i + ext);
            if (!f.exists()) return f;
            i++;
        }
    }

    private static String renderMarkdown(Models.DocumentResult result) {
        StringBuilder md = new StringBuilder();
        md.append("# ").append(escape(result.filename)).append("\n\n");
        md.append("- Type: `").append(result.documentType).append("`\n");
        md.append("- Units: ").append(result.unitCount).append(" (`").append(result.unitType).append("`)\n");
        Object sha = result.metadata.get("sha256");
        if (sha != null) md.append("- SHA-256: `").append(sha).append("`\n");
        md.append('\n');
        for (Models.Unit unit : result.units) {
            md.append("## ").append(escape(unit.name)).append("\n\n");
            if (!unit.metadata.isEmpty()) {
                for (Map.Entry<String, Object> entry : unit.metadata.entrySet()) md.append("- **").append(escape(entry.getKey())).append(":** ").append(escape(String.valueOf(entry.getValue()))).append("\n");
                md.append('\n');
            }
            for (Models.Element e : unit.elements) renderElement(md, e);
        }
        if (!result.assets.isEmpty()) {
            md.append("## Assets\n\n");
            for (Models.Asset a : result.assets) md.append("- `").append(a.outputPath == null ? a.source : a.outputPath).append("` — ").append(a.mimeType).append(", ").append(a.size).append(" bytes, SHA-256 `").append(a.sha256).append("`\n");
            md.append('\n');
        }
        if (!result.warnings.isEmpty()) {
            md.append("## Warnings\n\n");
            for (String warning : result.warnings) md.append("- ").append(escape(warning)).append("\n");
            md.append('\n');
        }
        if (!result.unsupportedObjects.isEmpty()) {
            md.append("## Unsupported objects\n\n");
            for (String warning : result.unsupportedObjects) md.append("- ").append(escape(warning)).append("\n");
        }
        return md.toString();
    }

    private static void renderElement(StringBuilder md, Models.Element e) {
        String type = e.type == null ? "element" : e.type;
        if ("cell".equals(type)) {
            Object address = e.data.get("address");
            md.append("- `").append(address == null ? "?" : address).append("` = ").append(escape(e.text)).append('\n');
            Object formula = e.data.get("formula");
            if (formula != null) md.append("  - formula: `").append(escape(String.valueOf(formula))).append("`\n");
            return;
        }
        if ("table".equals(type)) {
            Object rowsObj = e.data.get("rows");
            if (rowsObj instanceof List) {
                @SuppressWarnings("unchecked") List<Object> rows = (List<Object>) rowsObj;
                renderTable(md, rows);
                return;
            }
        }
        if ("paragraph".equals(type) || "text".equals(type) || "ocr_text".equals(type) || "shape_text".equals(type) || "speaker_notes".equals(type)) {
            if (e.text != null && !e.text.trim().isEmpty()) md.append(escape(e.text)).append("\n\n");
            return;
        }
        md.append("- **").append(escape(type)).append("**");
        if (e.text != null && !e.text.isEmpty()) md.append(": ").append(escape(e.text));
        if (!e.data.isEmpty()) md.append(" — `").append(escape(String.valueOf(e.data))).append("`");
        md.append('\n');
    }

    private static void renderTable(StringBuilder md, List<Object> rawRows) {
        List<List<String>> rows = new ArrayList<>();
        int columns = 0;
        for (Object raw : rawRows) {
            List<String> row = new ArrayList<>();
            if (raw instanceof List) for (Object value : (List<?>) raw) row.add(String.valueOf(value));
            columns = Math.max(columns, row.size());
            rows.add(row);
        }
        if (columns == 0) return;
        List<String> first = rows.isEmpty() ? new ArrayList<>() : rows.get(0);
        md.append('|');
        for (int i = 0; i < columns; i++) md.append(' ').append(escapePipe(i < first.size() ? first.get(i) : "")).append(" |");
        md.append('\n').append('|');
        for (int i = 0; i < columns; i++) md.append(" --- |");
        md.append('\n');
        for (int r = 1; r < rows.size(); r++) {
            md.append('|');
            List<String> row = rows.get(r);
            for (int c = 0; c < columns; c++) md.append(' ').append(escapePipe(c < row.size() ? row.get(c) : "")).append(" |");
            md.append('\n');
        }
        md.append('\n');
    }

    private static String escape(String value) { return value == null ? "" : value.replace("\r", "").replace("\u0000", ""); }
    private static String escapePipe(String value) { return escape(value).replace("|", "\\|").replace("\n", "<br>"); }
}
