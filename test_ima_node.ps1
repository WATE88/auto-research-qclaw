# Test IMA API directly via ima_api.cjs
Set-Location 'C:\Users\wate\.qclaw\skills\ima-skill'
$env:IMA_CLIENT_ID = 'cd8f18bf3caa5c8e9be93b73385fe879'
$env:IMA_API_KEY = 'cd8f18bf3caa5c8e9be93b73385fe879'
$env:IMA_FORCE_UPDATE_CHECK = '0'
$env:IMA_DEBUG = '1'
$outFile = 'C:\Users\wate\.qclaw\workspace-agent-d29ea948\ima_test_out.txt'
$errFile = 'C:\Users\wate\.qclaw\workspace-agent-d29ea948\ima_test_err.txt'
$node = 'C:\Users\wate\scoop\apps\nodejs\current\node.exe'
$proc = Start-Process -FilePath $node -ArgumentList 'C:\Users\wate\.qclaw\skills\ima-skill\ima_api.cjs','openapi/list_docs','{}','{}' -NoNewWindow -PassThru -RedirectStandardOutput $outFile -RedirectStandardError $errFile
$proc | Wait-Process -Timeout 15 -ErrorAction SilentlyContinue
Write-Host "EXIT:" $proc.ExitCode
Write-Host "---STDOUT---"
Get-Content $outFile -Raw
Write-Host "---STDERR---"
Get-Content $errFile -Raw