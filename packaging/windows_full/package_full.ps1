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

$sevenZip = "C:\Program Files\7-Zip\7z.exe"
if (-not (Test-Path $sevenZip)) {
    & choco install 7zip -y --no-progress
    if ($LASTEXITCODE -ne 0) { throw "Could not install 7-Zip." }
}
$zip = Join-Path $repo "dist/FilesExtract-Full-Portable-v0.4.0-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
& $sevenZip a -tzip -mx=7 $zip "$app\*"
if ($LASTEXITCODE -ne 0) { throw "Portable ZIP creation failed." }

Write-Host "== Inno Setup installer =="
$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    & choco install innosetup -y --no-progress
    if ($LASTEXITCODE -ne 0) { throw "Could not install Inno Setup." }
    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw "ISCC.exe was not found." }
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
