@echo off
cd /d "%~dp0.."
python debug\kaitori_app.py
if errorlevel 1 pause
