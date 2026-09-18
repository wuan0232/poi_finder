@echo off
setlocal
cd /d "%~dp0"
title POI Finder

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found: venv\Scripts\python.exe
    echo Create or restore the project virtual environment first.
    pause
    exit /b 1
)

echo Starting POI Finder...
echo URL: http://127.0.0.1:8765
echo Keep this window open. Press Ctrl+C to stop the server.
echo.

"venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8765 --workers 1

echo.
echo POI Finder stopped. Review any error shown above.
pause
endlocal
