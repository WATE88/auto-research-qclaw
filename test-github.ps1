[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'
try {
    $r = Invoke-WebRequest -Uri 'https://github.com/WATE88/auto-research-qclaw' -UseBasicParsing -TimeoutSec 20
    Write-Host "StatusCode: $($r.StatusCode)"
    Write-Host "ContentLength: $($r.Content.Length)"
    Write-Host "FinalUrl: $($r.BaseResponse.ResponseUri)"
    Write-Host "Headers: $($r.Headers | Out-String)"
} catch {
    Write-Host "Exception: $($_.Exception.GetType().Name)"
    Write-Host "Message: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        Write-Host "HTTP Status: $($_.Exception.Response.StatusCode)"
        Write-Host "HTTP Description: $($_.Exception.Response.StatusDescription)"
    }
}
