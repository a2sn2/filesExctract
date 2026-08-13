package com.filesextract.mobile;

import org.junit.Test;
import static org.junit.Assert.*;

public class SafeZipTest {
    @Test public void normalizeRemovesDotSegments() { assertEquals("xl/worksheets/sheet1.xml", SafeZip.normalize("xl/worksheets/../worksheets/./sheet1.xml")); }
    @Test public void resolveRelativeRelationshipTarget() {
        assertEquals("xl/worksheets/sheet1.xml", SafeZip.resolve("xl/workbook.xml", "worksheets/sheet1.xml"));
        assertEquals("word/media/image1.png", SafeZip.resolve("word/document.xml", "media/image1.png"));
    }
}
