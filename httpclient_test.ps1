try {
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.DefaultRequestHeaders.Host = 'ima.qq.com'
    $r = $client.GetAsync('https://14.22.6.238/').Result
    Write-Host 'HTTPClient OK:' $r.StatusCode
} catch {
    Write-Host 'HTTPClient FAIL:' $_.Exception.Message
}