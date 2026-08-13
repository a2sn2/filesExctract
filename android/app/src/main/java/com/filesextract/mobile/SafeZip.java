package com.filesextract.mobile;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

final class SafeZip implements AutoCloseable {
    private final ZipFile zip;
    private final Models.ExtractionOptions options;
    private long totalRead = 0;

    SafeZip(File file, Models.ExtractionOptions options) throws Exception {
        this.zip = new ZipFile(file);
        this.options = options;
        preflight();
    }

    private void preflight() throws Exception {
        long declaredTotal = 0;
        Enumeration<? extends ZipEntry> entries = zip.entries();
        while (entries.hasMoreElements()) {
            ZipEntry e = entries.nextElement();
            validateName(e.getName());
            long size = e.getSize();
            if (size > options.maxZipEntryBytes) throw new IllegalArgumentException("ZIP entry exceeds mobile safety limit: " + e.getName());
            if (size > 0) declaredTotal += size;
            if (declaredTotal > options.maxTotalUncompressedBytes) throw new IllegalArgumentException("Archive exceeds mobile uncompressed-size limit.");
        }
    }

    boolean has(String path) { return zip.getEntry(normalize(path)) != null; }

    byte[] read(String path) throws Exception {
        String normalized = normalize(path);
        validateName(normalized);
        ZipEntry e = zip.getEntry(normalized);
        if (e == null) return null;
        try (InputStream in = zip.getInputStream(e); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[32 * 1024];
            long entryRead = 0;
            int n;
            while ((n = in.read(buffer)) != -1) {
                entryRead += n;
                totalRead += n;
                if (entryRead > options.maxZipEntryBytes) throw new IllegalArgumentException("ZIP entry exceeds mobile safety limit while reading: " + normalized);
                if (totalRead > options.maxTotalUncompressedBytes) throw new IllegalArgumentException("Archive exceeds mobile uncompressed-size limit while reading.");
                out.write(buffer, 0, n);
            }
            return out.toByteArray();
        }
    }

    List<String> namesWithPrefix(String prefix) {
        String p = normalize(prefix);
        List<String> names = new ArrayList<>();
        Enumeration<? extends ZipEntry> entries = zip.entries();
        while (entries.hasMoreElements()) {
            ZipEntry e = entries.nextElement();
            if (!e.isDirectory() && e.getName().startsWith(p)) names.add(e.getName());
        }
        Collections.sort(names);
        return names;
    }

    static String normalize(String path) {
        String p = path.replace('\\', '/');
        while (p.startsWith("/")) p = p.substring(1);
        List<String> parts = new ArrayList<>();
        for (String part : p.split("/")) {
            if (part.isEmpty() || ".".equals(part)) continue;
            if ("..".equals(part)) {
                if (!parts.isEmpty()) parts.remove(parts.size() - 1);
            } else {
                parts.add(part);
            }
        }
        return String.join("/", parts);
    }

    static String resolve(String baseFile, String target) {
        if (target.startsWith("/")) return normalize(target);
        int slash = baseFile.lastIndexOf('/');
        String base = slash >= 0 ? baseFile.substring(0, slash + 1) : "";
        return normalize(base + target);
    }

    private static void validateName(String name) {
        String normalized = normalize(name);
        if (normalized.startsWith("../") || normalized.equals("..") || name.indexOf('\0') >= 0) {
            throw new IllegalArgumentException("Unsafe ZIP path: " + name);
        }
    }

    @Override public void close() throws Exception { zip.close(); }
}
