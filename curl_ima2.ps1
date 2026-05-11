# Test IMA API with correct endpoint
$clientId = 'cd8f18bf3caa5c8e9be93b73385fe879'
$headers = @{
    'ima-openapi-clientid' = $clientId
    'ima-openapi-apikey' = $clientId
    'ima-openapi-ctx' = 'skill_version=1.0.0'
    'Content-Type' = 'application/json'
}
$body = '{"cursor":"","limit":5}'
try {
    $r = Invoke-WebRequest -Uri 'https://ima.qq.com/openapi/wiki/v1/get_addable_knowledge_base_list' -Method POST -Headers $headers -Body $body -UseBasicParsing -TimeoutSec 15
    Write-Host 'Status:' $r.StatusCode
    Write-Host 'Body:' $r.Content
} catch {
    Write-Host 'Error:' $_.Exception.Message
}