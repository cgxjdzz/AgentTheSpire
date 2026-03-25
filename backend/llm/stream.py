"""LLM 流式调用封装。"""
from __future__ import annotations

from typing import Callable, Awaitable

from llm.text_runner import stream_text


async def stream_analysis(
    system_prompt: str,
    user_prompt: str,
    llm_cfg: dict,
    on_chunk: Callable[[str], Awaitable[None]],
) -> str:
    return await stream_text(system_prompt, user_prompt, llm_cfg, on_chunk)
