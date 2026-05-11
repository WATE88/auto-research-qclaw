Set-Location 'C:\Users\wate\.qclaw\skills\ima-skill'
$env:IMA_FORCE_UPDATE_CHECK = '0'
$nodeExe = 'C:\Users\wate\scoop\apps\nodejs\current\node.exe'
& $nodeExe 'C:\Users\wate\.qclaw\skills\ima-skill\ima_api.cjs' 'openapi/list_docs' '{}' '{}'