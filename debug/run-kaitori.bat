@echo off
cd /d "%~dp0.."
python debug\trade_radar_desktop.py
if errorlevel 1 pause
