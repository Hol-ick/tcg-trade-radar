@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
if not defined SCRIPT_DIR set "SCRIPT_DIR=%CD%\debug\"
set "ROOT=%SCRIPT_DIR%.."
cd /d "%ROOT%" || goto :fail

set "SKIP_BROWSER=0"
set "NO_PAUSE=0"
:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--skip-browser" (
    set "SKIP_BROWSER=1"
    shift
    goto :parse_args
)
if /I "%~1"=="--no-pause" (
    set "NO_PAUSE=1"
    shift
    goto :parse_args
)
echo 알 수 없는 옵션: %~1
echo 사용법: debug\setup-trade-radar.bat [--skip-browser] [--no-pause]
goto :fail
:args_done

if not exist "%ROOT%\pyproject.toml" (
    echo pyproject.toml을 찾지 못했습니다. Git 저장소 루트에서 실행하세요.
    goto :fail
)

set "BOOTSTRAP_PY="
set "BOOTSTRAP_ARGS="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_PY=py"
        set "BOOTSTRAP_ARGS=-3.11"
    )
)
if not defined BOOTSTRAP_PY (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
        if not errorlevel 1 set "BOOTSTRAP_PY=python"
    )
)
if not defined BOOTSTRAP_PY (
    echo Python 3.11 이상을 찾지 못했습니다.
    echo https://www.python.org/downloads/windows/ 에서 Python을 설치하고 PATH 추가를 선택하세요.
    goto :fail
)

if not exist "%ROOT%\.venv\Scripts\python.exe" (
    echo [1/5] 프로젝트 가상환경을 생성합니다.
    %BOOTSTRAP_PY% %BOOTSTRAP_ARGS% -m venv "%ROOT%\.venv"
    if errorlevel 1 goto :fail
) else (
    echo [1/5] 기존 프로젝트 가상환경을 사용합니다.
)

set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
"%VENV_PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo .venv의 Python이 3.11 이상이 아닙니다. 기존 .venv를 확인한 뒤 다시 시도하세요.
    goto :fail
)

echo [2/5] pip을 준비합니다.
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check --no-input
if errorlevel 1 echo pip 업그레이드는 건너뛰고 프로젝트 설치를 계속합니다.

echo [3/5] 프로젝트와 PySide6/Playwright 의존성을 설치합니다.
"%VENV_PY%" -m pip install -e . --disable-pip-version-check --no-input
if errorlevel 1 goto :fail

if not exist "%ROOT%\.audit" mkdir "%ROOT%\.audit"

if "%SKIP_BROWSER%"=="1" goto :skip_browser
echo [4/5] Playwright Chromium을 준비합니다. 이미 Chrome 또는 Edge가 있으면 실패해도 fallback으로 실행할 수 있습니다.
"%VENV_PY%" -m playwright install chromium
if errorlevel 1 echo Chromium 설치에 실패했습니다. debug\checkhost.bat로 Chrome/Edge fallback을 확인하세요.
:skip_browser

echo [5/5] Python 모듈 컴파일을 확인합니다.
"%VENV_PY%" -m compileall -q "%ROOT%\kaitori_collector" "%ROOT%\debug"
if errorlevel 1 goto :fail

echo.
echo 설정 완료. 프로젝트 루트의 TCG Trade Radar.bat를 실행하면 데스크톱 앱이 열립니다.
if "%NO_PAUSE%"=="0" pause
exit /b 0

:fail
echo.
echo 설정을 완료하지 못했습니다. 위 오류를 확인하고 docs\windows-setup.md를 참고하세요.
if "%NO_PAUSE%"=="0" pause
exit /b 1
