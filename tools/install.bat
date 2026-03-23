@echo off
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
:: 第一次进入时开启日志（同时输出到屏幕和 install.log）
if not defined INSTALL_LOGGING (
    set INSTALL_LOGGING=1
    call :init_log_file
    echo [INFO] 安装日志: %INSTALL_LOG_FILE%
    call "%~f0" %* 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath $env:INSTALL_LOG_FILE"
    exit /b %errorlevel%
)
setlocal enabledelayedexpansion
chcp 65001 >nul
title AgentTheSpire Installer

echo.
echo  ==============================
echo    AgentTheSpire Installer
echo  ==============================
echo.
call :show_progress 0 "开始环境检查"
call :log_info "初始化安装器"

:: ── 检查 Python ──────────────────────────────────────────────────────────────
call :log_info "检查 Python"
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.11+
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python !PY_VER!

:: ── 检查 Node.js ─────────────────────────────────────────────────────────────
call :log_info "检查 Node.js"
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Node.js，请先安装 Node.js 18+
    pause & exit /b 1
)
for /f %%v in ('node --version 2^>nul') do set NODE_VER=%%v
echo [OK] Node.js !NODE_VER!

:: ── 检查 .NET SDK ─────────────────────────────────────────────────────────────
dotnet --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] 未找到 .NET SDK，Code Agent 将无法编译 mod
    echo        run tools\setup_mod_deps.bat to install automatically
    echo.
) else (
    for /f %%v in ('dotnet --version 2^>nul') do set DOTNET_VER=%%v
    echo [OK] .NET SDK !DOTNET_VER!
)

:: ── 检查 Godot 路径 ───────────────────────────────────────────────────────────
call :log_info "检查 Godot 配置"
set "CONFIG_FILE=%ROOT_DIR%\config.json"
set "GODOT_OK=0"
if exist "!CONFIG_FILE!" (
    for /f "usebackq delims=" %%g in (`python -c "import json,pathlib; p=pathlib.Path(r'!CONFIG_FILE!'); cfg=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}; print(cfg.get('godot_exe_path',''))" 2^>nul`) do set "GODOT_PATH=%%g"
    if defined GODOT_PATH if not "!GODOT_PATH!"=="" (
        if exist "!GODOT_PATH!" (
            echo [OK] Godot 路径已配置
            set "GODOT_OK=1"
        )
    )
)
if "!GODOT_OK!"=="0" (
    echo [WARN] 未配置 Godot 路径，.pck 打包功能不可用
    echo        run tools\setup_mod_deps.bat to install Godot 4.5.1 automatically
)

:: ── 检查 claude CLI ───────────────────────────────────────────────────────────
call :log_info "检查 claude CLI"
claude --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] 未找到 claude CLI
    echo        订阅账号模式需运行: npm install -g @anthropic-ai/claude-code
    echo        使用 Kimi/DeepSeek 等 API 可跳过
    echo.
) else (
    echo [OK] claude CLI 已安装
)

:: ── 1/3 Python 依赖（venv 隔离，不影响 conda/mamba/系统 Python）────────────
echo.
call :show_progress 20 "准备后端 Python 环境"
echo [1/3] 创建 Python 虚拟环境...
call :log_info "切换到 backend 目录"
cd /d "%ROOT_DIR%\backend"

if not exist ".venv" (
    call :log_info "创建 Python 虚拟环境 .venv"
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] 创建 venv 失败
        pause & exit /b 1
    )
    echo [OK] venv 创建成功
) else (
    echo [OK] venv 已存在，跳过创建
)

echo [1/3] 安装后端依赖...
call :show_progress 40 "升级 pip"
call .venv\Scripts\activate.bat
call :log_info "已激活虚拟环境，开始升级 pip"
call :install_with_fallback --upgrade pip
if errorlevel 1 (
    echo [ERROR] pip 升级失败
    pause & exit /b 1
)
call :show_progress 55 "安装后端依赖"
call :log_info "开始安装 backend\\requirements.txt"
call :install_with_fallback -r requirements.txt
if errorlevel 1 (
    echo [ERROR] 后端依赖安装失败
    pause & exit /b 1
)
echo [OK] 后端依赖安装完成
call :log_info "后端依赖安装完成"

echo [1/3] 预下载 rembg 模型...
call :show_progress 65 "预下载 rembg 模型"
call :log_info "开始预热 rembg 模型缓存"
python -c "import json,pathlib; from rembg import new_session; root=pathlib.Path(r'%ROOT_DIR%'); cfg_path=root/'config.json'; cfg=json.loads(cfg_path.read_text(encoding='utf-8')) if cfg_path.exists() else {}; model=cfg.get('image_gen',{}).get('rembg_model','birefnet-general'); print(f'[INFO] rembg model: {model}'); new_session(model); print('[OK] rembg model ready')"
if errorlevel 1 (
    echo [WARN] rembg 模型预下载失败，首次抠图时会自动下载
    call :log_info "rembg 模型预下载失败，改为运行时下载"
) else (
    echo [OK] rembg 模型已就绪
    call :log_info "rembg 模型预下载完成"
)
call .venv\Scripts\deactivate.bat

