# Test IMA API with both credentials
$clientId = 'cd8f18bf3caa5c8e9be93b73385fe879'
$headers = @{
    'ima-openapi-clientid' = $clientId
    'ima-openapi-apikey' = $clientId
    'ima-openapi-ctx' = 'skill_version=1.0.0'
    'Content-Type' = 'application/json'
}
# Try get_knowledge_base (requires existing IDs, might give clue about auth)
$body1 = '{"ids":[]}'
try {
    $r1 = Invoke-WebRequest -Uri 'https://ima.qq.com/openapi/wiki/v1/get_knowledge_base' -Method POST -Headers $headers -Body $body1 -UseBasicParsing -TimeoutSec 15
    Write-Host 'get_knowledge_base Status:' $r1.StatusCode
    Write-Host 'get_knowledge_base Body:' $r1.Content
} catch {
    Write-Host 'get_knowledge_base Error:' $_.Exception.Message
}
# Try search_knowledge_base
$body2 = '{"query":"","cursor":"","limit":5}'
try {
    $r2 = Invoke-WebRequest -Uri 'https://ima.qq.com/openapi/wiki/v1/search_knowledge_base' -Method POST -Headers $headers -Body $body2 -UseBasicParsing -TimeoutSec 15
    Write-Host 'search_knowledge_base Status:' $r2.StatusCode
    Write-Host 'search_knowledge_base Body:' $r2.Content
} catch {
    Write-Host 'search_knowledge_base Error:' $_.Exception.Message
}