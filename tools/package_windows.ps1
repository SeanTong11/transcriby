Param(
  [string]$Version = "v3-20260301-git-05fac7f",
  [string]$Arch = "x86_64"
)

$ErrorActionPreference = "Stop"

Write-Host "== Fetching mpv dev package =="
& $PSScriptRoot\fetch_mpv.ps1 -Version $Version -Arch $Arch

Write-Host "== Building SlowPlay =="
python $PSScriptRoot\build_windows.py

$distDir = Join-Path (Get-Location) "SlowPlay-Windows"
if (-not (Test-Path $distDir)) {
  Write-Error "Build output not found: $distDir"
}

$zipPath = Join-Path (Get-Location) "SlowPlay-Windows.zip"
if (Test-Path $zipPath) {
  Remove-Item -Force $zipPath
}

Write-Host "== Packaging =="
Compress-Archive -Path $distDir -DestinationPath $zipPath

Write-Host "== SHA256 =="
$hash = Get-FileHash $zipPath -Algorithm SHA256
$hashLine = "$($hash.Hash)  $($hash.Path)"
$hashLine | Out-File -Encoding ASCII -FilePath "SHA256SUMS.txt"

Write-Host "Done."
Write-Host " - $zipPath"
Write-Host " - SHA256SUMS.txt"
