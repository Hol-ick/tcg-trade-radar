@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ROOT=%~dp0"
if not defined ROOT set "ROOT=%CD%\"
cd /d "%ROOT%" || goto :fail

set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "FIRST_RUN_MARKER=%ROOT%\.audit\first-run-complete.txt"

if exist "%FIRST_RUN_MARKER%" goto :launch

echo.
echo TCG Trade Radar를 처음 실행합니다.
echo Python 환경과 수집 브라우저를 한 번 준비합니다.
echo 완료 후에는 이 파일만 다시 실행하면 됩니다.
echo.
call "%ROOT%\debug\setup-trade-radar.bat" --no-pause
if errorlevel 1 goto :fail

echo 설치 상태를 확인합니다.
call "%ROOT%\debug\checkhost.bat" --skip-network
if errorlevel 1 goto :fail

if not exist "%ROOT%\.audit" mkdir "%ROOT%\.audit"
> "%FIRST_RUN_MARKER%" echo TCG Trade Radar first run completed.

:launch
if not exist "%VENV_PY%" (
    echo 가상환경을 찾을 수 없습니다. debug\setup-trade-radar.bat를 확인하세요.
    goto :fail
)

"%VENV_PY%" -c "import PySide6, playwright" >nul 2>&1
if errorlevel 1 (
    echo 설치된 Python 패키지를 확인하지 못했습니다.
    echo 첫 실행 마커를 삭제한 뒤 이 파일을 다시 실행하거나 debug\setup-trade-radar.bat를 실행하세요.
    goto :fail
)

"%VENV_PY%" "%ROOT%\debug\trade_radar_desktop.py"
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo 앱을 실행하지 못했습니다.
echo docs\windows-setup.md의 문제 해결 안내를 확인하세요.
pause
exit /b 1
