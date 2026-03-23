from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
from pathlib import Path


def _extract_text(event: dict) -> str:
    if event.get("type") == "assistant" and event.get("message"):
        msg = event["message"]
        parts = []
        for block in msg.get("content", []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(block["text"])
            elif block.get("type") == "tool_use":
                name = block.get("name", "Tool")
                inp = block.get("input", {})
                detail = (
                    inp.get("command")
                    or inp.get("file_path")
                    or inp.get("pattern")
                    or inp.get("prompt")
                    or ""
                )
                summary = f"[{name}] {detail}" if detail else f"[{name}]"
                parts.append(summary + "\n")
        return "".join(parts)
    if event.get("type") == "result":
        return event.get("result", "")
    return ""


async def run(prompt: str, project_root: Path, llm_cfg: dict, stream_callback=None) -> str:
    env = os.environ.copy()
    if llm_cfg.get("api_key"):
        env["ANTHROPIC_API_KEY"] = llm_cfg["api_key"]
    if llm_cfg.get("base_url"):
        env["ANTHROPIC_BASE_URL"] = llm_cfg["base_url"]

    cmd = [
        "claude",
        "--print",
        "--verbose",
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "-p", prompt,
    ]

    loop = asyncio.get_event_loop()
    line_queue: asyncio.Queue = asyncio.Queue()

    def _reader():
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(project_root),
                env=env,
            )
        except Exception as exc:
            loop.call_soon_threadsafe(line_queue.put_nowait, ("error", str(exc)))
            return

        assert proc.stdout is not None
        assert proc.stderr is not None

        for raw_line in proc.stdout:
            decoded = raw_line.decode("utf-8", errors="replace").strip()
            if decoded:
                loop.call_soon_threadsafe(line_queue.put_nowait, ("line", decoded))

        stderr_text = proc.stderr.read().decode("utf-8", errors="replace").strip()
        proc.wait()
        loop.call_soon_threadsafe(
            line_queue.put_nowait,
            ("done", (proc.returncode, stderr_text)),
        )

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    full_output = []

    while True:
        tag, data = await line_queue.get()

        if tag == "error":
            thread.join()
            raise RuntimeError(f"无法启动 Claude CLI: {data}")

        if tag == "done":
            returncode, stderr_text = data
            thread.join()
            if returncode != 0:
                detail = stderr_text or "".join(full_output) or "(无输出)"
                raise RuntimeError(f"Claude CLI 退出码 {returncode}\n{detail}")
            return "".join(full_output)

        try:
            event = json.loads(data)
            text = _extract_text(event)
        except json.JSONDecodeError:
            text = data

        if text:
            full_output.append(text)
            if stream_callback:
                await stream_callback(text)
