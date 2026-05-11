# Test IMA API directly with curl
$clientId = 'cd8f18bf3caa5c8e9be93b73385fe879'
$body = '{}'
$headers = @{
    'ima-openapi-clientid' = $clientId
    'ima-openapi-apikey' = $clientId
    'ima-openapi-ctx' = 'skill_version=1.0.0'
    'Content-Type' = 'application/json'
}
try {
    $r = Invoke-WebRequest -Uri 'https://ima.qq.com/openapi/list_docs' -Method POST -Headers $headers -Body $body -UseBasicParsing -TimeoutSec 15
    Write-Host 'Status:' $r.StatusCode
    Write-Host 'Body:' $r.Content
} catch {
    Write-Host 'Error:' $_.Exception.Message
    Write-Host 'Response:' $_.Exception.Response
}