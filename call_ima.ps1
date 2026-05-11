Set-Location 'C:\Users\wate\.qclaw\skills\ima-skill'
$nodeExe = 'C:\Users\wate\scoop\apps\nodejs\current\node.exe'
$script = 'ima_api.cjs'
$cmd = 'openapi/list_docs'
$body = '{"limit":5}'
$auth = '{"clientId":"cd8f18bf3caa5c8e9be93b73385fe879","apiKey":"cd8f18bf3caa5c8e9be93b73385fe879"}'
& $nodeExe $script $cmd $body $auth