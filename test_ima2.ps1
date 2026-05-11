try {
    $r = Invoke-WebRequest -Uri 'https://ima.qq.com' -UseBasicParsing -TimeoutSec 10
    Write-Host 'IMA主页 OK:' $r.StatusCode
} catch {
    Write-Host '失败:' $_.Exception.Message
}
try {
    $r2 = Invoke-WebRequest -Uri 'https://ima.qq.com/agent-interface' -UseBasicParsing -TimeoutSec 10
    Write-Host 'IMA API接口 OK:' $r2.StatusCode
} catch {
    Write-Host 'API失败:' $_.Exception.Message
}