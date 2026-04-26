cd C:\Users\wate\.qclaw\workspace-agent-d29ea948\auto-research-qclaw
$pid_python = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*autoresearch_unified*' }).ProcessId
Write-Host "AutoResearch PID: $pid_python"
Write-Host "Memory check every 10s for 3 minutes..."
$start = Get-Date
while ((Get-Date) -lt $start.AddMinutes(3)) {
    $proc = Get-Process -Id $pid_python -ErrorAction SilentlyContinue
    if ($proc) {
        $memMB = [math]::Round($proc.WorkingSet64 / 1MB, 1)
        Write-Host "$(Get-Date -Format 'HH:mm:ss')  PID=$pid_python  Memory=${memMB}MB"
    } else {
        Write-Host "Process $pid_python died!"
        break
    }
    Start-Sleep -Seconds 10
}
