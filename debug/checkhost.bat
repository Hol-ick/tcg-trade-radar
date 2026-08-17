@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
if not defined SCRIPT_DIR set "SCRIPT_DIR=%CD%\debug\"
set "ROOT=%SCRIPT_DIR%.."
cd /d "%ROOT%" || goto :fail

set "CHECK_PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%CHECK_PY%" set "CHECK_PY=python"
where "%CHECK_PY%" >nul 2>&1
if not exist "%ROOT%\.venv\Scripts\python.exe" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python을 찾지 못했습니다. 프로젝트 루트의 TCG Trade Radar.bat를 먼저 실행하세요.
        goto :fail
    )
)

"%CHECK_PY%" "%ROOT%\debug\checkhost.py" --project-root "%ROOT%" %*
set "CHECK_EXIT=%ERRORLEVEL%"
if not "%CHECK_EXIT%"=="0" (
    echo.
    echo 점검 결과 코드: %CHECK_EXIT%
    echo 설치 문제는 프로젝트 루트의 TCG Trade Radar.bat를 다시 실행하고, 공개 주소 문제는 위 상태와 수집 로그를 확인하세요.
    pause
)
exit /b %CHECK_EXIT%

:fail
pause
exit /b 1
