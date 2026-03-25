"""
游戏日志分析器：读取 STS2 的 godot.log，提取报错信息，交给 LLM 分析。
支持 WebSocket 流式返回分析结果。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, WebSocket

from config import get_config
from llm.stream import stream_analysis
from llm.stage_events import build_stage_event

router = APIRouter()

# STS2 日志路径（Windows）
_LOG_PATH = Path(os.environ.get("APPDATA", "")) / "SlayTheSpire2" / "logs" / "godot.log"

# 提取 log 时只保留最后这么多行（避免 token 爆炸）
_MAX_LINES = 300

_SYSTEM_PROMPT = """\
你是一名 Slay the Spire 2 mod 开发专家，擅长分析游戏崩溃、黑屏、mod 加载失败等问题。
你会收到游戏日志（godot.log）中提取的关键内容，请：
1. 判断出现了什么问题（崩溃/黑屏/功能异常/mod 加载失败等）
2. 指出根本原因（精确到具体的错误信息、类名、方法名）
3. 给出修复建议（具体到应该改哪个文件、哪段代码）

常见问题参考：
- LocException / token type StartObject：localization JSON 格式错误，用了嵌套对象而不是 flat key-value
- Found end tag X expected Y：localization 文本里有方括号 [] 被解析为 BBCode 标签
- DuplicateModelException：用 new XxxModel() 而不是 ModelDb.GetById() / .ToMutable()
- Pack created with newer version：dotnet publish 用了错误的 Godot 版本（需 4.5.1）
- must be marked with PoolAttribute：Card/Relic 类缺少 [Pool(...)] 标注
- 黑屏无报错：通常是 dotnet build 未 publish，PCK 未更新

请用中文回答，格式清晰，重点突出。
"""


async def _send_stage(ws: WebSocket, scope: str, stage: str, message: str):
    payload = build_stage_event(scope, stage, message)
    if payload:
        await ws.send_text(json.dumps({"event": "stage_update", **payload}))


def _read_log() -> tuple[str, bool]:
    """
    读取游戏日志，提取最后 _MAX_LINES 行以及所有包含 ERROR/Exception/CRITICAL 的行。
    返回 (提取内容, 日志是否存在)。
    """
    if not _LOG_PATH.exists():
        return "", False

    text = _LOG_PATH.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # 取最后 _MAX_LINES 行
    tail = lines[-_MAX_LINES:]

    # 额外捞出全文中的 ERROR/Exception/CRITICAL 行（可能在 tail 之前）
    error_pattern = re.compile(r"error|exception|critical|crash|fail", re.IGNORECASE)
    extra = [l for l in lines[:-_MAX_LINES] if error_pattern.search(l)]

    combined = []
    if extra:
        combined.append("=== 日志前段错误摘录 ===")
        combined.extend(extra[-100:])   # 最多 100 条
        combined.append("=== 日志末段（最后300行）===")
    combined.extend(tail)

    return "\n".join(combined), True


def _build_prompt(extra_context: str) -> str:
    log_content, exists = _read_log()
    if not exists:
        return f"游戏日志文件不存在：{_LOG_PATH}\n请确认游戏已运行过至少一次。"

    parts = ["以下是 STS2 游戏日志内容：\n```\n", log_content, "\n```"]
    if extra_context:
        parts.append(f"\n\n用户补充说明：{extra_context}")
    parts.append("\n\n请分析上述日志，找出问题原因并给出修复建议。")
    return "".join(parts)


@router.websocket("/ws/analyze-log")
async def ws_analyze_log(ws: WebSocket):
    """
    WebSocket 端点：流式返回日志分析结果。

    客户端发送：
    {
        "context": "黑屏了，刚加了 MyMod"   // 可选，用户补充描述
    }

    服务端推流事件：
    - log_info: { lines: N }              // 读到了多少行
    - stream:   { chunk: "..." }          // LLM 流式文本片段
    - done:     { full: "完整分析结果" }
    - error:    { message: "..." }
    """
    await ws.accept()
    try:
        raw = await ws.receive_text()
        params = json.loads(raw)
        extra_context = params.get("context", "")

        # 读日志
        await _send_stage(ws, "text", "reading_input", "正在读取游戏日志...")
        log_content, exists = _read_log()
        if not exists:
            await ws.send_text(json.dumps({
                "event": "error",
                "message": f"日志文件不存在：{_LOG_PATH}"
            }))
            return

        line_count = log_content.count("\n") + 1
        await ws.send_text(json.dumps({"event": "log_info", "lines": line_count}))

        # 构建 prompt
        await _send_stage(ws, "text", "preparing_prompt", "正在整理日志分析上下文...")
        prompt = _build_prompt(extra_context)

        cfg = get_config()
        llm_cfg = cfg["llm"]
        streamed = False

        async def send_chunk(chunk: str):
            nonlocal streamed
            if not streamed:
                streamed = True
                await _send_stage(ws, "text", "ai_streaming", "AI 已开始输出分析结果...")
            await ws.send_text(json.dumps({"event": "stream", "chunk": chunk}))

        await _send_stage(ws, "text", "ai_running", "正在调用 AI 分析日志...")
        full_text = await stream_analysis(_SYSTEM_PROMPT, prompt, llm_cfg, send_chunk)
        await _send_stage(ws, "text", "done", "日志分析完成")
        await ws.send_text(json.dumps({"event": "done", "full": full_text}))

    except Exception as e:
        try:
            await ws.send_text(json.dumps({"event": "error", "message": str(e)}))
        except Exception:
            pass
