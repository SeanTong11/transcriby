Param(
  [string]$Version = "v3-20260301-git-05fac7f",
  [string]$Arch = "x86_64"
)

$ErrorActionPreference = "Stop"

$baseUrl = "https://sourceforge.net/projects/mpv-player-windows/files/libmpv/"
$zipName = "mpv-dev-$Arch-$Version.7z"
$downloadUrl = "$baseUrl$zipName/download"

$destRoot = Join-Path $PSScriptRoot "..\third_party\mpv"
if (-not (Test-Path $destRoot)) {
  New-Item -ItemType Directory -Path $destRoot | Out-Null
}
$destRoot = (Resolve-Path $destRoot).Path

function Resolve-7z {
  $cmd = Get-Command 7z -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  $resp = Read-Host "7z not found. Install 7-Zip using winget? (y/N)"
  if ($resp -match '^(y|yes)$') {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
      Write-Error "winget not found. Please install 7-Zip manually and ensure '7z' is on PATH."
    }
    winget install --id 7zip.7zip -e --accept-package-agreements --accept-source-agreements
  } else {
    Write-Error "7z is required. Aborting."
  }

  $cmd = Get-Command 7z -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  $fallback = "C:\Program Files\7-Zip\7z.exe"
  if (Test-Path $fallback) {
    return $fallback
  }

  Write-Error "7z not found after install attempt. Ensure 7-Zip is installed and '7z' is on PATH."
}

$sevenZip = Resolve-7z

Write-Host "Downloading $zipName ..."
$zipPath = Join-Path $env:TEMP $zipName
Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

if (Test-Path $destRoot) {
  Remove-Item -Recurse -Force $destRoot
}
New-Item -ItemType Directory -Path $destRoot | Out-Null

Write-Host "Extracting to $destRoot ..."
& $sevenZip x $zipPath -o$destRoot | Out-Null

Write-Host "Done. DLLs are in $destRoot"
