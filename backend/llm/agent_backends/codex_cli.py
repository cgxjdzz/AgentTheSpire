from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


def _decode_output(raw: bytes) -> str:
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
    cmd = [
        codex_exe,
        "exec",
        "--full-auto",
        "--color", "never",
        "--skip-git-repo-check",
        "-C", str(project_root),
        "-o", str(output_file),
        "-",
    ]
    if model:
        cmd.extend(["-m", model])

    loop = asyncio.get_event_loop()
    line_queue: asyncio.Queue = asyncio.Queue()

    def _reader():
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
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
        assert proc.stdin is not None

        proc.stdin.write(prompt.encode("utf-8", errors="replace"))
        proc.stdin.close()

        def _pump(pipe, tag):
            for raw_line in pipe:
                decoded = _decode_output(raw_line)
                if decoded:
                    loop.call_soon_threadsafe(line_queue.put_nowait, (tag, decoded))

        stdout_thread = threading.Thread(target=_pump, args=(proc.stdout, "stdout"), daemon=True)
        stderr_thread = threading.Thread(target=_pump, args=(proc.stderr, "stderr"), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        proc.wait()
        stdout_thread.join()
        stderr_thread.join()
        loop.call_soon_threadsafe(line_queue.put_nowait, ("done", proc.returncode))

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    streamed_chunks: list[str] = []
    error_chunks: list[str] = []

    try:
        while True:
            tag, data = await line_queue.get()

            if tag == "error":
                thread.join()
                raise RuntimeError(f"无法启动 Codex CLI: {data}")

            if tag == "done":
                thread.join()
                if data != 0:
                    detail = "".join(error_chunks) or "".join(streamed_chunks) or "(无输出)"
                    raise RuntimeError(f"Codex CLI 退出码 {data}\n{detail}")
                break

            if tag == "stderr":
                error_chunks.append(data)
            else:
                streamed_chunks.append(data)
                if stream_callback:
                    await stream_callback(data)

        if output_file.exists():
            final_text = output_file.read_text(encoding="utf-8", errors="replace").strip()
        else:
            final_text = "".join(streamed_chunks).strip()

        return final_text
    finally:
        try:
            output_file.unlink(missing_ok=True)
        except Exception:
            pass
