while ($true) {
    mpremote connect auto repl

    Write-Host ""
    Write-Host "ESP32 disconnected. Waiting for reconnect..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}