:: ── 2/3 前端依赖 ─────────────────────────────────────────────────────────────
echo.
call :show_progress 75 "安装前端依赖"
echo [2/3] 安装前端依赖...
call :log_info "切换到 frontend 目录"
cd /d "%ROOT_DIR%\frontend"
call :log_info "开始执行 npm install"
npm install
if errorlevel 1 (
    echo [ERROR] 前端依赖安装失败
    pause & exit /b 1
)
echo [OK] 前端依赖安装完成
call :log_info "前端依赖安装完成"

:: ── 3/3 前端构建 ─────────────────────────────────────────────────────────────
echo.
call :show_progress 90 "构建前端"
echo [3/3] 构建前端...
call :log_info "开始执行 npm run build"
npm run build
if errorlevel 1 (
    echo [ERROR] 前端构建失败
    pause & exit /b 1
)
echo [OK] 前端构建完成

:: ── 可选：本地图生 ────────────────────────────────────────────────────────────
echo.
call :show_progress 95 "可选组件"
set /p LOCAL_IMG="是否安装本地图像生成（ComfyUI + FLUX.2，需约 12GB 磁盘）？[y/N] "
if /i "!LOCAL_IMG!"=="y" (
    echo.
    echo 正在安装 ComfyUI...
    call :log_info "开始安装 ComfyUI"
    cd /d "%ROOT_DIR%"
    git clone https://github.com/comfyanonymous/ComfyUI.git comfyui
    cd comfyui
    python -m pip install -r requirements.txt
    echo.
    echo [提示] FLUX.2 模型文件需手动下载放入 comfyui\models\checkpoints\
    echo        下载地址：https://huggingface.co/black-forest-labs/FLUX.2-dev
    python -c "import json,pathlib; p=pathlib.Path(r'%ROOT_DIR%\config.json'); cfg=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}; cfg.setdefault('image_gen',{})['local']={'comfyui_url':'http://127.0.0.1:8188','installed':True,'model_path':''}; p.write_text(json.dumps(cfg,indent=2,ensure_ascii=False),encoding='utf-8')"
)

echo.
call :show_progress 100 "安装完成"
echo  ==============================
echo    安装完成！
echo    运行 tools\start.bat 启动 AgentTheSpire
echo  ==============================
echo.
pause
goto :eof

:install_with_fallback
setlocal enabledelayedexpansion
if defined PIP_INDEX_URL (
    echo [INFO] 使用环境变量 PIP_INDEX_URL: !PIP_INDEX_URL!
    call :pip_install_from_source "!PIP_INDEX_URL!" %*
    set "RC=!errorlevel!"
    endlocal & exit /b %RC%
)

call :pip_install_from_source "https://pypi.org/simple" %*
if not errorlevel 1 (
    endlocal & exit /b 0
)

for %%i in (
    "https://pypi.tuna.tsinghua.edu.cn/simple"
    "https://mirrors.aliyun.com/pypi/simple/"
    "https://pypi.mirrors.ustc.edu.cn/simple"
) do (
    echo [WARN] 默认 PyPI 连接失败，尝试镜像：%%~i
    call :pip_install_from_source "%%~i" %*
    if not errorlevel 1 (
        endlocal & exit /b 0
    )
)

echo [ERROR] 所有可用 pip 源都失败，请检查网络，或先设置 PIP_INDEX_URL 后重试
endlocal & exit /b 1

:pip_install_from_source
setlocal enabledelayedexpansion
set "PIP_SOURCE=%~1"
shift
set "PIP_ARGS="
:collect_pip_args
if "%~1"=="" goto run_pip_install
set "PIP_ARGS=!PIP_ARGS! %~1"
shift
goto collect_pip_args
:run_pip_install
set "TS=!TIME: =0!"
echo [INFO !TS!] pip 源：!PIP_SOURCE!
python -m pip install --disable-pip-version-check --default-timeout 60 --retries 2 --index-url "!PIP_SOURCE!" !PIP_ARGS!
set "RC=!errorlevel!"
endlocal & exit /b %RC%

:show_progress
setlocal enabledelayedexpansion
set /a PCT=%~1
set "STEP=%~2"
set /a FILLED=(PCT+9)/10
set "BAR="
for /l %%i in (1,1,10) do (
    if %%i LEQ !FILLED! (
        set "BAR=!BAR!#"
    ) else (
        set "BAR=!BAR!-"
    )
)
set "TS=!TIME: =0!"
title AgentTheSpire Installer - !PCT!%% !STEP!
echo [INFO !TS!] [!BAR!] !PCT!%% !STEP!
endlocal & exit /b 0

:log_info
setlocal enabledelayedexpansion
set "MSG=%~1"
set "TS=!TIME: =0!"
echo [INFO !TS!] !MSG!
endlocal & exit /b 0

:init_log_file
setlocal
set "DEFAULT_LOG=%ROOT_DIR%\install.log"
for /f "usebackq delims=" %%g in (`powershell -NoProfile -Command "$default = [System.IO.Path]::GetFullPath('%ROOT_DIR%\install.log'); try { $fs = [System.IO.File]::Open($default, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None); $fs.Close(); $default } catch { Join-Path (Split-Path $default) ('install-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log') }"`) do set "LOG_PATH=%%g"
if not defined LOG_PATH set "LOG_PATH=%ROOT_DIR%\install.log"
endlocal & set "INSTALL_LOG_FILE=%LOG_PATH%" & exit /b 0

