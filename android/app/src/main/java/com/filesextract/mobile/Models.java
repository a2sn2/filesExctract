package com.filesextract.mobile;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Models {
    private Models() {}

    public static final class DocumentResult {
        public String schemaVersion = "1.0-mobile";
        public String filename;
        public String documentType;
        public String unitType;
        public int unitCount;
        public final Map<String, Object> metadata = new LinkedHashMap<>();
        public final List<Unit> units = new ArrayList<>();
        public final List<String> warnings = new ArrayList<>();
        public final List<String> unsupportedObjects = new ArrayList<>();
        public final List<Asset> assets = new ArrayList<>();
    }

    public static final class Unit {
        public int index;
        public String name;
        public final Map<String, Object> metadata = new LinkedHashMap<>();
        public final List<Element> elements = new ArrayList<>();

        public Unit(int index, String name) {
            this.index = index;
            this.name = name;
        }
    }

    public static final class Element {
        public int order;
        public String type;
        public String text;
        public final Map<String, Object> data = new LinkedHashMap<>();

        public Element(int order, String type, String text) {
            this.order = order;
            this.type = type;
            this.text = text;
        }
    }

    public static final class Asset {
        public String name;
        public String mimeType;
        public String source;
        public long size;
        public String sha256;
        public String outputPath;
        public transient byte[] bytes;
    }

    public static final class ExtractionOptions {
        public boolean enableOcr = true;
        public int maxPdfPages = 500;
        public long maxInputBytes = 250L * 1024L * 1024L;
        public long maxZipEntryBytes = 64L * 1024L * 1024L;
        public long maxTotalUncompressedBytes = 512L * 1024L * 1024L;
        public int maxOcrPages = 75;
    }

    public static final class ExtractionOutput {
        public DocumentResult result;
        public java.io.File directory;
        public java.io.File jsonFile;
        public java.io.File markdownFile;
    }
}
