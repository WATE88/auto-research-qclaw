Set-Location 'C:\Users\wate\.qclaw\skills\ima-skill'
$env:IMA_FORCE_UPDATE_CHECK = '0'
$nodeExe = 'C:\Users\wate\scoop\apps\nodejs\current\node.exe'
$body = @'
process.stdout.write('testing123');
''@
& $nodeExe -e $body