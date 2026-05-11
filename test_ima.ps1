$ErrorActionPreference = 'Stop'
try {
    $r = Invoke-WebRequest -Uri 'https://ima.qq.com' -UseBasicParsing -TimeoutSec 10
    Write-Host 'IMA Status:' $r.StatusCode
} catch {
    Write-Host 'IMA FAIL:' $_.Exception.Message
}
try {
    $r2 = Invoke-WebRequest -Uri 'https://ima.qq.com/agent-interface' -UseBasicParsing -TimeoutSec 10
    Write-Host 'IMA API Status:' $r2.StatusCode
} catch {
    Write-Host 'IMA API FAIL:' $_.Exception.Message
}