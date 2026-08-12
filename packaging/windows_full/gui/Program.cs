using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

namespace FilesExtract.Gui;

internal static class Program
{
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AttachConsole(uint dwProcessId);

    private const uint AttachParentProcess = 0xFFFFFFFF;

    [STAThread]
    private static void Main(string[] args)
    {
        if (args.Length > 0)
        {
            AttachConsole(AttachParentProcess);
            try
            {
                Console.SetOut(new StreamWriter(Console.OpenStandardOutput()) { AutoFlush = true });
                Console.SetError(new StreamWriter(Console.OpenStandardError()) { AutoFlush = true });
            }
            catch { }
            Environment.ExitCode = Backend.RunCliAsync(args).GetAwaiter().GetResult();
            return;
        }

        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}

internal static class Backend
{
    public static string Root => Path.GetFullPath(AppContext.BaseDirectory);
    public static string Python => Path.Combine(Root, "runtime", "python", "python.exe");

    public static ProcessStartInfo CreateStartInfo(IEnumerable<string> args)
    {
        if (!File.Exists(Python))
            throw new FileNotFoundException("The bundled Python runtime is missing.", Python);

        var psi = new ProcessStartInfo
        {
            FileName = Python,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WorkingDirectory = Root,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        psi.ArgumentList.Add("-m");
        psi.ArgumentList.Add("files_extract");
        foreach (var arg in args) psi.ArgumentList.Add(arg);

        var lo = Path.Combine(Root, "tools", "libreoffice", "program");
        var tess = Path.Combine(Root, "tools", "tesseract");
        var path = Environment.GetEnvironmentVariable("PATH") ?? "";
        psi.Environment["PATH"] = string.Join(Path.PathSeparator, new[] { lo, tess, path });
        psi.Environment["FILES_EXTRACT_BUNDLE_ROOT"] = Root;
        psi.Environment["TESSDATA_PREFIX"] = Path.Combine(tess, "tessdata");
        psi.Environment["DOCLING_ARTIFACTS_PATH"] = Path.Combine(Root, "models");
        psi.Environment["DOCLING_SERVE_ARTIFACTS_PATH"] = Path.Combine(Root, "models");
        psi.Environment["HF_HUB_OFFLINE"] = "1";
        psi.Environment["TRANSFORMERS_OFFLINE"] = "1";
        psi.Environment["HF_HUB_DISABLE_TELEMETRY"] = "1";
        psi.Environment["PYTHONUTF8"] = "1";
        return psi;
    }

    public static async Task<(int ExitCode, string Stdout, string Stderr)> RunAsync(IEnumerable<string> args)
    {
        using var process = new Process { StartInfo = CreateStartInfo(args) };
        process.Start();
        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();
        return (process.ExitCode, await stdoutTask, await stderrTask);
    }

    public static async Task<int> RunCliAsync(IEnumerable<string> args)
    {
        var result = await RunAsync(args);
        if (!string.IsNullOrEmpty(result.Stdout)) Console.Write(result.Stdout);
        if (!string.IsNullOrEmpty(result.Stderr)) Console.Error.Write(result.Stderr);
        return result.ExitCode;
    }
}

internal sealed class MainForm : Form
{
    private static readonly HashSet<string> Supported = new(StringComparer.OrdinalIgnoreCase)
    { ".pdf", ".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm", ".doc", ".xls", ".ppt" };

    private readonly ListBox _files = new() { Dock = DockStyle.Fill, HorizontalScrollbar = true };
    private readonly TextBox _output = new() { Dock = DockStyle.Fill };
    private readonly TextBox _password = new() { Dock = DockStyle.Fill, UseSystemPasswordChar = true };
    private readonly CheckBox _assets = new() { Text = "Extract embedded assets", Checked = true, AutoSize = true };
    private readonly CheckBox _pagination = new() { Text = "Render Word page reference", Checked = true, AutoSize = true };
    private readonly TextBox _log = new() { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Both, WordWrap = false, Font = new Font("Consolas", 9F) };
    private readonly ProgressBar _progress = new() { Dock = DockStyle.Fill, Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 30, Visible = false };
    private readonly Button _extract = new() { Text = "Extract", AutoSize = true };
    private readonly Button _doctor = new() { Text = "Diagnostics", AutoSize = true };
    private readonly Button _openOutput = new() { Text = "Open output", AutoSize = true };

