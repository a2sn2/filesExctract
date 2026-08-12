param(
    [string]$AppRoot = "release/windows-full"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repo
$app = [System.IO.Path]::GetFullPath((Join-Path $repo $AppRoot))
if (-not (Test-Path (Join-Path $app "FilesExtract.exe"))) { throw "Windows full app was not built: $app" }

New-Item -ItemType Directory -Force -Path "dist" | Out-Null

Write-Host "== Integrity manifest =="
$manifestPath = Join-Path $app "MANIFEST-SHA256.txt"
$lines = Get-ChildItem $app -File -Recurse | Where-Object { $_.FullName -ne $manifestPath } | Sort-Object FullName | ForEach-Object {
    $relative = [System.IO.Path]::GetRelativePath($app, $_.FullName).Replace('\\','/')
    $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $relative"
}
$lines | Set-Content $manifestPath -Encoding ASCII

Write-Host "== Portable ZIP =="
# Use the .NET ZIP implementation built into PowerShell/.NET instead of relying
# on Chocolatey or a separately provisioned 7-Zip executable. ZipArchive emits
# Zip64 automatically when archive size/member counts require it.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = Join-Path $repo "dist/FilesExtract-Full-Portable-v0.4.0-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $app,
    $zip,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)
if (-not (Test-Path $zip) -or (Get-Item $zip).Length -le 0) {
    throw "Portable ZIP creation failed."
}

Write-Host "== Inno Setup installer =="
$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    # Install a checksum-pinned immutable official release into a private build
    # directory. This is a build-time compiler only and is not included in the
    # FilesExtract end-user product.
    $innoVersion = "6.7.3"
    $innoUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-$innoVersion.exe"
    $innoExpectedSha256 = "9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732"
    $innoInstaller = Join-Path $env:RUNNER_TEMP "innosetup-$innoVersion.exe"
    $innoRoot = Join-Path $env:RUNNER_TEMP "FilesExtract-InnoSetup"
    Invoke-WebRequest $innoUrl -OutFile $innoInstaller
    $innoActualSha256 = (Get-FileHash $innoInstaller -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($innoActualSha256 -ne $innoExpectedSha256) {
        throw "Inno Setup checksum mismatch. Expected $innoExpectedSha256, got $innoActualSha256."
    }
    if (Test-Path $innoRoot) { Remove-Item $innoRoot -Recurse -Force }
    $innoProcess = Start-Process -FilePath $innoInstaller -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/DIR=$innoRoot" -Wait -PassThru -NoNewWindow
    if ($innoProcess.ExitCode -ne 0) {
        throw "Inno Setup installer failed with exit code $($innoProcess.ExitCode)."
    }
    $iscc = Join-Path $innoRoot "ISCC.exe"
}
if (-not $iscc -or -not (Test-Path $iscc)) { throw "ISCC.exe was not found." }
& $iscc "/DSourceDir=$app" "packaging/windows_full/FilesExtract.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }

$setup = Join-Path $repo "dist/FilesExtract-Full-Setup-v0.4.0.exe"
if (-not (Test-Path $setup)) { throw "Expected installer was not created: $setup" }

$hashLines = @()
foreach ($file in @($setup, $zip)) {
    $hash = (Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant()
    $hashLines += "$hash  $([System.IO.Path]::GetFileName($file))"
}
$hashLines | Set-Content (Join-Path $repo "dist/SHA256SUMS-WINDOWS-FULL.txt") -Encoding ASCII
Copy-Item (Join-Path $app "build-info.json") (Join-Path $repo "dist/build-info-windows-full.json") -Force
Write-Host "Packaging complete."
