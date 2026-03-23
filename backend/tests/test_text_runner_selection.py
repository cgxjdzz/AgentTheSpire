"""Tests for text runner backend resolution."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.text_runner import resolve_text_backend, resolve_model


def test_text_runner_uses_cli_backend_when_mode_is_agent_cli():
    llm_cfg = {"mode": "agent_cli", "agent_backend": "codex"}
    assert resolve_text_backend(llm_cfg) == "codex_cli"


def test_text_runner_uses_litellm_when_mode_is_api():
    llm_cfg = {"mode": "api", "provider": "openai"}
    assert resolve_text_backend(llm_cfg) == "litellm"


def test_resolve_model_supports_openai_provider():
    llm_cfg = {"mode": "api", "provider": "openai"}
    assert resolve_model(llm_cfg).startswith("openai/")
