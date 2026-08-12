$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
python -m kaitori_collector --serve --host 127.0.0.1 --port 8787 --db .audit\kaitori.sqlite3
