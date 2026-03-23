from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Awaitable, Callable, Optional

import litellm

from config import get_config, normalize_llm_config
from llm.prompt_builder import append_global_ai_instructions

_MODEL_MAP = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "openai/gpt-5",
    "moonshot": "moonshot/moonshot-v1-8k",
    "deepseek": "deepseek/deepseek-chat",
    "qwen": "openai/qwen-plus",
    "zhipu": "zhipuai/glm-4-flash",
}


def _decode_output(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk", "cp936"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def resolve_model(llm_cfg: dict) -> str:
    cfg = normalize_llm_config(llm_cfg)
    if cfg.get("model"):
        return cfg["model"]
    provider = cfg.get("provider", "anthropic")
    return _MODEL_MAP.get(provider, "claude-sonnet-4-6")


def resolve_text_backend(llm_cfg: dict) -> str:
    cfg = normalize_llm_config(llm_cfg)
    if cfg.get("mode") == "agent_cli":
        return f"{cfg.get('agent_backend', 'claude')}_cli"
    return "litellm"


def _with_latest_runtime_custom_prompt(llm_cfg: dict) -> dict:
    runtime_llm_cfg = normalize_llm_config(get_config().get("llm"))
    merged = normalize_llm_config(llm_cfg)
    merged["custom_prompt"] = runtime_llm_cfg.get("custom_prompt", "")
    return merged


def build_text_prompt(prompt: str, llm_cfg: dict, use_runtime_config: bool = False) -> str:
    effective_cfg = _with_latest_runtime_custom_prompt(llm_cfg) if use_runtime_config else llm_cfg
    return append_global_ai_instructions(prompt, effective_cfg)


def build_system_prompt(system_prompt: str, llm_cfg: dict, use_runtime_config: bool = False) -> str:
    effective_cfg = _with_latest_runtime_custom_prompt(llm_cfg) if use_runtime_config else llm_cfg
    return append_global_ai_instructions(system_prompt, effective_cfg)


async def complete_text(
    prompt: str,
    llm_cfg: dict,
    cwd: Optional[Path] = None,
) -> str:
    prompt = build_text_prompt(prompt, llm_cfg, use_runtime_config=True)
    backend = resolve_text_backend(llm_cfg)
    if backend == "litellm":
        return await _complete_via_litellm(prompt, llm_cfg)
    if backend == "codex_cli":
        return await _complete_via_codex_cli(prompt, llm_cfg, cwd)
    return await _complete_via_claude_cli(prompt, cwd)


async def stream_text(
    system_prompt: str,
    user_prompt: str,
    llm_cfg: dict,
    on_chunk: Callable[[str], Awaitable[None]],
    cwd: Optional[Path] = None,
) -> str:
    backend = resolve_text_backend(llm_cfg)
    system_prompt = build_system_prompt(system_prompt, llm_cfg, use_runtime_config=True)
    if backend == "litellm":
        return await _stream_via_litellm(system_prompt, user_prompt, llm_cfg, on_chunk)

    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    if backend == "codex_cli":
        full_text = await _complete_via_codex_cli(full_prompt, llm_cfg, cwd)
    else:
        full_text = await _complete_via_claude_cli(full_prompt, cwd)
    chunk_size = 80
    for i in range(0, len(full_text), chunk_size):
        await on_chunk(full_text[i:i + chunk_size])
        await asyncio.sleep(0)
    return full_text


async def _complete_via_claude_cli(prompt: str, cwd: Optional[Path]) -> str:
    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True,
                timeout=180,
                cwd=str(cwd) if cwd else None,
            ),
        ),
        timeout=185,
    )
    return result.stdout.decode("utf-8", errors="replace").strip()


async def _complete_via_codex_cli(prompt: str, llm_cfg: dict, cwd: Optional[Path]) -> str:
    codex_exe = shutil.which("codex.cmd" if os.name == "nt" else "codex") or shutil.which("codex")
    if not codex_exe:
        raise RuntimeError("未找到 Codex CLI，请先安装并确保 codex 可执行文件在 PATH 中")

    cmd = [
        codex_exe,
        "exec",
        "--full-auto",
        "--color", "never",
        "--skip-git-repo-check",
        "-",
    ]
    if cwd:
        cmd[2:2] = ["-C", str(cwd)]
    model = normalize_llm_config(llm_cfg).get("model")
    if model:
        cmd[2:2] = ["-m", model]

    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                input=prompt.encode("utf-8", errors="replace"),
                capture_output=True,
                timeout=180,
                cwd=str(cwd) if cwd else None,
            ),
        ),
        timeout=185,
    )
    if result.returncode != 0:
        detail = _decode_output(result.stderr).strip()
        raise RuntimeError(f"Codex CLI 退出码 {result.returncode}\n{detail}")
    return _decode_output(result.stdout).strip()


async def _complete_via_litellm(prompt: str, llm_cfg: dict) -> str:
    response = await litellm.acompletion(
        model=resolve_model(llm_cfg),
        messages=[{"role": "user", "content": prompt}],
        api_key=llm_cfg.get("api_key") or None,
        api_base=llm_cfg.get("base_url") or None,
        temperature=0.2,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


async def _stream_via_litellm(
    system_prompt: str,
    user_prompt: str,
    llm_cfg: dict,
    on_chunk: Callable[[str], Awaitable[None]],
) -> str:
    stream = await litellm.acompletion(
        model=resolve_model(llm_cfg),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        api_key=llm_cfg.get("api_key") or None,
        api_base=llm_cfg.get("base_url") or None,
        temperature=0.2,
        max_tokens=2048,
        stream=True,
    )

    full_text: list[str] = []
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            full_text.append(delta)
            await on_chunk(delta)

    return "".join(full_text)
