@echo off
cd /d "%~dp0.."
python -m kaitori_collector --serve --host 127.0.0.1 --port 8787 --db .audit\kaitori.sqlite3
pause
