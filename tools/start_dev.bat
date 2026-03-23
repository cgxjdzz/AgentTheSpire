@echo off
chcp 65001 >nul
title AgentTheSpire DEV
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

:: 清理旧的 7860 进程
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":7860 " ^| findstr "LISTENING"') do (
    echo 清理旧后端进程 PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 >nul

:: 后端：uvicorn --reload 监听文件变化自动重启
start "AgentTheSpire Backend [DEV]" cmd /k "cd /d "%ROOT_DIR%\backend" && call .venv\Scripts\activate.bat && uvicorn main:app --host 127.0.0.1 --port 7860 --reload"

:: 前端：vite dev server，支持 HMR 热更新
start "AgentTheSpire Frontend [DEV]" cmd /k "cd /d "%ROOT_DIR%\frontend" && npm run dev"

echo.
echo [DEV 模式]
echo   前端热更新：http://localhost:5173  （改 .tsx 自动刷新）
echo   后端热重启：改 .py 文件保存后自动重启
echo.
echo 关闭此窗口不会停止服务，请分别关闭两个子窗口。
timeout /t 5 >nul
