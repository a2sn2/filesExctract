package com.filesextract.mobile;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.util.Locale;

final class DocumentTypeDetector {
    private DocumentTypeDetector() {}

    static String detect(File file, String filename) throws Exception {
        byte[] head = new byte[8];
        try (InputStream in = new FileInputStream(file)) {
            int n = in.read(head);
            if (n >= 5 && head[0] == '%' && head[1] == 'P' && head[2] == 'D' && head[3] == 'F' && head[4] == '-') return "pdf";
        }
        String lower = filename.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".docx")) return "docx";
        if (lower.endsWith(".xlsx") || lower.endsWith(".xlsm")) return "xlsx";
        if (lower.endsWith(".pptx")) return "pptx";
        throw new IllegalArgumentException("Unsupported Android file type. Supported: PDF, DOCX, XLSX/XLSM, PPTX.");
    }
}
