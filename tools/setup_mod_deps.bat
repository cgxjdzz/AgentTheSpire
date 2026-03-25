@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title AgentTheSpire — Mod 开发依赖安装
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

echo.
echo  ============================================
echo    AgentTheSpire Mod 开发依赖安装
echo    .NET 9 SDK  +  Godot 4.5.1 Mono
echo  ============================================
echo.

:: Godot 默认解压到仓库根目录下的 godot\ 文件夹
set "GODOT_INSTALL_DIR=%ROOT_DIR%\godot"
set "GODOT_EXE=%GODOT_INSTALL_DIR%\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64.exe"
set "GODOT_DOWNLOAD_URL=https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_mono_win64.zip"
set "GODOT_ZIP=%TEMP%\godot_4.5.1_mono.zip"

:: ── 1. 检查 / 安装 .NET 9 SDK ──────────────────────────────────────────────
echo [.NET 9 SDK]
dotnet --version >nul 2>&1
if errorlevel 1 goto :install_dotnet

:: 检查版本是否是 9.x
for /f "tokens=1" %%v in ('dotnet --version 2^>nul') do set DOTNET_VER=%%v
if "!DOTNET_VER:~0,2!"=="9." (
    echo [OK] 已安装 .NET !DOTNET_VER!，跳过
    goto :check_godot
)
echo [INFO] 当前 .NET 版本: !DOTNET_VER!，需要 9.x

:install_dotnet
echo [安装] 正在通过 winget 安装 .NET 9 SDK...
winget install --id Microsoft.DotNet.SDK.9 --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo [WARN] winget 安装失败，尝试手动下载...
    set "DOTNET_INSTALLER=%TEMP%\dotnet9_installer.exe"
    curl -L -o "!DOTNET_INSTALLER!" "https://download.visualstudio.microsoft.com/download/pr/dotnet-sdk-9.0-win-x64.exe"
    if errorlevel 1 (
        echo [ERROR] 下载失败，请手动安装 .NET 9 SDK:
        echo         https://dotnet.microsoft.com/download/dotnet/9.0
        pause & exit /b 1
    )
    "!DOTNET_INSTALLER!" /install /quiet /norestart
    if errorlevel 1 (
        echo [ERROR] .NET 9 SDK 安装失败，请手动安装
        pause & exit /b 1
    )
)
:: 刷新 PATH
for /f "tokens=*" %%p in ('where dotnet 2^>nul') do set "DOTNET_NEW=%%p"
if not defined DOTNET_NEW (
    :: winget 安装后需要新开终端才能识别，提示用户
    echo.
    echo [提示] .NET 9 安装完成，但当前终端可能无法识别新路径。
    echo        请关闭此窗口，重新运行 tools\setup_mod_deps.bat 继续。
    pause & exit /b 0
)
echo [OK] .NET 9 SDK 安装完成

:: ── 2. 检查 / 安装 Godot 4.5.1 Mono ─────────────────────────────────────
:check_godot
echo.
echo [Godot 4.5.1 Mono]

:: 先读 config.json 里有没有配置路径
set "CONFIG_FILE=%ROOT_DIR%\config.json"
set "GODOT_FROM_CONFIG="
if exist "!CONFIG_FILE!" (
    for /f "delims=" %%l in ('python -c "import json,pathlib; p=pathlib.Path(r'!CONFIG_FILE!'); cfg=json.loads(p.read_text()); print(cfg.get('godot_exe_path',''))" 2^>nul') do (
        set "GODOT_FROM_CONFIG=%%l"
    )
)

:: 检查 config 里的路径是否有效
if defined GODOT_FROM_CONFIG if not "!GODOT_FROM_CONFIG!"=="" (
    if exist "!GODOT_FROM_CONFIG!" (
        echo [OK] 已配置且存在: !GODOT_FROM_CONFIG!
        goto :verify_godot_version
    ) else (
        echo [INFO] config.json 中的路径不存在，重新查找...
    )
)

:: 检查默认安装位置
if exist "!GODOT_EXE!" (
    echo [OK] 找到已有安装: !GODOT_EXE!
    set "GODOT_FROM_CONFIG=!GODOT_EXE!"
    goto :verify_godot_version
)

:: 搜索常见位置
for %%d in (
    "C:\Godot\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64.exe"
    "C:\Program Files\Godot\Godot_v4.5.1-stable_mono_win64.exe"
    "%USERPROFILE%\Godot\Godot_v4.5.1-stable_mono_win64.exe"
) do (
    if exist %%d (
        set "GODOT_FROM_CONFIG=%%~d"
        echo [OK] 找到: %%~d
        goto :verify_godot_version
    )
)

:: 需要下载安装
echo [安装] 未找到 Godot 4.5.1 Mono，开始下载（约 130MB）...
echo        下载地址: !GODOT_DOWNLOAD_URL!
echo.

if not exist "!GODOT_INSTALL_DIR!" mkdir "!GODOT_INSTALL_DIR!"

curl -L --progress-bar -o "!GODOT_ZIP!" "!GODOT_DOWNLOAD_URL!"
if errorlevel 1 (
    echo.
    echo [ERROR] 下载失败（可能需要代理）
    echo         请手动下载并解压到: !GODOT_INSTALL_DIR!
    echo         下载地址: !GODOT_DOWNLOAD_URL!
    pause & exit /b 1
)

echo.
echo [解压] 正在解压 Godot...
powershell -Command "Expand-Archive -Path '!GODOT_ZIP!' -DestinationPath '!GODOT_INSTALL_DIR!' -Force"
if errorlevel 1 (
    echo [ERROR] 解压失败
    pause & exit /b 1
)
del "!GODOT_ZIP!" >nul 2>&1

if not exist "!GODOT_EXE!" (
    echo [ERROR] 解压后找不到 exe，目录结构可能有变化
    echo         请手动确认: !GODOT_INSTALL_DIR!
    pause & exit /b 1
)

set "GODOT_FROM_CONFIG=!GODOT_EXE!"
echo [OK] Godot 解压完成: !GODOT_EXE!

:verify_godot_version
:: 验证版本是 4.5.1
"!GODOT_FROM_CONFIG!" --version --headless 2>nul | findstr "4.5.1" >nul
if errorlevel 1 (
    echo [WARN] 无法验证版本（headless 模式可能不支持），请人工确认是 4.5.1
) else (
    echo [OK] 版本验证通过: 4.5.1
)

:: ── 3. 将 Godot 路径写入 config.json ──────────────────────────────────────
echo.
echo [配置] 将 Godot 路径写入 config.json...

:: 路径反斜杠转义为 JSON 格式
set "GODOT_JSON_PATH=!GODOT_FROM_CONFIG:\=\\!"

python -c "
import json, pathlib
p = pathlib.Path(r'%ROOT_DIR%\config.json')
cfg = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
cfg['godot_exe_path'] = r'!GODOT_FROM_CONFIG!'
p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
print('写入完成')
"
if errorlevel 1 (
    echo [WARN] config.json 写入失败，请手动填写 godot_exe_path 字段
)

:: ── 完成 ───────────────────────────────────────────────────────────────────
echo.
echo  ============================================
echo    依赖安装完成！
echo.
echo    .NET 9 SDK : 已就绪
echo    Godot 路径 : !GODOT_FROM_CONFIG!
echo.
echo    如果之前还没跑过 tools\install.bat，
echo    现在可以运行 tools\install.bat 了。
echo  ============================================
echo.
pause

