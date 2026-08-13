param(
    [string]$AppRoot = "release/windows-full",
    [ValidateSet("All", "Manifest", "Portable", "Installer", "Finalize")]
    [string]$Phase = "All"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repo
$app = [System.IO.Path]::GetFullPath((Join-Path $repo $AppRoot))
if (-not (Test-Path (Join-Path $app "FilesExtract.exe"))) { throw "Windows full app was not built: $app" }

New-Item -ItemType Directory -Force -Path "dist" | Out-Null
$zip = Join-Path $repo "dist/FilesExtract-Full-Portable-v0.4.0-windows-x64.zip"
$setup = Join-Path $repo "dist/FilesExtract-Full-Setup-v0.4.0.exe"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    $stream = $null
    $sha256 = $null
    try {
        $stream = [System.IO.File]::Open(
            $resolved,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::Read
        )
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        $bytes = $sha256.ComputeHash($stream)
        return [System.Convert]::ToHexString($bytes).ToLowerInvariant()
    }
    finally {
        if ($sha256) { $sha256.Dispose() }
        if ($stream) { $stream.Dispose() }
    }
}

function Invoke-Manifest {
    Write-Host "== Integrity manifest =="
    $manifestPath = Join-Path $app "MANIFEST-SHA256.txt"
    if (Test-Path $manifestPath) { Remove-Item $manifestPath -Force }
    $lines = Get-ChildItem $app -File -Recurse | Sort-Object FullName | ForEach-Object {
        $filePath = $_.FullName
        $relative = [System.IO.Path]::GetRelativePath($app, $filePath).Replace('\','/')
        $hash = Get-Sha256Hex -Path $filePath
        "$hash  $relative"
    }
    $lines | Set-Content $manifestPath -Encoding ASCII
    if (-not (Test-Path $manifestPath) -or (Get-Item $manifestPath).Length -le 0) {
        throw "Integrity manifest creation failed."
    }
    Write-Host "Integrity manifest created with $($lines.Count) entries."
}

function Invoke-Portable {
    Write-Host "== Portable ZIP =="
    if (-not (Test-Path (Join-Path $app "MANIFEST-SHA256.txt"))) {
        throw "MANIFEST-SHA256.txt is required before portable packaging."
    }
    if (Test-Path $zip) { Remove-Item $zip -Force }
    $tar = Join-Path $env:SystemRoot "System32\tar.exe"
    if (-not (Test-Path $tar)) { throw "Windows tar.exe is unavailable." }
    Push-Location $app
    try {
        & $tar -a -cf $zip .
        if ($LASTEXITCODE -ne 0) { throw "tar.exe ZIP creation failed with exit code $LASTEXITCODE." }
    }
    finally { Pop-Location }
    if (-not (Test-Path $zip) -or (Get-Item $zip).Length -le 0) {
        throw "Portable ZIP creation failed."
    }
    Write-Host "Portable ZIP bytes: $((Get-Item $zip).Length)"
}

function Get-InnoCompiler {
    $isccCandidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $found = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($found) { return $found }

    $innoVersion = "6.7.3"
    $innoUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-$innoVersion.exe"
    $innoExpectedSha256 = "9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732"
    $innoInstaller = Join-Path $env:RUNNER_TEMP "innosetup-$innoVersion.exe"
    $innoRoot = Join-Path $env:RUNNER_TEMP "FilesExtract-InnoSetup"
    Invoke-WebRequest $innoUrl -OutFile $innoInstaller
    $innoActualSha256 = Get-Sha256Hex -Path $innoInstaller
    if ($innoActualSha256 -ne $innoExpectedSha256) {
        throw "Inno Setup checksum mismatch. Expected $innoExpectedSha256, got $innoActualSha256."
    }
    if (Test-Path $innoRoot) { Remove-Item $innoRoot -Recurse -Force }
    $arguments = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/DIR=$innoRoot")
    $innoProcess = Start-Process -FilePath $innoInstaller -ArgumentList $arguments -Wait -PassThru -NoNewWindow
    if ($innoProcess.ExitCode -ne 0) {
        throw "Inno Setup installer failed with exit code $($innoProcess.ExitCode)."
    }
    $privateIscc = Get-ChildItem $innoRoot -Filter "ISCC.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if (-not $privateIscc -or -not (Test-Path $privateIscc)) { throw "ISCC.exe was not found after private Inno Setup installation." }
    return $privateIscc
}

function Invoke-Installer {
    Write-Host "== Inno Setup installer =="
    if (-not (Test-Path (Join-Path $app "MANIFEST-SHA256.txt"))) {
        throw "MANIFEST-SHA256.txt is required before installer packaging."
    }
    if (Test-Path $setup) { Remove-Item $setup -Force }
    $iscc = Get-InnoCompiler
    Write-Host "Using ISCC: $iscc"
    & $iscc "/DSourceDir=$app" "packaging/windows_full/FilesExtract.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed with exit code $LASTEXITCODE." }
    if (-not (Test-Path $setup) -or (Get-Item $setup).Length -le 0) {
        throw "Expected installer was not created: $setup"
    }
    Write-Host "Installer bytes: $((Get-Item $setup).Length)"
}

function Invoke-Finalize {
    Write-Host "== Final checksums =="
    if (-not (Test-Path $setup)) { throw "Installer is missing: $setup" }
    if (-not (Test-Path $zip)) { throw "Portable ZIP is missing: $zip" }
    $hashLines = @()
    foreach ($file in @($setup, $zip)) {
        $hash = Get-Sha256Hex -Path $file
        $hashLines += "$hash  $([System.IO.Path]::GetFileName($file))"
    }
    $hashLines | Set-Content (Join-Path $repo "dist/SHA256SUMS-WINDOWS-FULL.txt") -Encoding ASCII
    Copy-Item (Join-Path $app "build-info.json") (Join-Path $repo "dist/build-info-windows-full.json") -Force
    Write-Host "Packaging complete."
}

switch ($Phase) {
    "Manifest" { Invoke-Manifest }
    "Portable" { Invoke-Portable }
    "Installer" { Invoke-Installer }
    "Finalize" { Invoke-Finalize }
    "All" { Invoke-Manifest; Invoke-Portable; Invoke-Installer; Invoke-Finalize }
}
