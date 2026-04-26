$url = "https://ghproxy.com/https://github.com/cli/cli/releases/download/v2.90.0/gh_2.90.0_windows_amd64.msi"
$out = "$env:TEMP\gh_new.msi"
Write-Host "Downloading gh CLI..."
$client = New-Object System.Net.WebClient
try {
    $client.DownloadFile($url, $out)
    $size = (Get-Item $out).Length
    Write-Host "Downloaded: $([math]::Round($size/1MB,1)) MB"
    if ($size -gt 5MB) {
        Write-Host "Installing..."
        Start-Process msiexec.exe -ArgumentList "/i $out /qn" -Wait -NoNewWindow
        Write-Host "Done"
    } else {
        Write-Host "File too small, failed"
    }
} catch {
    Write-Host "Error: $_"
} finally {
    $client.Dispose()
}
