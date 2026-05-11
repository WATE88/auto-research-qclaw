Set-Location 'C:\Users\wate\.qclaw\skills\ima-skill'
$env:IMA_FORCE_UPDATE_CHECK = '0'
$nodeExe = 'C:\Users\wate\scoop\apps\nodejs\current\node.exe'
$job = Start-Process -FilePath $nodeExe -ArgumentList 'C:\Users\wate\.qclaw\skills\ima-skill\ima_api.cjs','openapi/list_docs','{}','{}' -NoNewWindow -PassThru -RedirectStandardOutput 'C:\Users\wate\.qclaw\workspace-agent-d29ea948\ima_out.txt' -RedirectStandardError 'C:\Users\wate\.qclaw\workspace-agent-d29ea948\ima_err.txt'
$job | Wait-Process -TimeoutSec 20
Write-Host "Exit code:" $job.ExitCode
Write-Host "STDOUT:" (Get-Content 'C:\Users\wate\.qclaw\workspace-agent-d29ea948\ima_out.txt' -Raw)
Write-Host "STDERR:" (Get-Content 'C:\Users\wate\.qclaw\workspace-agent-d29ea948\ima_err.txt' -Raw)