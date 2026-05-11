$dirs = @(
    "C:\Users\wate\.qclaw",
    "C:\Users\wate\.openclaw",
    "C:\Users\wate\AppData\Roaming\LM Studio",
    "C:\Users\wate\AppData\Local\LM Studio"
)
foreach ($d in $dirs) {
    if (Test-Path $d) {
        Get-ChildItem $d -Recurse -File -Include *.json,*.yaml,*.yml,*.toml,*.config,*.env,*.txt 2>$null | ForEach-Object {
            $content = Get-Content $_.FullName -Raw 2>$null
            if ($content -and $content -match '(?i)hermes') {
                Write-Host ("FOUND: " + $_.FullName)
            }
        }
    }
}
Write-Host "SEARCH_DONE"