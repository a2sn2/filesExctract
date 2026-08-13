package com.filesextract.mobile;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.pdf.PdfRenderer;
import android.os.Environment;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * Creates a DOCX whose pages visually match the source PDF/image.
 *
 * This mode deliberately prioritizes appearance over editability: each source page is
 * rendered as a full-page image and placed at the same physical page size in Word.
 * It is the only deterministic way to keep arbitrary PDF drawing/text/table layouts
 * visually unchanged across Word renderers without reflowing the content.
 */
final class VisualDocxConverter {
    private static final int MAX_PDF_PAGES = 250;
    private static final int MAX_RENDER_EDGE_PX = 4200;
    private static final double MAX_RENDER_SCALE = 3.0; // 216 DPI for standard PDF pages.
    private static final double MAX_WORD_PAGE_POINTS = 22.0 * 72.0;

    private VisualDocxConverter() {}

    static final class ConversionOutput {
        final File file;
        final int pages;
        final String mode;

        ConversionOutput(File file, int pages, String mode) {
            this.file = file;
            this.pages = pages;
            this.mode = mode;
        }
    }

    private static final class PageSpec {
        final int index;
        final double widthPt;
        final double heightPt;

        PageSpec(int index, double widthPt, double heightPt) {
            this.index = index;
            double scale = Math.min(1.0, MAX_WORD_PAGE_POINTS / Math.max(widthPt, heightPt));
            this.widthPt = Math.max(1.0, widthPt * scale);
            this.heightPt = Math.max(1.0, heightPt * scale);
        }

        String relationshipId() { return "rIdImage" + index; }
        String mediaPath() { return "word/media/page_" + index + ".png"; }
    }

    static boolean supports(String filename, String mimeType) {
        String mime = mimeType == null ? "" : mimeType.toLowerCase(Locale.ROOT);
        if ("application/pdf".equals(mime) || mime.startsWith("image/")) return true;
        String name = filename == null ? "" : filename.toLowerCase(Locale.ROOT);
        return name.endsWith(".pdf") || name.endsWith(".png") || name.endsWith(".jpg")
                || name.endsWith(".jpeg") || name.endsWith(".webp") || name.endsWith(".bmp")
                || name.endsWith(".gif") || name.endsWith(".heic") || name.endsWith(".heif");
    }

    static ConversionOutput convert(Context context, File input, String filename, String mimeType) throws Exception {
        if (input == null || !input.isFile()) throw new IllegalArgumentException("Source file does not exist.");
        if (!supports(filename, mimeType)) throw new IllegalArgumentException("Exact-layout Word conversion currently supports PDF and image files.");

        File base = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS);
        if (base == null) base = context.getFilesDir();
        File dir = new File(base, "FilesExtract/Conversions");
        if (!dir.mkdirs() && !dir.exists()) throw new IllegalStateException("Could not create conversion output directory.");
        File output = uniqueFile(dir, safeStem(filename) + "_exact-layout.docx");

