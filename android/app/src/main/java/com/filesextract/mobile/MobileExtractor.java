package com.filesextract.mobile;

import android.content.Context;
import java.io.File;

interface MobileExtractor {
    Models.DocumentResult extract(Context context, File input, String filename, Models.ExtractionOptions options) throws Exception;
}
