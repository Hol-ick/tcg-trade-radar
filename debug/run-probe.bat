@echo off
cd /d "%~dp0.."
python debug\probe_galleries.py --gallery tcggame --gallery onepiececardgame --gallery pokemoncardgame --gallery digimontcg --gallery vg
if errorlevel 1 pause
