package com.filesextract.mobile;

import android.graphics.Bitmap;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;

import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.io.File;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

final class OcrHelper {
    private OcrHelper() {}

    static String recognizePdfPage(File pdf, int pageIndex) throws Exception {
        try (ParcelFileDescriptor pfd = ParcelFileDescriptor.open(pdf, ParcelFileDescriptor.MODE_READ_ONLY);
             PdfRenderer renderer = new PdfRenderer(pfd)) {
            if (pageIndex < 0 || pageIndex >= renderer.getPageCount()) return "";
            try (PdfRenderer.Page page = renderer.openPage(pageIndex)) {
                int width = Math.max(1, page.getWidth());
                int height = Math.max(1, page.getHeight());
                double scale = Math.min(2.0, 2200.0 / Math.max(width, height));
                scale = Math.max(1.0, scale);
                int renderW = Math.max(1, (int) Math.round(width * scale));
                int renderH = Math.max(1, (int) Math.round(height * scale));
                Bitmap bitmap = Bitmap.createBitmap(renderW, renderH, Bitmap.Config.ARGB_8888);
                try {
                    page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                    return recognize(bitmap);
                } finally {
                    bitmap.recycle();
                }
            }
        }
    }

    private static String recognize(Bitmap bitmap) throws Exception {
        TextRecognizer recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        try {
            CountDownLatch latch = new CountDownLatch(1);
            AtomicReference<String> result = new AtomicReference<>("");
            AtomicReference<Exception> error = new AtomicReference<>();
            InputImage image = InputImage.fromBitmap(bitmap, 0);
            recognizer.process(image)
                    .addOnSuccessListener(text -> {
                        result.set(text == null ? "" : text.getText());
                        latch.countDown();
                    })
                    .addOnFailureListener(e -> {
                        error.set(e);
                        latch.countDown();
                    });
            if (!latch.await(45, TimeUnit.SECONDS)) throw new IllegalStateException("OCR timed out after 45 seconds.");
            if (error.get() != null) throw error.get();
            return result.get() == null ? "" : result.get().trim();
        } finally {
            recognizer.close();
        }
    }
}
