$ErrorActionPreference = "Stop"

if (-not $env:TRANSCRIBY_MPV_DIR) {
  Write-Warning "TRANSCRIBY_MPV_DIR is not set. Build will try PATH and fallback locations."
} else {
  Write-Host "Using TRANSCRIBY_MPV_DIR=$env:TRANSCRIBY_MPV_DIR"
}

Write-Host "== Building Transcriby =="
uv run python $PSScriptRoot\build_windows.py

$distDir = Join-Path (Get-Location) "Transcriby-Windows"
if (-not (Test-Path $distDir)) {
  Write-Error "Build output not found: $distDir"
}

$zipPath = Join-Path (Get-Location) "Transcriby-Windows.zip"
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
