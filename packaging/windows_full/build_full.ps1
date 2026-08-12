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

Write-Host "== Offline Docling models =="
& docling-tools models download layout tableformer -o $models
if ($LASTEXITCODE -ne 0) { throw "Failed to prefetch Docling layout/table models." }

function Ensure-ChocoPackage([string]$Name) {
    & choco install $Name -y --no-progress
    return $LASTEXITCODE
}

Write-Host "== Tesseract =="
# Use the Windows installer published from the Tesseract project release rather
# than depending on Chocolatey's community repository at build time. The binary
# is checksum-pinned so the build fails closed if the payload ever changes.
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
Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/eng.traineddata" -OutFile (Join-Path $tessdata "eng.traineddata")
Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/ara.traineddata" -OutFile (Join-Path $tessdata "ara.traineddata")
Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tesseract/main/LICENSE" -OutFile (Join-Path $app "LICENSE-TESSERACT.txt")

Write-Host "== LibreOffice =="
$loExe = $null
$loCandidates = @(
    "C:\Program Files\LibreOffice\program\soffice.exe",
    "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
)
foreach ($candidate in $loCandidates) { if (Test-Path $candidate) { $loExe = $candidate; break } }
if (-not $loExe) {
    $exit = Ensure-ChocoPackage "libreoffice-fresh"
    if ($exit -ne 0) {
        $exit = Ensure-ChocoPackage "libreoffice"
        if ($exit -ne 0) { throw "Chocolatey could not install LibreOffice." }
    }
    foreach ($candidate in $loCandidates) { if (Test-Path $candidate) { $loExe = $candidate; break } }
}
if (-not $loExe) { throw "LibreOffice was not found after installation." }
$loRoot = Split-Path (Split-Path $loExe -Parent) -Parent
$loDest = Join-Path $tools "libreoffice"
Copy-Item $loRoot $loDest -Recurse -Force
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
    offline_docling_models = @("layout", "tableformer")
    bundled_ocr_languages = @("ara", "eng")
}
$buildInfo | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $app "build-info.json") -Encoding UTF8

Write-Host "Windows full runtime created at $app"
