"""
共享子进程流式运行器。
两个 agent backend (claude_cli / codex_cli) 共用此模块处理
subprocess 启动、stdout/stderr pump 和 asyncio queue 消费。
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip()


async def run_streaming(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict,
    name: str = "CLI",
    stdin_data: bytes | None = None,
    decode: Callable[[bytes], str] = _default_decode,
    process_line: Callable[[str], str | None] | None = None,
    stream_callback=None,
) -> tuple[list[str], list[str]]:
    """
    启动子进程，并发 pump stdout/stderr，异步消费输出。

    参数
    ----
    cmd            : 命令列表
    cwd            : 工作目录
    env            : 环境变量
    name           : 用于错误信息的名称（如 "Claude CLI"）
    stdin_data     : 若不为 None，写入进程 stdin 后关闭
    decode         : bytes → str 的解码函数（可自定义多编码重试）
    process_line   : stdout 行 → 最终文本（返回 None 表示忽略该行）
                     默认直接返回原始行
    stream_callback: async (text: str) -> None，实时推流

    返回
    ----
    (output_chunks, error_chunks)
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    def _pump(pipe, tag: str):
        for raw in pipe:
            text = decode(raw)
            if text:
                loop.call_soon_threadsafe(queue.put_nowait, (tag, text))

    def _reader():
        stdin_pipe = subprocess.PIPE if stdin_data is not None else None
        logger.debug("[%s] 启动进程: %s (cwd=%s)", name, cmd[0], cwd)
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=stdin_pipe,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(cwd),
                env=env,
            )
        except Exception as exc:
            logger.error("[%s] 进程启动失败: %s", name, exc)
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
            return

        logger.info("[%s] 进程已启动 pid=%s", name, proc.pid)
        if stdin_data is not None:
            assert proc.stdin is not None
            proc.stdin.write(stdin_data)
            proc.stdin.close()

        t_out = threading.Thread(target=_pump, args=(proc.stdout, "stdout"), daemon=True)
        t_err = threading.Thread(target=_pump, args=(proc.stderr, "stderr"), daemon=True)
        t_out.start()
        t_err.start()
        proc.wait()
        t_out.join()
        t_err.join()
        logger.info("[%s] 进程退出 pid=%s returncode=%s", name, proc.pid, proc.returncode)
        loop.call_soon_threadsafe(queue.put_nowait, ("done", proc.returncode))

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    output_chunks: list[str] = []
    error_chunks: list[str] = []

    while True:
        tag, data = await queue.get()

        if tag == "error":
            thread.join()
            logger.error("[%s] 无法启动进程: %s", name, data)
            raise RuntimeError(f"无法启动 {name}: {data}")

        if tag == "done":
            returncode = int(data)  # type: ignore[arg-type]
            thread.join()
            if returncode != 0:
                detail = "".join(error_chunks) or "".join(output_chunks) or "(无输出)"
                logger.error("[%s] 退出码=%s\n%s", name, returncode, detail[:500])
                raise RuntimeError(f"{name} 退出码 {returncode}\n{detail}")
            logger.info("[%s] 执行完成，输出 %d 块", name, len(output_chunks))
            return output_chunks, error_chunks

        if tag == "stderr":
            line = str(data)
            error_chunks.append(line)
            logger.warning("[%s][stderr] %s", name, line.rstrip())
            if stream_callback:
                await stream_callback(f"[stderr] {line}")
            continue

        # stdout
        raw_line = str(data)
        text = process_line(raw_line) if process_line else raw_line
        if text:
            output_chunks.append(text)
            if stream_callback:
                await stream_callback(text)
