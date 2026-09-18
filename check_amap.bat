@echo off
setlocal
cd /d "%~dp0"
title POI Finder - Amap Check

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

echo Checking configured Amap Web Service key and HTTPS connection...
echo.
"venv\Scripts\python.exe" "scripts\probe_amap.py" --configured-key
set "CHECK_EXIT=%ERRORLEVEL%"
echo.
if "%CHECK_EXIT%"=="0" (
    echo [PASS] Amap service is reachable and the configured key was accepted.
) else (
    echo [FAIL] Amap check failed. Copy the message above, but never share your key.
)
pause
exit /b %CHECK_EXIT%
