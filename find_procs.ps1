Write-Host "=== Python processes ==="
Get-Process | Where-Object { $_.ProcessName -like 'python*' } | Select-Object Id,ProcessName,Path | Format-Table -AutoSize
Write-Host ""
Write-Host "=== Node processes ==="
Get-Process | Where-Object { $_.ProcessName -like 'node*' } | Select-Object Id,ProcessName,Path | Format-Table -AutoSize
Write-Host ""
Write-Host "=== AutoResearch (port 8899) status ==="
Get-NetTCPConnection -LocalPort 8899 -ErrorAction SilentlyContinue | Select-Object LocalPort,RemoteAddress,State | Format-Table -AutoSize
