Set-Location 'C:\Users\wate\.qclaw\skills\ima-skill'
$env:IMA_FORCE_UPDATE_CHECK = '0'
$nodeExe = 'C:\Users\wate\scoop\apps\nodejs\current\node.exe'
$stdout = & $nodeExe 'C:\Users\wate\.qclaw\skills\ima-skill\ima_api.cjs' 'openapi/list_docs' '{}' '{}' 2>&1
Write-Host "STDOUT+STDERR: $stdout"