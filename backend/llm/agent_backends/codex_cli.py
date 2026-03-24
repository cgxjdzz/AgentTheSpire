from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from ._runner import run_streaming


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk", "cp936"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


async def run(prompt: str, project_root: Path, llm_cfg: dict, stream_callback=None) -> str:
    env = os.environ.copy()
    if llm_cfg.get("api_key"):
        env["OPENAI_API_KEY"] = llm_cfg["api_key"]
    if llm_cfg.get("base_url"):
        env["OPENAI_BASE_URL"] = llm_cfg["base_url"]

    codex_exe = shutil.which("codex.cmd" if os.name == "nt" else "codex") or shutil.which("codex")
    if not codex_exe:
        raise RuntimeError("未找到 Codex CLI，请先安装并确保 codex 可执行文件在 PATH 中")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        output_file = Path(tmp.name)

    model = llm_cfg.get("model") or None
    # Windows 上 Codex 沙箱需要 CreateProcessAsUserW 权限（error 1920），普通用户无此权限。
    # --dangerously-bypass-approvals-and-sandbox 已包含 --full-auto 的自动审批功能，二者互斥。
    disable_sandbox = llm_cfg.get("codex_disable_sandbox", os.name == "nt")
    auto_flag = "--dangerously-bypass-approvals-and-sandbox" if disable_sandbox else "--full-auto"
    cmd = [
        codex_exe,
        "exec",
        auto_flag,
        "--color", "never",
        "--skip-git-repo-check",
        "-C", str(project_root),
        "-o", str(output_file),
        "-",
    ]
    if model:
        cmd.extend(["-m", model])

    try:
        output_chunks, _ = await run_streaming(
            cmd,
            cwd=project_root,
            env=env,
            name="Codex CLI",
            stdin_data=prompt.encode("utf-8", errors="replace"),
            decode=_decode,
            stream_callback=stream_callback,
        )

        if output_file.exists():
            return output_file.read_text(encoding="utf-8", errors="replace").strip()
        return "".join(output_chunks).strip()
    finally:
        output_file.unlink(missing_ok=True)
