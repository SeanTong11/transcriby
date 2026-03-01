Param(
  [string]$Version = "v3-20260301-git-05fac7f",
  [string]$Arch = "x86_64"
)

$ErrorActionPreference = "Stop"

$baseUrl = "https://sourceforge.net/projects/mpv-player-windows/files/libmpv/"
$zipName = "mpv-dev-$Arch-$Version.7z"
$downloadUrl = "$baseUrl$zipName/download"

$destRoot = Join-Path $PSScriptRoot "..\third_party\mpv"
$destRoot = (Resolve-Path $destRoot).Path

if (-not (Get-Command 7z -ErrorAction SilentlyContinue)) {
  Write-Error "7z not found. Install 7-Zip and ensure '7z' is on PATH."
}

Write-Host "Downloading $zipName ..."
$zipPath = Join-Path $env:TEMP $zipName
Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

if (Test-Path $destRoot) {
  Remove-Item -Recurse -Force $destRoot
}
New-Item -ItemType Directory -Path $destRoot | Out-Null

Write-Host "Extracting to $destRoot ..."
& 7z x $zipPath -o$destRoot | Out-Null

Write-Host "Done. DLLs are in $destRoot"
