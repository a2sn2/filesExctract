using System.Diagnostics;
using System.Text;

namespace FilesExtract.Converter;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new ConverterForm());
    }
}

internal sealed class ConverterForm : Form
{
    private readonly TextBox _source = new() { Dock = DockStyle.Fill, ReadOnly = true };
    private readonly TextBox _output = new() { Dock = DockStyle.Fill };
    private readonly TextBox _password = new() { Width = 180, UseSystemPasswordChar = true };
    private readonly ComboBox _target = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 150 };
    private readonly Button _convert = new() { Text = "Convert — Exact Layout", AutoSize = true };
    private readonly Button _open = new() { Text = "Open output folder", AutoSize = true };
    private readonly ProgressBar _progress = new() { Dock = DockStyle.Fill, Style = ProgressBarStyle.Marquee, Visible = false };
    private readonly TextBox _log = new() { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Both, WordWrap = false };

    public ConverterForm()
    {
        Text = "FilesExtract 0.5.0 — Exact Layout Converter";
        Width = 800;
        Height = 520;
        MinimumSize = new Size(680, 440);
        StartPosition = FormStartPosition.CenterScreen;

        _target.Items.AddRange(new object[] { "Word (.docx)", "PDF (.pdf)" });
        _target.SelectedIndex = 0;
        _output.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "FilesExtractOutput");

        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(14), ColumnCount = 1, RowCount = 7 };
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        root.Controls.Add(Row("Source", _source, Button("Browse", ChooseSource)));
        root.Controls.Add(Row("Output folder", _output, Button("Browse", ChooseOutput)));

        var options = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        options.Controls.Add(new Label { Text = "Target", AutoSize = true, Padding = new Padding(0, 6, 4, 0) });
        options.Controls.Add(_target);
        options.Controls.Add(new Label { Text = "Password (optional)", AutoSize = true, Padding = new Padding(18, 6, 4, 0) });
        options.Controls.Add(_password);
        root.Controls.Add(options);

        var note = new Label
        {
            AutoSize = true,
            MaximumSize = new Size(740, 0),
            Text = "Exact Layout preserves the page appearance by placing each rendered source page at the same page size. The page remains visually faithful; individual text elements are not editable in this mode."
        };
        root.Controls.Add(note);

        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        _convert.Click += async (_, _) => await ConvertAsync();
        _open.Click += (_, _) => OpenOutput();
        actions.Controls.Add(_convert);
        actions.Controls.Add(_open);
        root.Controls.Add(actions);
        root.Controls.Add(_progress);
        root.Controls.Add(_log);
        Controls.Add(root);
    }

    private static Control Row(string label, Control field, Button button)
    {
        var row = new TableLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, ColumnCount = 3 };
        row.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        row.Controls.Add(new Label { Text = label, AutoSize = true, Anchor = AnchorStyles.Left, Padding = new Padding(0, 6, 8, 0) }, 0, 0);
        row.Controls.Add(field, 1, 0);
        row.Controls.Add(button, 2, 0);
        return row;
    }

    private static Button Button(string text, EventHandler click)
    {
        var button = new Button { Text = text, AutoSize = true };
        button.Click += click;
        return button;
    }

    private void ChooseSource(object? sender, EventArgs e)
    {
        using var dialog = new OpenFileDialog
        {
            Filter = "Supported files|*.pdf;*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif;*.tif;*.tiff;*.doc;*.docx;*.docm;*.xls;*.xlsx;*.xlsm;*.ppt;*.pptx;*.pptm|All files|*.*"
        };
        if (dialog.ShowDialog(this) == DialogResult.OK) _source.Text = dialog.FileName;
    }

    private void ChooseOutput(object? sender, EventArgs e)
    {
        using var dialog = new FolderBrowserDialog { SelectedPath = _output.Text };
        if (dialog.ShowDialog(this) == DialogResult.OK) _output.Text = dialog.SelectedPath;
    }

    private void SetBusy(bool busy)
    {
        _progress.Visible = busy;
        _convert.Enabled = !busy;
    }

    private void Log(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return;
        _log.AppendText(text.TrimEnd() + Environment.NewLine);
    }

    private async Task ConvertAsync()
    {
        if (!File.Exists(_source.Text))
        {
            MessageBox.Show(this, "Choose a source file first.", "FilesExtract", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        Directory.CreateDirectory(_output.Text);
        var extension = _target.SelectedIndex == 0 ? ".docx" : ".pdf";
        var target = _target.SelectedIndex == 0 ? "docx" : "pdf";
        var destination = Path.Combine(_output.Text, Path.GetFileNameWithoutExtension(_source.Text) + "__exact" + extension);

        SetBusy(true);
        try
        {
            var root = Path.GetFullPath(AppContext.BaseDirectory);
            var python = Path.Combine(root, "runtime", "python", "python.exe");
            if (!File.Exists(python)) throw new FileNotFoundException("Bundled Python runtime is missing.", python);

            var info = new ProcessStartInfo
            {
                FileName = python,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                WorkingDirectory = root,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            foreach (var arg in new[] { "-m", "files_extract.conversion", _source.Text, "-o", destination, "--to", target, "--mode", "exact-layout" })
                info.ArgumentList.Add(arg);

            var lo = Path.Combine(root, "tools", "libreoffice", "program");
            info.Environment["PATH"] = lo + Path.PathSeparator + (Environment.GetEnvironmentVariable("PATH") ?? "");
            info.Environment["FILES_EXTRACT_BUNDLE_ROOT"] = root;
            info.Environment["PYTHONUTF8"] = "1";
            if (!string.IsNullOrWhiteSpace(_password.Text)) info.Environment["FILES_EXTRACT_PASSWORD"] = _password.Text;

            using var process = new Process { StartInfo = info };
            process.Start();
            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();
            await process.WaitForExitAsync();
            Log(await stdout);
            Log(await stderr);
            if (process.ExitCode != 0) throw new InvalidOperationException("Conversion failed. See the log for details.");
            MessageBox.Show(this, $"Converted successfully:\n{destination}", "FilesExtract", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            Log(ex.ToString());
            MessageBox.Show(this, ex.Message, "FilesExtract", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            _password.Clear();
            SetBusy(false);
        }
    }

    private void OpenOutput()
    {
        Directory.CreateDirectory(_output.Text);
        Process.Start(new ProcessStartInfo("explorer.exe", _output.Text) { UseShellExecute = true });
    }
}
