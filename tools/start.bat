@echo off
chcp 65001 >nul
title AgentTheSpire

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"
set "FRONTEND_DIST=%FRONTEND_DIR%\dist"
set "FRONTEND_NODE_MODULES=%FRONTEND_DIR%\node_modules"

:: 清理占用 7860 端口的旧进程
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":7860 " ^| findstr "LISTENING"') do (
    echo 清理旧进程 PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 >nul

if not exist "%FRONTEND_DIST%" (
    echo 检测到前端构建产物不存在，正在构建 frontend/dist...
    if not exist "%FRONTEND_NODE_MODULES%" (
        echo [错误] 缺少前端依赖目录 "%FRONTEND_NODE_MODULES%"。
        echo 请先运行 tools\install.bat 安装依赖后再重试。
        exit /b 1
    )

    pushd "%FRONTEND_DIR%"
    call npm run build
    if errorlevel 1 (
        popd
        echo [错误] 前端构建失败，已停止启动。
        exit /b 1
    )
    popd
)

cd /d "%ROOT_DIR%\backend"
echo 启动 AgentTheSpire...
echo 打开浏览器访问 http://localhost:7860
start /b cmd /c "timeout /t 3 >nul && start "" http://localhost:7860"
.venv\Scripts\python.exe main.py


