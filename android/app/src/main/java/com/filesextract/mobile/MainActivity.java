package com.filesextract.mobile;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.ArrayList;

public final class MainActivity extends Activity {
    private static final int PICK_FILE = 1001;
    private Uri selectedUri;
    private String selectedName;
    private TextView fileLabel;
    private TextView status;
    private Button extractButton;
    private Button shareButton;
    private ProgressBar progress;
    private CheckBox ocr;
    private Models.ExtractionOutput lastOutput;

    @Override protected void onCreate(Bundle savedInstanceState) { super.onCreate(savedInstanceState); setContentView(buildUi()); }

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(24), dp(20), dp(24));
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        scroll.addView(root, new ScrollView.LayoutParams(-1, -2));
        TextView title = text("FilesExtract", 30, true); title.setTextColor(Color.rgb(17, 24, 39)); root.addView(title, lp(-1, -2, 0));
        TextView subtitle = text("Extract PDF, Word, Excel and PowerPoint into structured JSON + Markdown — locally on Android.", 16, false); subtitle.setTextColor(Color.DKGRAY); subtitle.setPadding(0, dp(8), 0, dp(24)); root.addView(subtitle, lp(-1, -2, 0));
        Button pick = new Button(this); pick.setText("Choose document"); pick.setOnClickListener(v -> chooseFile()); root.addView(pick, lp(-1, dp(52), 0));
        fileLabel = text("No file selected", 14, false); fileLabel.setPadding(0, dp(10), 0, dp(14)); root.addView(fileLabel, lp(-1, -2, 0));
        ocr = new CheckBox(this); ocr.setText("OCR scanned PDF pages (on-device)"); ocr.setChecked(true); root.addView(ocr, lp(-1, -2, 0));
        extractButton = new Button(this); extractButton.setText("Extract"); extractButton.setEnabled(false); extractButton.setOnClickListener(v -> startExtraction()); root.addView(extractButton, lp(-1, dp(52), dp(12)));
        progress = new ProgressBar(this); progress.setIndeterminate(true); progress.setVisibility(View.GONE); LinearLayout.LayoutParams pp = lp(-2, -2, dp(18)); pp.gravity = Gravity.CENTER_HORIZONTAL; root.addView(progress, pp);
        status = text("Ready", 14, false); status.setTextIsSelectable(true); status.setPadding(0, dp(16), 0, dp(16)); root.addView(status, lp(-1, -2, 0));
        shareButton = new Button(this); shareButton.setText("Share JSON + Markdown"); shareButton.setEnabled(false); shareButton.setOnClickListener(v -> shareOutput()); root.addView(shareButton, lp(-1, dp(52), 0));
        TextView note = text("Security: files are processed locally. Macros/OLE objects are never executed. Output is stored under the app's Documents/FilesExtract directory.", 12, false); note.setTextColor(Color.GRAY); note.setPadding(0, dp(22), 0, 0); root.addView(note, lp(-1, -2, 0));
        return scroll;
    }

    private void chooseFile() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","application/vnd.ms-excel.sheet.macroEnabled.12","application/vnd.openxmlformats-officedocument.presentationml.presentation"});
        startActivityForResult(intent, PICK_FILE);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_FILE && resultCode == RESULT_OK && data != null && data.getData() != null) {
            selectedUri = data.getData(); selectedName = displayName(selectedUri); if (selectedName == null || selectedName.trim().isEmpty()) selectedName = "document";
            fileLabel.setText(selectedName); extractButton.setEnabled(true); shareButton.setEnabled(false); lastOutput = null; status.setText("Selected. Tap Extract.");
            try { getContentResolver().takePersistableUriPermission(selectedUri, Intent.FLAG_GRANT_READ_URI_PERMISSION); } catch (Exception ignored) {}
        }
    }

    private void startExtraction() {
        if (selectedUri == null) return;
        extractButton.setEnabled(false); shareButton.setEnabled(false); progress.setVisibility(View.VISIBLE); status.setText("Extracting… Large files and OCR may take a while.");
        Uri uri = selectedUri; String name = selectedName; boolean enableOcr = ocr.isChecked();
        new Thread(() -> {
            File temp = null;
            try {
                temp = copyToCache(uri, name);
                Models.ExtractionOptions options = new Models.ExtractionOptions(); options.enableOcr = enableOcr;
                Models.ExtractionOutput output = MobileEngine.extract(getApplicationContext(), temp, name, options); lastOutput = output;
                String message = "Success\n\nType: " + output.result.documentType + "\nUnits: " + output.result.unitCount + "\nAssets: " + output.result.assets.size() + "\nWarnings: " + output.result.warnings.size() + "\nUnsupported: " + output.result.unsupportedObjects.size() + "\n\nOutput:\n" + output.directory.getAbsolutePath();
                runOnUiThread(() -> { progress.setVisibility(View.GONE); extractButton.setEnabled(true); shareButton.setEnabled(true); status.setText(message); });
            } catch (Exception ex) {
                String message = ex.getClass().getSimpleName() + ": " + (ex.getMessage() == null ? "Extraction failed" : ex.getMessage());
                runOnUiThread(() -> { progress.setVisibility(View.GONE); extractButton.setEnabled(true); status.setText("Failed\n\n" + message); Toast.makeText(MainActivity.this, "Extraction failed", Toast.LENGTH_LONG).show(); });
            } finally { if (temp != null) temp.delete(); }
        }, "files-extract-worker").start();
    }

    private File copyToCache(Uri uri, String name) throws Exception {
        String suffix = ".bin"; int dot = name.lastIndexOf('.'); if (dot >= 0 && dot < name.length() - 1) suffix = name.substring(dot);
        File temp = File.createTempFile("filesextract-", suffix, getCacheDir()); ContentResolver resolver = getContentResolver();
        try (InputStream in = resolver.openInputStream(uri); FileOutputStream out = new FileOutputStream(temp)) {
            if (in == null) throw new IllegalArgumentException("Could not open selected document.");
            byte[] buffer = new byte[64 * 1024]; long total = 0; int n;
            while ((n = in.read(buffer)) != -1) { total += n; if (total > 250L * 1024L * 1024L) throw new IllegalArgumentException("File exceeds the 250 MB mobile limit."); out.write(buffer, 0, n); }
        }
        return temp;
    }

    private void shareOutput() {
        if (lastOutput == null) return;
        ArrayList<Uri> uris = new ArrayList<>(); String authority = getPackageName() + ".files";
        uris.add(FileProvider.getUriForFile(this, authority, lastOutput.jsonFile)); uris.add(FileProvider.getUriForFile(this, authority, lastOutput.markdownFile));
        Intent share = new Intent(Intent.ACTION_SEND_MULTIPLE); share.setType("text/*"); share.putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris); share.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION); startActivity(Intent.createChooser(share, "Share FilesExtract output"));
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) { if (cursor != null && cursor.moveToFirst()) return cursor.getString(0); } catch (Exception ignored) {}
        String path = uri.getLastPathSegment(); return path == null ? "document" : path;
    }

    private TextView text(String value, int sp, boolean bold) { TextView tv = new TextView(this); tv.setText(value); tv.setTextSize(sp); if (bold) tv.setTypeface(tv.getTypeface(), android.graphics.Typeface.BOLD); return tv; }
    private LinearLayout.LayoutParams lp(int w, int h, int top) { LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(w, h); p.topMargin = top; return p; }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}
