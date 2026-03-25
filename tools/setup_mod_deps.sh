#!/usr/bin/env bash
# AgentTheSpire — Mod 开发依赖安装（Linux / macOS / WSL2）
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GODOT_VERSION="4.5.1"
GODOT_INSTALL_DIR="$ROOT_DIR/godot"
CONFIG_FILE="$ROOT_DIR/config.json"

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
info() { echo -e "[INFO] $1"; }

echo ""
echo " ============================================"
echo "   AgentTheSpire Mod 开发依赖安装"
echo "   .NET 9 SDK  +  Godot 4.5.1 Mono"
echo " ============================================"
echo ""

# ── 1. 检测系统 ──────────────────────────────────────────────────────────────
OS="linux"
ARCH="x86_64"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    ARCH=$(uname -m)  # arm64 or x86_64
fi

# ── 2. .NET 9 SDK ─────────────────────────────────────────────────────────────
echo "[.NET 9 SDK]"

install_dotnet_linux() {
    info "通过 apt 安装 .NET 9 SDK..."
    # Microsoft 官方 feed
    wget -q https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb
    sudo dpkg -i /tmp/packages-microsoft-prod.deb
    sudo apt-get update -qq
    sudo apt-get install -y dotnet-sdk-9.0
}

install_dotnet_macos() {
    info "通过 Homebrew 安装 .NET 9 SDK..."
    if command -v brew &>/dev/null; then
        brew install --cask dotnet-sdk
    else
        err "未找到 Homebrew。请先安装：https://brew.sh 或手动安装 .NET 9 SDK"
    fi
}

if command -v dotnet &>/dev/null; then
    DOTNET_VER=$(dotnet --version 2>/dev/null | head -1)
    if [[ "$DOTNET_VER" == 9.* ]]; then
        ok "已安装 .NET $DOTNET_VER，跳过"
    else
        info "当前版本: $DOTNET_VER，需要 9.x，开始安装..."
        [[ "$OS" == "linux" ]] && install_dotnet_linux || install_dotnet_macos
    fi
else
    info "未找到 dotnet，开始安装..."
    [[ "$OS" == "linux" ]] && install_dotnet_linux || install_dotnet_macos
fi

# 验证
dotnet --version &>/dev/null && ok ".NET 9 SDK 安装完成" || err ".NET 安装后仍无法运行，请重开终端或手动安装"

# ── 3. Godot 4.5.1 Mono ──────────────────────────────────────────────────────
echo ""
echo "[Godot 4.5.1 Mono]"

# 确定下载文件名
if [[ "$OS" == "linux" ]]; then
    GODOT_FILENAME="Godot_v${GODOT_VERSION}-stable_mono_linux_x86_64"
    GODOT_ZIP="${GODOT_FILENAME}.zip"
    GODOT_EXE="$GODOT_INSTALL_DIR/${GODOT_FILENAME}/${GODOT_FILENAME}"
elif [[ "$OS" == "macos" ]]; then
    if [[ "$ARCH" == "arm64" ]]; then
        GODOT_FILENAME="Godot_v${GODOT_VERSION}-stable_mono_macos.universal"
    else
        GODOT_FILENAME="Godot_v${GODOT_VERSION}-stable_mono_macos.universal"
    fi
    GODOT_ZIP="${GODOT_FILENAME}.zip"
    GODOT_EXE="$GODOT_INSTALL_DIR/Godot_mono.app/Contents/MacOS/Godot"
fi

GODOT_DOWNLOAD_URL="https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable/${GODOT_ZIP}"

# 先检查 config.json
GODOT_FROM_CONFIG=""
if [[ -f "$CONFIG_FILE" ]] && command -v python3 &>/dev/null; then
    GODOT_FROM_CONFIG=$(python3 -c "
import json, pathlib
p = pathlib.Path('$CONFIG_FILE')
cfg = json.loads(p.read_text()) if p.exists() else {}
print(cfg.get('godot_exe_path', ''))
" 2>/dev/null)
fi

if [[ -n "$GODOT_FROM_CONFIG" && -f "$GODOT_FROM_CONFIG" ]]; then
    ok "已配置且存在: $GODOT_FROM_CONFIG"
elif [[ -f "$GODOT_EXE" ]]; then
    ok "找到已有安装: $GODOT_EXE"
    GODOT_FROM_CONFIG="$GODOT_EXE"
else
    # 下载安装
    info "未找到 Godot 4.5.1，开始下载（约 130MB）..."
    info "下载地址: $GODOT_DOWNLOAD_URL"
    mkdir -p "$GODOT_INSTALL_DIR"

    GODOT_ZIP_PATH="/tmp/godot_${GODOT_VERSION}_mono.zip"
    if command -v curl &>/dev/null; then
        curl -L --progress-bar -o "$GODOT_ZIP_PATH" "$GODOT_DOWNLOAD_URL"
    elif command -v wget &>/dev/null; then
        wget --show-progress -q -O "$GODOT_ZIP_PATH" "$GODOT_DOWNLOAD_URL"
    else
        err "需要 curl 或 wget 来下载 Godot"
    fi

    info "解压中..."
    unzip -q "$GODOT_ZIP_PATH" -d "$GODOT_INSTALL_DIR"
    rm "$GODOT_ZIP_PATH"

    if [[ "$OS" == "linux" ]]; then
        chmod +x "$GODOT_EXE"
    fi

    if [[ ! -f "$GODOT_EXE" ]]; then
        err "解压后找不到 exe，请检查: $GODOT_INSTALL_DIR"
    fi

    GODOT_FROM_CONFIG="$GODOT_EXE"
    ok "Godot 下载完成: $GODOT_EXE"
fi

# 写入 config.json
if command -v python3 &>/dev/null; then
    python3 -c "
import json, pathlib
p = pathlib.Path('$CONFIG_FILE')
cfg = json.loads(p.read_text()) if p.exists() else {}
cfg['godot_exe_path'] = '$GODOT_FROM_CONFIG'
p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
"
    ok "Godot 路径已写入 config.json"
else
    warn "无法自动写入 config.json，请手动填写 godot_exe_path: $GODOT_FROM_CONFIG"
fi

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
echo " ============================================"
echo "   依赖安装完成！"
echo ""
echo "   .NET 9 SDK : $(dotnet --version 2>/dev/null)"
echo "   Godot 路径 : $GODOT_FROM_CONFIG"
echo ""
echo "   如果还没跑过 ./tools/install.sh，现在可以运行了。"
echo " ============================================"
echo ""
