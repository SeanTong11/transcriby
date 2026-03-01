$ErrorActionPreference = "Stop"

$mpvDir = Join-Path (Get-Location) "third_party\mpv"
if (-not (Test-Path $mpvDir)) {
  Write-Error "Missing libmpv DLLs. Place mpv dev DLLs under: $mpvDir"
}

Write-Host "== Building Transcriby =="
python $PSScriptRoot\build_windows.py

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
