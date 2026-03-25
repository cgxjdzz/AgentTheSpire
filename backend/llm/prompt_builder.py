from __future__ import annotations

from config import normalize_llm_config

_GLOBAL_PROMPT_HEADER = "## User Configured Global AI Instructions"


def append_global_ai_instructions(base_prompt: str, llm_cfg: dict) -> str:
    custom_prompt = normalize_llm_config(llm_cfg).get("custom_prompt", "").strip()
    if not custom_prompt:
        return base_prompt
    return f"{base_prompt.rstrip()}\n\n{_GLOBAL_PROMPT_HEADER}\n{custom_prompt}"
