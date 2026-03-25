#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
echo "启动 AgentTheSpire..."
echo "打开浏览器访问 http://localhost:7860"
python3 "$ROOT_DIR/backend/main.py" &
sleep 2 && open "http://localhost:7860" 2>/dev/null || xdg-open "http://localhost:7860" 2>/dev/null || true
wait
