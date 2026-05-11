$ErrorActionPreference = 'Stop'
try {
    $r = Invoke-WebRequest -Uri 'https://www.baidu.com' -UseBasicParsing -TimeoutSec 10
    Write-Host 'Baidu OK:' $r.StatusCode
} catch {
    Write-Host 'Baidu FAIL:' $_.Exception.Message
}
try {
    $r2 = Invoke-WebRequest -Uri 'https://github.com' -UseBasicParsing -TimeoutSec 10
    Write-Host 'GitHub OK:' $r2.StatusCode
} catch {
    Write-Host 'GitHub FAIL:' $_.Exception.Message
}