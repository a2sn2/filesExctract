param(
    [string]$OutputRoot = "release/windows-full"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repo
$app = [System.IO.Path]::GetFullPath((Join-Path $repo $OutputRoot))
$runtime = Join-Path $app "runtime"
$pythonDir = Join-Path $runtime "python"
$sitePackages = Join-Path $pythonDir "Lib/site-packages"
$tools = Join-Path $app "tools"
$models = Join-Path $app "models"

if (Test-Path $app) { Remove-Item $app -Recurse -Force }
New-Item -ItemType Directory -Force -Path $app, $runtime, $pythonDir, $sitePackages, $tools, $models | Out-Null

Write-Host "== Builder dependencies =="
python -m pip install --upgrade pip
python -m pip install -e ".[full,dev]" pip-licenses
if ($LASTEXITCODE -ne 0) { throw "Failed to install build dependencies." }

Write-Host "== GUI =="
dotnet publish "packaging/windows_full/gui/FilesExtract.Gui.csproj" `
    -c Release `
    -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:PublishTrimmed=false `
    -o $app
if ($LASTEXITCODE -ne 0) { throw "Failed to publish the Windows GUI." }

Write-Host "== Embedded Python =="
$pyVersion = "3.12.10"
$pyZip = Join-Path $env:RUNNER_TEMP "python-embed.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-embed-amd64.zip" -OutFile $pyZip
Expand-Archive $pyZip -DestinationPath $pythonDir -Force
$pth = Get-ChildItem $pythonDir -Filter "python*._pth" | Select-Object -First 1
if (-not $pth) { throw "Python embedded _pth file was not found." }
@"
python312.zip
.
Lib\site-packages
import site
"@ | Set-Content -Path $pth.FullName -Encoding ASCII

Write-Host "== Full Python extraction runtime =="
python -m pip install --upgrade --target $sitePackages ".[full]"
if ($LASTEXITCODE -ne 0) { throw "Failed to populate the embedded Python runtime." }

# Record the exact Python distributions that landed in the private runtime.
$freezeCode = @'
import importlib.metadata as m
rows = []
for d in m.distributions():
    name = d.metadata.get("Name") or d.metadata.get("Summary") or "unknown"
    rows.append(name + "==" + d.version)
print("\n".join(sorted(set(rows), key=str.lower)))
'@
$freezeOutput = & (Join-Path $pythonDir "python.exe") -c $freezeCode
if ($LASTEXITCODE -ne 0) { throw "Could not enumerate the embedded Python runtime." }
$freezeOutput | Set-Content -Path (Join-Path $app "runtime-freeze.txt") -Encoding UTF8

Write-Host "== Offline Docling models =="
& docling-tools models download layout tableformer -o $models
if ($LASTEXITCODE -ne 0) { throw "Failed to prefetch Docling layout/table models." }

Write-Host "== Tesseract =="
# Use a checksum-pinned Windows installer rather than a package manager so the
# resulting product is reproducible and independent from Chocolatey state.
$tessVersion = "5.5.3.20260724"
$tessInstaller = Join-Path $env:RUNNER_TEMP "tesseract-ocr-w64-setup-$tessVersion.exe"
$tessUrl = "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-$tessVersion.exe"
$tessExpectedSha256 = "bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4"
Invoke-WebRequest $tessUrl -OutFile $tessInstaller
$tessActualSha256 = (Get-FileHash $tessInstaller -Algorithm SHA256).Hash.ToLowerInvariant()
if ($tessActualSha256 -ne $tessExpectedSha256) {
    throw "Tesseract installer checksum mismatch. Expected $tessExpectedSha256, got $tessActualSha256."
}
$tessInstallRoot = Join-Path $env:RUNNER_TEMP "FilesExtract-Tesseract"
if (Test-Path $tessInstallRoot) { Remove-Item $tessInstallRoot -Recurse -Force }
$process = Start-Process -FilePath $tessInstaller -ArgumentList "/S", "/D=$tessInstallRoot" -Wait -PassThru -NoNewWindow
if ($process.ExitCode -ne 0) { throw "Tesseract installer failed with exit code $($process.ExitCode)." }
$tessExe = Join-Path $tessInstallRoot "tesseract.exe"
if (-not (Test-Path $tessExe)) {
    $tessExe = Get-ChildItem $tessInstallRoot -Filter "tesseract.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $tessExe -or -not (Test-Path $tessExe)) { throw "Tesseract executable was not found after verified installation." }
$tessRoot = Split-Path $tessExe -Parent
$tessDest = Join-Path $tools "tesseract"
Copy-Item $tessRoot $tessDest -Recurse -Force
$tessdata = Join-Path $tessDest "tessdata"
New-Item -ItemType Directory -Force -Path $tessdata | Out-Null
$tessdataCommit = "87416418657359cb625c412a48b6e1d6d41c29bd"
Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/$tessdataCommit/eng.traineddata" -OutFile (Join-Path $tessdata "eng.traineddata")
Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/$tessdataCommit/ara.traineddata" -OutFile (Join-Path $tessdata "ara.traineddata")
Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tesseract/5.5.3/LICENSE" -OutFile (Join-Path $app "LICENSE-TESSERACT.txt")

Write-Host "== LibreOffice =="
# The official TDF mirror list publishes both the exact MSI filename and its
# SHA-256. Administrative extraction keeps LibreOffice private to FilesExtract;
# the target PC does not need LibreOffice installed globally.
$loVersion = "26.2.5"
$loMsi = Join-Path $env:RUNNER_TEMP "LibreOffice_${loVersion}_Win_x86-64.msi"
$loUrl = "https://download.documentfoundation.org/libreoffice/stable/$loVersion/win/x86_64/LibreOffice_${loVersion}_Win_x86-64.msi"
$loExpectedSha256 = "f15ba07bfcb0186986cf3171063506f5d207c11f8cc051ba0d135209e9e915f9"
Invoke-WebRequest $loUrl -OutFile $loMsi -MaximumRedirection 10
$loActualSha256 = (Get-FileHash $loMsi -Algorithm SHA256).Hash.ToLowerInvariant()
if ($loActualSha256 -ne $loExpectedSha256) {
    throw "LibreOffice MSI checksum mismatch. Expected $loExpectedSha256, got $loActualSha256."
}
$loAdminRoot = Join-Path $env:RUNNER_TEMP "FilesExtract-LibreOffice-Admin"
if (Test-Path $loAdminRoot) { Remove-Item $loAdminRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $loAdminRoot | Out-Null
$loArgs = @("/a", $loMsi, "/qn", "/norestart", "TARGETDIR=$loAdminRoot")
$loProcess = Start-Process -FilePath "msiexec.exe" -ArgumentList $loArgs -Wait -PassThru -NoNewWindow
if ($loProcess.ExitCode -ne 0) { throw "LibreOffice administrative extraction failed with exit code $($loProcess.ExitCode)." }
$loExe = Get-ChildItem $loAdminRoot -Filter "soffice.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if (-not $loExe -or -not (Test-Path $loExe)) { throw "LibreOffice soffice.exe was not found in the administratively extracted MSI." }
$loRoot = Split-Path (Split-Path $loExe -Parent) -Parent
$loDest = Join-Path $tools "libreoffice"
Copy-Item $loRoot $loDest -Recurse -Force
$bundledSoffice = Join-Path $loDest "program\soffice.exe"
if (-not (Test-Path $bundledSoffice)) { throw "Bundled LibreOffice layout is invalid: program\soffice.exe is missing." }
$loLicense = Get-ChildItem $loRoot -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^(license|copying)' } | Select-Object -First 1
if ($loLicense) { Copy-Item $loLicense.FullName (Join-Path $app "LICENSE-LIBREOFFICE.txt") -Force }

Write-Host "== Distribution metadata =="
Copy-Item "packaging/windows_full/README-WINDOWS-FULL.txt" (Join-Path $app "README.txt") -Force
if (Test-Path "CHANGELOG.md") { Copy-Item "CHANGELOG.md" (Join-Path $app "CHANGELOG.md") -Force }

& pip-licenses --format=markdown --with-urls --output-file (Join-Path $app "THIRD-PARTY-PYTHON-LICENSES.md")
if ($LASTEXITCODE -ne 0) { throw "pip-licenses failed." }

@"
@echo off
setlocal
set "ROOT=%~dp0"
set "FILES_EXTRACT_BUNDLE_ROOT=%ROOT%"
set "PATH=%ROOT%tools\libreoffice\program;%ROOT%tools\tesseract;%PATH%"
set "TESSDATA_PREFIX=%ROOT%tools\tesseract\tessdata"
set "DOCLING_ARTIFACTS_PATH=%ROOT%models"
set "DOCLING_SERVE_ARTIFACTS_PATH=%ROOT%models"
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "HF_HUB_DISABLE_TELEMETRY=1"
set "PYTHONUTF8=1"
"%ROOT%runtime\python\python.exe" -m files_extract %*
exit /b %ERRORLEVEL%
"@ | Set-Content -Path (Join-Path $app "files-extract-cli.cmd") -Encoding ASCII

$commit = (& git rev-parse HEAD).Trim()
$buildInfo = [ordered]@{
    product = "FilesExtract"
    version = "0.4.0"
    platform = "windows-x64"
    source_commit = $commit
    build_time_utc = [DateTime]::UtcNow.ToString("o")
    embedded_python = $pyVersion
    tesseract = $tessVersion
    tessdata_fast_commit = $tessdataCommit
    libreoffice = $loVersion
    offline_docling_models = @("layout", "tableformer")
    bundled_ocr_languages = @("ara", "eng")
}
$buildInfo | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $app "build-info.json") -Encoding UTF8

Write-Host "Windows full runtime created at $app"
