#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo " =============================="
echo "   AgentTheSpire Installer"
echo " =============================="
echo ""

# 检查 Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] 未找到 python3，请先安装 Python 3.11+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &>/dev/null; then
    echo "[ERROR] 未找到 node，请先安装 Node.js 18+"
    exit 1
fi

# 检查 claude CLI
if ! command -v claude &>/dev/null; then
    echo "[WARN] 未找到 claude CLI。"
    echo "       如需订阅账号模式，请运行: npm install -g @anthropic-ai/claude-code"
    echo ""
fi

# 后端依赖
echo "[1/3] 安装后端 Python 依赖..."
cd "$ROOT_DIR/backend"
python3 -m pip install -r requirements.txt

echo ""
echo "[1/3] 预下载 rembg 模型..."
if ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import json
import os
from pathlib import Path
from rembg import new_session

root = Path(os.environ["ROOT_DIR"])
cfg_path = root / "config.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
model = cfg.get("image_gen", {}).get("rembg_model", "birefnet-general")
print(f"[INFO] rembg model: {model}")
new_session(model)
print("[OK] rembg model ready")
PY
then
    echo "[OK] rembg 模型已就绪"
else
    echo "[WARN] rembg 模型预下载失败，首次抠图时会自动下载"
fi

# 前端依赖
echo ""
echo "[2/3] 安装前端 Node.js 依赖..."
cd "$ROOT_DIR/frontend"
npm install

# 前端构建
echo ""
echo "[3/3] 构建前端..."
npm run build

# 询问本地图生
echo ""
read -r -p "是否安装本地图像生成（ComfyUI + FLUX.2，需约 12GB 磁盘）？[y/N] " LOCAL_IMG
if [[ "$LOCAL_IMG" =~ ^[Yy]$ ]]; then
    echo "正在安装 ComfyUI..."
    cd "$ROOT_DIR"
    git clone https://github.com/comfyanonymous/ComfyUI.git comfyui
    cd comfyui
    python3 -m pip install -r requirements.txt
    echo ""
    echo "[提示] FLUX.2 模型文件需手动下载放入 comfyui/models/checkpoints/"
    echo "       下载地址：https://huggingface.co/black-forest-labs/FLUX.2-dev"
    python3 -c "
import json, pathlib
p = pathlib.Path('$ROOT_DIR/config.json')
cfg = json.loads(p.read_text()) if p.exists() else {}
cfg.setdefault('image_gen', {})['local'] = {'comfyui_url': 'http://127.0.0.1:8188', 'installed': True, 'model_path': ''}
p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
"
fi

echo ""
echo " =============================="
echo "   安装完成！运行 ./tools/start.sh 启动"
echo " =============================="
echo ""