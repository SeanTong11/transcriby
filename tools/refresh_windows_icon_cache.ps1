param(
    [switch]$NoRestartExplorer
)

Write-Host "Refreshing Windows icon cache..." -ForegroundColor Cyan

$iconCachePaths = @(
    "$env:LOCALAPPDATA\IconCache.db",
    "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\iconcache*",
    "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\thumbcache*"
)

if (-not $NoRestartExplorer) {
    Write-Host "Stopping Explorer..." -ForegroundColor Yellow
    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
}

foreach ($pattern in $iconCachePaths) {
    Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Remove-Item $_.FullName -Force -ErrorAction Stop
            Write-Host "Deleted $($_.Name)"
        } catch {
            Write-Warning "Failed to delete $($_.FullName): $($_.Exception.Message)"
        }
    }
}

if (-not $NoRestartExplorer) {
    Write-Host "Restarting Explorer..." -ForegroundColor Yellow
    Start-Process explorer.exe
}

Write-Host "Done. Re-pin Transcriby on taskbar if needed." -ForegroundColor Green
