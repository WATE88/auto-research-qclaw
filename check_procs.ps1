Write-Host "=== Python processes ==="
Get-Process python* -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path | Format-Table -AutoSize
Write-Host ""
Write-Host "=== Port 8899 (AutoResearch) ==="
Get-NetTCPConnection -LocalPort 8899 -ErrorAction SilentlyContinue | Select-Object LocalPort,State | Format-Table -AutoSize
Write-Host ""
Write-Host "=== Port 19000 (ProSearch) ==="
Get-NetTCPConnection -LocalPort 19000 -ErrorAction SilentlyContinue | Select-Object LocalPort,State | Format-Table -AutoSize
