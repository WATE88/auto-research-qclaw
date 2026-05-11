Set-Location 'C:\Users\wate\.qclaw\skills\ima-skill'
$nodeExe = 'C:\Users\wate\scoop\apps\nodejs\current\node.exe'
Set-Content -Path 'C:\Users\wate\.qclaw\skills\ima-skill\debug_argv.js' -Value "console.log('argv:', JSON.stringify(process.argv));" -NoNewline -Encoding UTF8
& $nodeExe 'C:\Users\wate\.qclaw\skills\ima-skill\debug_argv.js' 'openapi/list_docs' '{"limit":5}' '{"clientId":"xxx","apiKey":"yyy"}'