package com.filesextract.mobile;

import android.content.Context;

import com.tom_roush.pdfbox.android.PDFBoxResourceLoader;
import com.tom_roush.pdfbox.pdmodel.PDDocument;
import com.tom_roush.pdfbox.pdmodel.PDDocumentInformation;
import com.tom_roush.pdfbox.text.PDFTextStripper;

import java.io.File;

final class PdfExtractor implements MobileExtractor {
    @Override
    public Models.DocumentResult extract(Context context, File input, String filename, Models.ExtractionOptions options) throws Exception {
        PDFBoxResourceLoader.init(context.getApplicationContext());
        Models.DocumentResult out = new Models.DocumentResult();
        out.unitType = "page";
        out.metadata.put("format", "PDF");
        int ocrCount = 0;
        try (PDDocument doc = PDDocument.load(input)) {
            int pages = doc.getNumberOfPages();
            out.metadata.put("page_count", pages);
            if (pages > options.maxPdfPages) throw new IllegalArgumentException("PDF has " + pages + " pages; mobile limit is " + options.maxPdfPages + ".");
            PDDocumentInformation info = doc.getDocumentInformation();
            if (info != null) {
                put(out, "title", info.getTitle());
                put(out, "author", info.getAuthor());
                put(out, "subject", info.getSubject());
                put(out, "keywords", info.getKeywords());
                put(out, "creator", info.getCreator());
                put(out, "producer", info.getProducer());
            }
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            for (int i = 0; i < pages; i++) {
                Models.Unit unit = new Models.Unit(i + 1, "Page " + (i + 1));
                stripper.setStartPage(i + 1);
                stripper.setEndPage(i + 1);
                String text = safeTrim(stripper.getText(doc));
                boolean ocrUsed = false;
                if (text.length() < 8 && options.enableOcr && ocrCount < options.maxOcrPages) {
                    try {
                        String ocr = OcrHelper.recognizePdfPage(input, i);
                        if (!ocr.isEmpty()) {
                            text = ocr;
                            ocrUsed = true;
                            ocrCount++;
                        }
                    } catch (Exception ex) {
                        out.warnings.add("OCR failed on page " + (i + 1) + ": " + ex.getMessage());
                    }
                }
                Models.Element e = new Models.Element(1, ocrUsed ? "ocr_text" : "text", text);
                e.data.put("page_number", i + 1);
                if (ocrUsed) e.data.put("ocr_engine", "ML Kit on-device text recognition");
                unit.elements.add(e);
                unit.metadata.put("ocr_used", ocrUsed);
                out.units.add(unit);
            }
        }
        out.metadata.put("ocr_pages", ocrCount);
        out.warnings.add("Android PDF table/layout extraction is text-first. Reading order is sorted by position; complex visual tables may require the desktop Docling engine for higher-fidelity structure.");
        return out;
    }

    private static void put(Models.DocumentResult out, String key, String value) {
        if (value != null && !value.trim().isEmpty()) out.metadata.put(key, value.trim());
    }

    private static String safeTrim(String value) {
        return value == null ? "" : value.replace("\u0000", "").trim();
    }
}
