"""Tests for LLM config normalization and legacy compatibility."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import normalize_config, normalize_llm_config


def test_normalize_legacy_claude_subscription_config():
    cfg = normalize_config({"llm": {"mode": "claude_subscription"}})
    assert cfg["llm"]["mode"] == "agent_cli"
    assert cfg["llm"]["agent_backend"] == "claude"


def test_normalize_legacy_api_key_config():
    cfg = normalize_config({"llm": {"mode": "api_key", "provider": "anthropic"}})
    assert cfg["llm"]["mode"] == "api"
    assert cfg["llm"]["provider"] == "anthropic"


def test_normalize_frontend_agent_cli_codex_payload():
    llm_cfg = normalize_llm_config({"mode": "agent_cli", "agent_backend": "codex"})
    assert llm_cfg["mode"] == "agent_cli"
    assert llm_cfg["agent_backend"] == "codex"


def test_normalize_frontend_api_payload():
    llm_cfg = normalize_llm_config({"mode": "api", "provider": "openai"})
    assert llm_cfg["mode"] == "api"
    assert llm_cfg["provider"] == "openai"


def test_normalize_llm_config_sets_default_custom_prompt():
    llm_cfg = normalize_llm_config({})
    assert llm_cfg["custom_prompt"] == ""
