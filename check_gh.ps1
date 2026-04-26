$f = "$env:TEMP\gh.msi"
if (Test-Path $f) {
    $size = (Get-Item $f).Length
    Write-Host "File size: $([math]::Round($size/1MB,1)) MB"
    if ($size -gt 2MB) {
        Write-Host "Valid installer"
        # Install
        Start-Process msiexec.exe -ArgumentList "/i $f /qn" -Wait -NoNewWindow
        Write-Host "Installation done"
    } else {
        Write-Host "Too small, invalid"
    }
} else {
    Write-Host "File not found"
}