    public MainForm()
    {
        Text = "FilesExtract 0.4.0 — Document Extraction";
        Width = 980;
        Height = 700;
        MinimumSize = new Size(760, 560);
        StartPosition = FormStartPosition.CenterScreen;
        AllowDrop = true;
        _output.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "FilesExtractOutput");

        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(12), ColumnCount = 1, RowCount = 7 };
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 34));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 66));

        var fileButtons = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        fileButtons.Controls.Add(Button("Add files", (_, _) => AddFiles()));
        fileButtons.Controls.Add(Button("Add folder", (_, _) => AddFolder()));
        fileButtons.Controls.Add(Button("Remove selected", (_, _) => RemoveSelected()));
        fileButtons.Controls.Add(Button("Clear", (_, _) => _files.Items.Clear()));
        root.Controls.Add(fileButtons);
        root.Controls.Add(_files);

        var outputRow = new TableLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, ColumnCount = 3 };
        outputRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        outputRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        outputRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        outputRow.Controls.Add(new Label { Text = "Output folder", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0);
        outputRow.Controls.Add(_output, 1, 0);
        outputRow.Controls.Add(Button("Browse", (_, _) => BrowseOutput()), 2, 0);
        root.Controls.Add(outputRow);

        var options = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        options.Controls.Add(_assets);
        options.Controls.Add(_pagination);
        options.Controls.Add(new Label { Text = "PDF password (optional)", AutoSize = true, Padding = new Padding(18, 6, 0, 0) });
        _password.Width = 180;
        options.Controls.Add(_password);
        root.Controls.Add(options);

        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        _extract.Click += async (_, _) => await ExtractAsync();
        _doctor.Click += async (_, _) => await DoctorAsync();
        _openOutput.Click += (_, _) => OpenOutput();
        actions.Controls.Add(_extract);
        actions.Controls.Add(_doctor);
        actions.Controls.Add(_openOutput);
        root.Controls.Add(actions);
        root.Controls.Add(_progress);
        root.Controls.Add(_log);
        Controls.Add(root);

        DragEnter += (_, e) =>
        {
            if (e.Data?.GetDataPresent(DataFormats.FileDrop) == true) e.Effect = DragDropEffects.Copy;
        };
        DragDrop += (_, e) =>
        {
            if (e.Data?.GetData(DataFormats.FileDrop) is string[] paths) AddPaths(paths);
        };

        Shown += async (_, _) => await DoctorAsync(false);
    }

    private static Button Button(string text, EventHandler click)
    {
        var button = new Button { Text = text, AutoSize = true };
        button.Click += click;
        return button;
    }

    private void AddFiles()
    {
        using var dialog = new OpenFileDialog
        {
            Multiselect = true,
            Filter = "Supported documents|*.pdf;*.docx;*.docm;*.xlsx;*.xlsm;*.pptx;*.pptm;*.doc;*.xls;*.ppt|All files|*.*"
        };
        if (dialog.ShowDialog(this) == DialogResult.OK) AddPaths(dialog.FileNames);
    }

    private void AddFolder()
    {
        using var dialog = new FolderBrowserDialog { Description = "Choose a folder containing documents" };
        if (dialog.ShowDialog(this) != DialogResult.OK) return;
        var files = Directory.EnumerateFiles(dialog.SelectedPath, "*", SearchOption.AllDirectories)
            .Where(p => Supported.Contains(Path.GetExtension(p)));
        AddPaths(files);
    }

    private void AddPaths(IEnumerable<string> paths)
    {
        var existing = new HashSet<string>(_files.Items.Cast<string>(), StringComparer.OrdinalIgnoreCase);
        foreach (var path in paths)
        {
            if (Directory.Exists(path))
            {
                AddPaths(Directory.EnumerateFiles(path, "*", SearchOption.AllDirectories));
                continue;
            }
            if (!File.Exists(path) || !Supported.Contains(Path.GetExtension(path))) continue;
            var full = Path.GetFullPath(path);
            if (existing.Add(full)) _files.Items.Add(full);
        }
    }

    private void RemoveSelected()
    {
        var selected = _files.SelectedItems.Cast<object>().ToArray();
        foreach (var item in selected) _files.Items.Remove(item);
    }

    private void BrowseOutput()
    {
        using var dialog = new FolderBrowserDialog { SelectedPath = _output.Text, Description = "Choose output folder" };
        if (dialog.ShowDialog(this) == DialogResult.OK) _output.Text = dialog.SelectedPath;
    }

    private void SetBusy(bool busy)
    {
        _progress.Visible = busy;
        _extract.Enabled = !busy;
        _doctor.Enabled = !busy;
    }

    private void Log(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return;
        _log.AppendText(text.TrimEnd() + Environment.NewLine);
        _log.SelectionStart = _log.TextLength;
        _log.ScrollToCaret();
    }

    private async Task DoctorAsync(bool showHeader = true)
    {
        SetBusy(true);
        try
        {
            if (showHeader) Log("=== Diagnostics ===");
            var result = await Backend.RunAsync(new[] { "doctor", "--json" });
            Log(result.Stdout);
            Log(result.Stderr);
            if (result.ExitCode != 0 && showHeader) MessageBox.Show(this, "Diagnostics reported an error. See the log.", "FilesExtract", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        catch (Exception ex)
        {
            Log(ex.ToString());
            if (showHeader) MessageBox.Show(this, ex.Message, "FilesExtract", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally { SetBusy(false); }
    }

    private async Task ExtractAsync()
    {
        var sources = _files.Items.Cast<string>().ToArray();
        if (sources.Length == 0)
        {
            MessageBox.Show(this, "Add at least one supported document first.", "FilesExtract", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        if (string.IsNullOrWhiteSpace(_output.Text)) return;

        Directory.CreateDirectory(_output.Text);
        SetBusy(true);
        var failed = 0;
        try
        {
            foreach (var source in sources)
            {
                var ext = Path.GetExtension(source).TrimStart('.').ToLowerInvariant();
                var name = Path.GetFileNameWithoutExtension(source);
                var destination = Path.Combine(_output.Text, $"{name}__{ext}_extracted");
                var args = new List<string> { "extract", source, "-o", destination };
                if (!_assets.Checked) args.Add("--no-assets");
                if (!_pagination.Checked) args.Add("--no-render-word-pages");
                if (!string.IsNullOrWhiteSpace(_password.Text))
                {
                    args.Add("--password");
                    args.Add(_password.Text);
                }

                Log($"> Extracting {source}");
                var result = await Backend.RunAsync(args);
                Log(result.Stdout);
                Log(result.Stderr);
                if (result.ExitCode != 0) failed++;
            }

            var message = failed == 0
                ? $"Completed successfully: {sources.Length} file(s)."
                : $"Completed with {failed} failure(s) out of {sources.Length}. Check the log.";
            MessageBox.Show(this, message, "FilesExtract", MessageBoxButtons.OK, failed == 0 ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
        }
        catch (Exception ex)
        {
            Log(ex.ToString());
            MessageBox.Show(this, ex.Message, "FilesExtract", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally { SetBusy(false); }
    }

    private void OpenOutput()
    {
        Directory.CreateDirectory(_output.Text);
        Process.Start(new ProcessStartInfo("explorer.exe", _output.Text) { UseShellExecute = true });
    }
}
