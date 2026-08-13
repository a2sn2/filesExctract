package com.filesextract.mobile;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.pdf.PdfDocument;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class ExtractionInstrumentedTest {
    private final Context context = ApplicationProvider.getApplicationContext();

    @Test public void extractsAllSupportedFamilies() throws Exception {
        Models.ExtractionOptions options = new Models.ExtractionOptions(); options.enableOcr = true;
        File xlsx = sampleXlsx(); Models.ExtractionOutput xo = MobileEngine.extract(context, xlsx, "sample.xlsx", options); assertEquals("xlsx", xo.result.documentType); assertEquals(1, xo.result.unitCount); assertTrue(xo.jsonFile.length() > 0); assertTrue(xo.markdownFile.length() > 0); assertEquals("Hello", xo.result.units.get(0).elements.get(0).text);
        File docx = sampleDocx(); Models.ExtractionOutput wo = MobileEngine.extract(context, docx, "sample.docx", options); assertEquals("docx", wo.result.documentType); assertTrue(wo.result.units.get(0).elements.stream().anyMatch(e -> e.text != null && e.text.contains("Hello Word")));
        File pptx = samplePptx(); Models.ExtractionOutput po = MobileEngine.extract(context, pptx, "sample.pptx", options); assertEquals("pptx", po.result.documentType); assertEquals(1, po.result.unitCount); assertTrue(po.result.units.get(0).elements.stream().anyMatch(e -> e.text != null && e.text.contains("Hello Slide")));
        File pdf = samplePdf(); Models.ExtractionOutput pdo = MobileEngine.extract(context, pdf, "sample.pdf", options); assertEquals("pdf", pdo.result.documentType); assertEquals(1, pdo.result.unitCount); assertFalse(pdo.result.units.get(0).elements.isEmpty());
    }

    private File sampleXlsx() throws Exception {
        File f = File.createTempFile("sample", ".xlsx", context.getCacheDir());
        try (ZipOutputStream z = new ZipOutputStream(new FileOutputStream(f))) {
            put(z, "[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>");
            put(z, "xl/workbook.xml", "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"Data\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>");
            put(z, "xl/_rels/workbook.xml.rels", "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/></Relationships>");
            put(z, "xl/sharedStrings.xml", "<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><si><t>Hello</t></si></sst>");
            put(z, "xl/worksheets/sheet1.xml", "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><dimension ref=\"A1:B2\"/><sheetData><row r=\"1\"><c r=\"A1\" t=\"s\"><v>0</v></c><c r=\"B1\"><f>1+1</f><v>2</v></c></row></sheetData><mergeCells><mergeCell ref=\"A2:B2\"/></mergeCells></worksheet>");
        }
        return f;
    }

    private File sampleDocx() throws Exception {
        File f = File.createTempFile("sample", ".docx", context.getCacheDir());
        try (ZipOutputStream z = new ZipOutputStream(new FileOutputStream(f))) {
            put(z, "[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>");
            put(z, "word/document.xml", "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body><w:p><w:r><w:t>Hello Word</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>");
            put(z, "word/_rels/document.xml.rels", "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"/>");
            put(z, "docProps/app.xml", "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\"><Pages>1</Pages></Properties>");
        }
        return f;
    }

    private File samplePptx() throws Exception {
        File f = File.createTempFile("sample", ".pptx", context.getCacheDir());
        try (ZipOutputStream z = new ZipOutputStream(new FileOutputStream(f))) {
            put(z, "[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>");
            put(z, "ppt/presentation.xml", "<p:presentation xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><p:sldIdLst><p:sldId id=\"256\" r:id=\"rId1\"/></p:sldIdLst></p:presentation>");
            put(z, "ppt/_rels/presentation.xml.rels", "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide1.xml\"/></Relationships>");
            put(z, "ppt/slides/slide1.xml", "<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id=\"2\" name=\"Title\"/></p:nvSpPr><p:txBody><a:p><a:r><a:t>Hello Slide</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>");
            put(z, "ppt/slides/_rels/slide1.xml.rels", "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"/>");
        }
        return f;
    }

    private File samplePdf() throws Exception {
        File f = File.createTempFile("sample", ".pdf", context.getCacheDir());
        PdfDocument doc = new PdfDocument(); PdfDocument.Page page = doc.startPage(new PdfDocument.PageInfo.Builder(600, 800, 1).create()); Canvas canvas = page.getCanvas(); Paint paint = new Paint(); paint.setTextSize(32f); canvas.drawText("Hello PDF", 50, 100, paint); doc.finishPage(page); try (FileOutputStream out = new FileOutputStream(f)) { doc.writeTo(out); } doc.close(); return f;
    }

    private void put(ZipOutputStream z, String path, String text) throws Exception { z.putNextEntry(new ZipEntry(path)); z.write(text.getBytes(StandardCharsets.UTF_8)); z.closeEntry(); }
}
