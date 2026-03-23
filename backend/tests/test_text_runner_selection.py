"""Tests for text runner backend resolution."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.text_runner import build_text_prompt, build_system_prompt, resolve_text_backend, resolve_model


def test_text_runner_uses_cli_backend_when_mode_is_agent_cli():
    llm_cfg = {"mode": "agent_cli", "agent_backend": "codex"}
    assert resolve_text_backend(llm_cfg) == "codex_cli"


def test_text_runner_uses_litellm_when_mode_is_api():
    llm_cfg = {"mode": "api", "provider": "openai"}
    assert resolve_text_backend(llm_cfg) == "litellm"


def test_resolve_model_supports_openai_provider():
    llm_cfg = {"mode": "api", "provider": "openai"}
    assert resolve_model(llm_cfg).startswith("openai/")


def test_build_text_prompt_appends_custom_prompt():
    llm_cfg = {"custom_prompt": "always answer in Chinese"}
    prompt = build_text_prompt("base prompt", llm_cfg)
    assert "base prompt" in prompt
    assert "always answer in Chinese" in prompt
    assert "User Configured Global AI Instructions" in prompt


def test_build_text_prompt_keeps_original_when_custom_prompt_blank():
    assert build_text_prompt("base prompt", {"custom_prompt": "   "}) == "base prompt"


def test_build_system_prompt_appends_custom_prompt():
    llm_cfg = {"custom_prompt": "prefer concise output"}
    prompt = build_system_prompt("system prompt", llm_cfg)
    assert "system prompt" in prompt
    assert "prefer concise output" in prompt


def test_build_text_prompt_uses_latest_runtime_custom_prompt_when_requested(monkeypatch):
    from llm import text_runner

    monkeypatch.setattr(text_runner, "get_config", lambda: {"llm": {"custom_prompt": ""}})
    assert text_runner.build_text_prompt(
        "base prompt",
        {"custom_prompt": "stale prompt"},
        use_runtime_config=True,
    ) == "base prompt"
