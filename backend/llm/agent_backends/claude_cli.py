from __future__ import annotations

import json
import os
from pathlib import Path

from ._runner import run_streaming


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
                parts.append(f"[{name}] {detail}\n" if detail else f"[{name}]\n")
        return "".join(parts)
    if event.get("type") == "result":
        return event.get("result", "")
    return ""


def _process_line(line: str) -> str | None:
    try:
        return _extract_text(json.loads(line)) or None
    except json.JSONDecodeError:
        return line


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

    output_chunks, _ = await run_streaming(
        cmd,
        cwd=project_root,
        env=env,
        name="Claude CLI",
        process_line=_process_line,
        stream_callback=stream_callback,
    )
    return "".join(output_chunks)
