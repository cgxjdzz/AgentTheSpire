"""
Mod 分析器：扫描 mod 项目 .cs 源码和 localization 文件，交给 LLM 分析内容。
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, WebSocket

from config import get_config
from llm.stream import stream_analysis
from llm.stage_events import build_stage_event

router = APIRouter()

_SKIP_DIRS = {"bin", "obj", ".godot", "packages", ".git", ".vs", "__pycache__"}

_SYSTEM_PROMPT = """\
你是 Slay the Spire 2 mod 开发专家。请分析给定的 mod 源码，用中文告诉用户以下内容：

1. **Mod 基本信息**：名称、主题、整体风格
2. **卡牌列表**：每张卡的名称（英文/中文）、类型（攻击/技能/力量）、费用、效果、数值
3. **遗物列表**：每个遗物的名称、稀有度、触发条件、效果
4. **Power/Buff 列表**：名称、叠层方式、效果
5. **特殊机制**：Harmony Patch、自定义系统、特殊交互等

格式要清晰，数值要具体，方便用户后续描述想修改哪里。
如果某类内容不存在，可以省略该节。
"""


async def _send_stage(ws: WebSocket, scope: str, stage: str, message: str):
    payload = build_stage_event(scope, stage, message)
    if payload:
        await ws.send_text(json.dumps({"event": "stage_update", **payload}))


def _scan_mod_files(project_root: Path) -> tuple[str, int]:
    """扫描 mod 项目的 .cs 和 localization JSON 文件，返回 (合并内容, 文件数)。"""
    parts: list[str] = []
    file_count = 0
    total_chars = 0
    MAX_TOTAL = 80_000  # 约 20k token，留足 LLM 回复空间

    # .cs 文件（按路径排序，Cards/Relics/Powers 优先）
    cs_files = sorted(
        (f for f in project_root.rglob("*.cs")
         if not any(p in _SKIP_DIRS for p in f.parts)),
        key=lambda f: (
            0 if any(p in {"Cards", "Relics", "Powers", "Patches"} for p in f.parts) else 1,
            str(f)
        )
    )

    for f in cs_files:
        if total_chars >= MAX_TOTAL:
            break
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            rel = str(f.relative_to(project_root))
            snippet = f"// {rel}\n{content[:4000]}"
            if len(content) > 4000:
                snippet += "\n// ... (truncated)"
            parts.append(snippet)
            total_chars += len(snippet)
            file_count += 1
        except Exception:
            pass

    # localization JSON
    for f in sorted(project_root.rglob("*.json")):
        if "localization" not in f.parts:
            continue
        if total_chars >= MAX_TOTAL:
            break
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            rel = str(f.relative_to(project_root))
            snippet = f"// Localization: {rel}\n{content[:2000]}"
            if len(content) > 2000:
                snippet += "\n// ... (truncated)"
            parts.append(snippet)
            total_chars += len(snippet)
            file_count += 1
        except Exception:
            pass

    return "\n\n".join(parts), file_count


@router.websocket("/ws/analyze-mod")
async def ws_analyze_mod(ws: WebSocket):
    """
    WebSocket 端点：扫描 mod 项目源码，流式返回 LLM 分析结果。

    客户端发送：{ "project_root": "E:/STS2mod/MyMod" }

    服务端推流：
    - scan_info: { files: N }
    - stream:    { chunk }
    - done:      { full }
    - error:     { message }
    """
    await ws.accept()
    try:
        raw = await ws.receive_text()
        params = json.loads(raw)
        project_root = Path(params.get("project_root", ""))

        if not project_root.exists():
            await ws.send_text(json.dumps({
                "event": "error",
                "message": f"路径不存在：{project_root}"
            }))
            return

        await _send_stage(ws, "text", "reading_input", "正在扫描 Mod 源码...")
        file_content, file_count = _scan_mod_files(project_root)

        if not file_content.strip():
            await ws.send_text(json.dumps({
                "event": "error",
                "message": f"未在 {project_root} 找到任何 .cs 源码文件"
            }))
            return

        await ws.send_text(json.dumps({"event": "scan_info", "files": file_count}))

        await _send_stage(ws, "text", "preparing_prompt", "正在整理源码分析上下文...")
        prompt = (
            f"以下是 mod 项目的源码（路径：{project_root}）：\n\n"
            f"```\n{file_content}\n```\n\n"
            "请分析这个 mod 的内容。"
        )

        cfg = get_config()
        llm_cfg = cfg["llm"]
        streamed = False

        async def send_chunk(chunk: str):
            nonlocal streamed
            if not streamed:
                streamed = True
                await _send_stage(ws, "text", "ai_streaming", "AI 已开始输出分析结果...")
            await ws.send_text(json.dumps({"event": "stream", "chunk": chunk}))

        await _send_stage(ws, "text", "ai_running", "正在调用 AI 分析 Mod...")
        full_text = await stream_analysis(_SYSTEM_PROMPT, prompt, llm_cfg, send_chunk)
        await _send_stage(ws, "text", "done", "Mod 分析完成")
        await ws.send_text(json.dumps({"event": "done", "full": full_text}))

    except Exception as e:
        try:
            await ws.send_text(json.dumps({"event": "error", "message": str(e)}))
        except Exception:
            pass
