package com.filesextract.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.pdf.PdfDocument;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

@RunWith(AndroidJUnit4.class)
public final class VisualDocxConversionInstrumentedTest {

    @Test
    public void imageToWordProducesValidVisualDocxPackage() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        File image = new File(context.getCacheDir(), "visual-source.png");
        Bitmap bitmap = Bitmap.createBitmap(640, 360, Bitmap.Config.ARGB_8888);
        try {
            Canvas canvas = new Canvas(bitmap);
            canvas.drawColor(Color.WHITE);
            Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
            paint.setColor(Color.BLACK);
            paint.setTextSize(42f);
            canvas.drawText("Exact layout test", 40, 120, paint);
            try (FileOutputStream out = new FileOutputStream(image)) {
                assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG, 100, out));
            }
        } finally {
            bitmap.recycle();
        }

        VisualDocxConverter.ConversionOutput result = VisualDocxConverter.convert(context, image, "visual-source.png", "image/png");
        assertNotNull(result);
        assertEquals(1, result.pages);
        assertTrue(result.file.isFile());
        assertTrue(result.file.length() > 0);

        try (ZipFile zip = new ZipFile(result.file)) {
            assertNotNull(zip.getEntry("[Content_Types].xml"));
            assertNotNull(zip.getEntry("word/document.xml"));
            assertNotNull(zip.getEntry("word/_rels/document.xml.rels"));
            assertNotNull(zip.getEntry("word/media/page_1.png"));
            String xml = read(zip, "word/document.xml");
            assertTrue(xml.contains("wp:anchor"));
            assertTrue(xml.contains("w:pgSz"));
            assertTrue(xml.contains("rIdImage1"));
        }
    }

    @Test
    public void twoPagePdfKeepsTwoWordPagesAndTwoRenderedImages() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        File pdfFile = new File(context.getCacheDir(), "two-pages.pdf");
        PdfDocument pdf = new PdfDocument();
        try {
            Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
            paint.setColor(Color.BLACK);
            paint.setTextSize(30f);
            for (int i = 1; i <= 2; i++) {
                PdfDocument.PageInfo info = new PdfDocument.PageInfo.Builder(612, 792, i).create();
                PdfDocument.Page page = pdf.startPage(info);
                page.getCanvas().drawColor(Color.WHITE);
                page.getCanvas().drawText("Page " + i, 72, 120, paint);
                pdf.finishPage(page);
            }
            try (FileOutputStream out = new FileOutputStream(pdfFile)) {
                pdf.writeTo(out);
            }
        } finally {
            pdf.close();
        }

        VisualDocxConverter.ConversionOutput result = VisualDocxConverter.convert(context, pdfFile, "two-pages.pdf", "application/pdf");
        assertEquals(2, result.pages);
        try (ZipFile zip = new ZipFile(result.file)) {
            assertNotNull(zip.getEntry("word/media/page_1.png"));
            assertNotNull(zip.getEntry("word/media/page_2.png"));
            String xml = read(zip, "word/document.xml");
            assertTrue(xml.contains("rIdImage1"));
            assertTrue(xml.contains("rIdImage2"));
            assertTrue(xml.contains("w:type w:val=\"nextPage\""));
        }
    }

    private static String read(ZipFile zip, String path) throws Exception {
        ZipEntry entry = zip.getEntry(path);
        assertNotNull(entry);
        try (InputStream in = zip.getInputStream(entry)) {
            byte[] bytes = new byte[(int) entry.getSize()];
            int offset = 0;
            while (offset < bytes.length) {
                int n = in.read(bytes, offset, bytes.length - offset);
                if (n < 0) break;
                offset += n;
            }
            return new String(bytes, 0, offset, StandardCharsets.UTF_8);
        }
    }
}
