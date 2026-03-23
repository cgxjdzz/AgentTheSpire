from __future__ import annotations

from pathlib import Path

from config import get_config, normalize_llm_config
from llm.agent_backends import run_claude_cli, run_codex_cli


def resolve_agent_backend(llm_cfg: dict) -> str:
    cfg = normalize_llm_config(llm_cfg)
    return cfg.get("agent_backend", "claude")


async def run_agent_task(prompt: str, project_root: Path, stream_callback=None) -> str:
    llm_cfg = get_config()["llm"]
    backend = resolve_agent_backend(llm_cfg)

    if backend == "codex":
        return await run_codex_cli(prompt, project_root, llm_cfg, stream_callback)
    return await run_claude_cli(prompt, project_root, llm_cfg, stream_callback)
