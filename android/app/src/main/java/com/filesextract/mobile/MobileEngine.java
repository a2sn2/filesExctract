package com.filesextract.mobile;

import android.content.Context;
import android.os.Environment;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public final class MobileEngine {
    private MobileEngine() {}

    public static Models.ExtractionOutput extract(Context context, File input, String filename, Models.ExtractionOptions options) throws Exception {
        if (input.length() <= 0) throw new IllegalArgumentException("The selected file is empty.");
        if (input.length() > options.maxInputBytes) throw new IllegalArgumentException("The selected file exceeds the 250 MB mobile safety limit.");

        String type = DocumentTypeDetector.detect(input, filename);
        MobileExtractor extractor;
        switch (type) {
            case "docx": extractor = new DocxExtractor(); break;
            case "xlsx": extractor = new XlsxExtractor(); break;
            case "pptx": extractor = new PptxExtractor(); break;
            case "pdf": extractor = new PdfExtractor(); break;
            default: throw new IllegalStateException("No extractor for " + type);
        }

        Models.DocumentResult result = extractor.extract(context, input, filename, options);
        result.filename = filename;
        result.documentType = type;
        result.unitCount = result.units.size();
        result.metadata.put("sha256", Hashing.sha256(input));
        result.metadata.put("input_bytes", input.length());
        result.metadata.put("engine", "FilesExtract Mobile 0.5.0");

        File base = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS);
        if (base == null) base = context.getFilesDir();
        File root = new File(base, "FilesExtract");
        if (!root.exists() && !root.mkdirs()) throw new IllegalStateException("Could not create output directory.");
        String safe = filename.replaceAll("[^A-Za-z0-9._-]", "_");
        String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
        File outDir = new File(root, safe + "_" + stamp);
        if (!outDir.mkdirs()) throw new IllegalStateException("Could not create extraction output directory.");

        return OutputWriter.write(result, outDir);
    }
}
