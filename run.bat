@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo 未找到虚拟环境，请先创建 venv。
    pause
    exit /b 1
)

echo 正在启动 POI Finder...
echo 浏览器访问：http://127.0.0.1:8000
"venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
