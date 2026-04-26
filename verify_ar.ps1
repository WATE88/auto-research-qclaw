Write-Host "=== AutoResearch (port 8899) ==="
Get-NetTCPConnection -LocalPort 8899 -ErrorAction SilentlyContinue | Select-Object LocalPort,State | Format-Table -AutoSize
if ($?) { Write-Host "OK" } else { Write-Host "NOT running" }
