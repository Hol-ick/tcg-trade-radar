@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
if not defined SCRIPT_DIR set "SCRIPT_DIR=%CD%\debug\"
set "ROOT=%SCRIPT_DIR%.."
cd /d "%ROOT%" || goto :fail

set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" goto :setup
"%VENV_PY%" -c "import PySide6, playwright" >nul 2>&1
if errorlevel 1 goto :setup
goto :run

:setup
echo 첫 실행 환경을 준비합니다. 완료까지 잠시 걸릴 수 있습니다.
call "%ROOT%\debug\setup-trade-radar.bat" --no-pause
if errorlevel 1 goto :fail

:run
"%VENV_PY%" "%ROOT%\debug\trade_radar_desktop.py"
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo 앱을 실행하지 못했습니다. debug\checkhost.bat 또는 docs\windows-setup.md를 확인하세요.
pause
exit /b 1
