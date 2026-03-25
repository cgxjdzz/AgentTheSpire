@echo off
:: generate_sandbox_wsb.bat
:: 根据当前 repo 路径生成 sandbox_test.wsb（不提交，见 .gitignore）
setlocal

:: 脚本所在目录的上一级即 repo 根目录
set "REPO_ROOT=%~dp0.."
:: 去掉末尾反斜杠（若有）
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "TEMPLATE=%~dp0sandbox_test.wsb.template"
set "OUTPUT=%~dp0sandbox_test.wsb"

if not exist "%TEMPLATE%" (
    echo [ERROR] Template not found: %TEMPLATE%
    exit /b 1
)

powershell -NoProfile -Command ^
  "(Get-Content '%TEMPLATE%' -Encoding UTF8) -replace '\{\{PROJECT_ROOT\}\}', '%REPO_ROOT%' | Set-Content '%OUTPUT%' -Encoding UTF8"

if errorlevel 1 (
    echo [ERROR] Failed to generate sandbox_test.wsb
    exit /b 1
)

echo [OK] Generated sandbox_test.wsb
echo      PROJECT_ROOT = %REPO_ROOT%