        boolean pdf = "application/pdf".equalsIgnoreCase(mimeType)
                || (filename != null && filename.toLowerCase(Locale.ROOT).endsWith(".pdf"));
        int pages = pdf ? convertPdf(input, output) : convertImage(input, output);
        return new ConversionOutput(output, pages, "visual_exact");
    }

    private static int convertPdf(File input, File output) throws Exception {
        List<PageSpec> specs = new ArrayList<>();
        try (ParcelFileDescriptor pfd = ParcelFileDescriptor.open(input, ParcelFileDescriptor.MODE_READ_ONLY);
             PdfRenderer renderer = new PdfRenderer(pfd);
             ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(output))) {
            int count = renderer.getPageCount();
            if (count <= 0) throw new IllegalArgumentException("PDF contains no pages.");
            if (count > MAX_PDF_PAGES) throw new IllegalArgumentException("PDF has " + count + " pages; exact-layout mobile limit is " + MAX_PDF_PAGES + ".");

            writePackageSkeleton(zip);
            for (int i = 0; i < count; i++) {
                try (PdfRenderer.Page page = renderer.openPage(i)) {
                    int widthPt = Math.max(1, page.getWidth());
                    int heightPt = Math.max(1, page.getHeight());
                    PageSpec spec = new PageSpec(i + 1, widthPt, heightPt);
                    specs.add(spec);

                    double scale = Math.min(MAX_RENDER_SCALE, (double) MAX_RENDER_EDGE_PX / Math.max(widthPt, heightPt));
                    scale = Math.max(0.2, scale);
                    int renderW = Math.max(1, (int) Math.round(widthPt * scale));
                    int renderH = Math.max(1, (int) Math.round(heightPt * scale));
                    Bitmap bitmap = Bitmap.createBitmap(renderW, renderH, Bitmap.Config.ARGB_8888);
                    try {
                        Canvas canvas = new Canvas(bitmap);
                        canvas.drawColor(Color.WHITE);
                        Matrix transform = new Matrix();
                        transform.setScale((float) scale, (float) scale);
                        page.render(bitmap, null, transform, PdfRenderer.Page.RENDER_MODE_FOR_PRINT);
                        writePng(zip, spec.mediaPath(), bitmap);
                    } finally {
                        bitmap.recycle();
                    }
                }
            }
            writeDocumentRelationships(zip, specs);
            writeDocumentXml(zip, specs);
        } catch (Exception ex) {
            // Never leave a corrupt file that looks like a successful conversion.
            output.delete();
            throw ex;
        }
        return specs.size();
    }

    private static int convertImage(File input, File output) throws Exception {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(input.getAbsolutePath(), bounds);
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw new IllegalArgumentException("Could not decode the selected image.");

        int sample = 1;
        while (Math.max(bounds.outWidth / sample, bounds.outHeight / sample) > 5000) sample *= 2;
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sample;
        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
        Bitmap source = BitmapFactory.decodeFile(input.getAbsolutePath(), options);
        if (source == null) throw new IllegalArgumentException("Could not decode the selected image.");

        // Android images normally do not carry a reliable page size. 96 DPI keeps the
        // source aspect ratio and gives Word a deterministic physical size.
        double widthPt = bounds.outWidth * 72.0 / 96.0;
        double heightPt = bounds.outHeight * 72.0 / 96.0;
        PageSpec spec = new PageSpec(1, widthPt, heightPt);
        List<PageSpec> specs = new ArrayList<>();
        specs.add(spec);

        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(output))) {
            writePackageSkeleton(zip);
            writePng(zip, spec.mediaPath(), source);
            writeDocumentRelationships(zip, specs);
            writeDocumentXml(zip, specs);
        } catch (Exception ex) {
            output.delete();
            throw ex;
        } finally {
            source.recycle();
        }
        return 1;
    }

    private static void writePackageSkeleton(ZipOutputStream zip) throws Exception {
        writeUtf8(zip, "[Content_Types].xml",
                "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                        + "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                        + "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
                        + "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
                        + "<Default Extension=\"png\" ContentType=\"image/png\"/>"
                        + "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
                        + "</Types>");
        writeUtf8(zip, "_rels/.rels",
                "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                        + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                        + "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
                        + "</Relationships>");
    }

    private static void writeDocumentRelationships(ZipOutputStream zip, List<PageSpec> specs) throws Exception {
        StringBuilder xml = new StringBuilder();
        xml.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>")
                .append("<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">");
        for (PageSpec spec : specs) {
            xml.append("<Relationship Id=\"").append(spec.relationshipId())
                    .append("\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image\" Target=\"media/page_")
                    .append(spec.index).append(".png\"/>");
        }
        xml.append("</Relationships>");
        writeUtf8(zip, "word/_rels/document.xml.rels", xml.toString());
    }

    private static void writeDocumentXml(ZipOutputStream zip, List<PageSpec> specs) throws Exception {
        StringBuilder xml = new StringBuilder(8192 + specs.size() * 1800);
        xml.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>")
                .append("<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" ")
                .append("xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" ")
                .append("xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" ")
                .append("xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" ")
                .append("xmlns:pic=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">")
                .append("<w:body>");

        for (int i = 0; i < specs.size(); i++) {
            PageSpec spec = specs.get(i);
            boolean last = i == specs.size() - 1;
            long cx = Math.max(1L, Math.round(spec.widthPt * 12700.0));
            long cy = Math.max(1L, Math.round(spec.heightPt * 12700.0));
            int widthTwips = Math.max(20, (int) Math.round(spec.widthPt * 20.0));
            int heightTwips = Math.max(20, (int) Math.round(spec.heightPt * 20.0));

            xml.append("<w:p><w:pPr><w:spacing w:before=\"0\" w:after=\"0\" w:line=\"1\" w:lineRule=\"exact\"/>");
            if (!last) appendSectionProperties(xml, widthTwips, heightTwips, true);
            xml.append("</w:pPr><w:r><w:drawing>")
                    .append("<wp:anchor distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\" simplePos=\"0\" relativeHeight=\"251658240\" behindDoc=\"0\" locked=\"1\" layoutInCell=\"1\" allowOverlap=\"1\">")
                    .append("<wp:simplePos x=\"0\" y=\"0\"/>")
                    .append("<wp:positionH relativeFrom=\"page\"><wp:posOffset>0</wp:posOffset></wp:positionH>")
                    .append("<wp:positionV relativeFrom=\"page\"><wp:posOffset>0</wp:posOffset></wp:positionV>")
                    .append("<wp:extent cx=\"").append(cx).append("\" cy=\"").append(cy).append("\"/>")
                    .append("<wp:effectExtent l=\"0\" t=\"0\" r=\"0\" b=\"0\"/><wp:wrapNone/>")
                    .append("<wp:docPr id=\"").append(spec.index).append("\" name=\"Source page ").append(spec.index).append("\"/>")
                    .append("<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect=\"1\"/></wp:cNvGraphicFramePr>")
                    .append("<a:graphic><a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">")
                    .append("<pic:pic><pic:nvPicPr><pic:cNvPr id=\"").append(spec.index).append("\" name=\"page_").append(spec.index).append(".png\"/><pic:cNvPicPr/></pic:nvPicPr>")
                    .append("<pic:blipFill><a:blip r:embed=\"").append(spec.relationshipId()).append("\"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>")
                    .append("<pic:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"").append(cx).append("\" cy=\"").append(cy).append("\"/></a:xfrm>")
                    .append("<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>")
                    .append("</a:graphicData></a:graphic></wp:anchor>")
                    .append("</w:drawing></w:r></w:p>");
        }

        PageSpec last = specs.get(specs.size() - 1);
        appendSectionProperties(xml,
                Math.max(20, (int) Math.round(last.widthPt * 20.0)),
                Math.max(20, (int) Math.round(last.heightPt * 20.0)),
                false);
        xml.append("</w:body></w:document>");
        writeUtf8(zip, "word/document.xml", xml.toString());
    }

    private static void appendSectionProperties(StringBuilder xml, int widthTwips, int heightTwips, boolean nextPage) {
        xml.append("<w:sectPr>");
        if (nextPage) xml.append("<w:type w:val=\"nextPage\"/>");
        xml.append("<w:pgSz w:w=\"").append(widthTwips).append("\" w:h=\"").append(heightTwips).append("\"");
        if (widthTwips > heightTwips) xml.append(" w:orient=\"landscape\"");
        xml.append("/>")
                .append("<w:pgMar w:top=\"0\" w:right=\"0\" w:bottom=\"0\" w:left=\"0\" w:header=\"0\" w:footer=\"0\" w:gutter=\"0\"/>")
                .append("</w:sectPr>");
    }

    private static void writePng(ZipOutputStream zip, String path, Bitmap bitmap) throws Exception {
        zip.putNextEntry(new ZipEntry(path));
        if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, zip)) throw new IllegalStateException("Could not encode rendered page image.");
        zip.closeEntry();
    }

    private static void writeUtf8(ZipOutputStream zip, String path, String text) throws Exception {
        zip.putNextEntry(new ZipEntry(path));
        zip.write(text.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }

    private static String safeStem(String filename) {
        String name = filename == null || filename.trim().isEmpty() ? "document" : filename.trim();
        int slash = Math.max(name.lastIndexOf('/'), name.lastIndexOf('\\'));
        if (slash >= 0) name = name.substring(slash + 1);
        int dot = name.lastIndexOf('.');
        if (dot > 0) name = name.substring(0, dot);
        name = name.replaceAll("[^A-Za-z0-9._-]", "_");
        return name.isEmpty() ? "document" : name;
    }

    private static File uniqueFile(File dir, String name) {
        File file = new File(dir, name);
        if (!file.exists()) return file;
        int dot = name.lastIndexOf('.');
        String stem = dot > 0 ? name.substring(0, dot) : name;
        String ext = dot > 0 ? name.substring(dot) : "";
        int i = 2;
        while (true) {
            file = new File(dir, stem + "_" + i + ext);
            if (!file.exists()) return file;
            i++;
        }
    }
}
