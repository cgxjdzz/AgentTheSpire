"""Tests for agent runner backend resolution."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.agent_runner import build_agent_prompt, resolve_agent_backend


def test_agent_runner_selects_claude_backend():
    llm_cfg = {"mode": "agent_cli", "agent_backend": "claude"}
    assert resolve_agent_backend(llm_cfg) == "claude"


def test_agent_runner_selects_codex_backend():
    llm_cfg = {"mode": "agent_cli", "agent_backend": "codex"}
    assert resolve_agent_backend(llm_cfg) == "codex"


def test_build_agent_prompt_appends_custom_prompt():
    llm_cfg = {"custom_prompt": "prefer minimal edits"}
    prompt = build_agent_prompt("fix the project", llm_cfg)
    assert "fix the project" in prompt
    assert "prefer minimal edits" in prompt
    assert "User Configured Global AI Instructions" in prompt


def test_build_agent_prompt_keeps_original_when_custom_prompt_blank():
    assert build_agent_prompt("fix the project", {"custom_prompt": ""}) == "fix the project"


def test_build_agent_prompt_uses_latest_runtime_custom_prompt_when_requested(monkeypatch):
    from llm import agent_runner

    monkeypatch.setattr(agent_runner, "get_config", lambda: {"llm": {"custom_prompt": ""}})
    assert agent_runner.build_agent_prompt(
        "fix the project",
        {"custom_prompt": "stale prompt"},
        use_runtime_config=True,
    ) == "fix the project"
