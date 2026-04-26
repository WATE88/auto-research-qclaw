Start-Sleep -Seconds 3
Write-Host "Checking port 8899..."
$conn = Get-NetTCPConnection -LocalPort 8899 -ErrorAction SilentlyContinue
if ($conn) {
    $conn | Format-Table -AutoSize
    Write-Host "AutoResearch is UP!"
} else {
    Write-Host "Port 8899 not listening"
}
Write-Host ""
Write-Host "Checking Python processes..."
Get-Process | Where-Object { $_.ProcessName -like '*python*' } | Select-Object Id,ProcessName,MainWindowTitle | Format-Table -AutoSize
