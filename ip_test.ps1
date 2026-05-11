$ErrorActionPreference = 'Stop'
try {
    $r = Invoke-WebRequest -Uri 'https://14.22.6.238' -UseBasicParsing -TimeoutSec 10 -SkipCertificateCheck
    Write-Host 'HTTPS IP OK:' $r.StatusCode
} catch {
    Write-Host 'HTTPS IP FAIL:' $_.Exception.Message
}
try {
    $r2 = Invoke-WebRequest -Uri 'http://14.22.6.238' -UseBasicParsing -TimeoutSec 10
    Write-Host 'HTTP IP OK:' $r2.StatusCode
} catch {
    Write-Host 'HTTP IP FAIL:' $_.Exception.Message
}