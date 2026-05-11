try { nslookup ima.qq.com } catch { Write-Host 'FAIL' }
try { nslookup ima.qq.com 8.8.8.8 } catch { Write-Host 'FAIL' }
try { nslookup ima.qq.com 114.114.114.114 } catch { Write-Host 'FAIL' }
try { [System.Net.Dns]::GetHostAddresses('ima.qq.com') } catch { Write-Host 'GetHostAddresses FAIL:' $_.Exception.Message }
try {
    $r = Invoke-WebRequest -Uri 'https://ima.qq.com' -UseBasicParsing -TimeoutSec 10
    Write-Host 'HTTPS OK:' $r.StatusCode
} catch {
    Write-Host 'HTTPS FAIL:' $_.Exception.Message
}