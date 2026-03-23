"""Tests for agent runner backend resolution."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.agent_runner import resolve_agent_backend


def test_agent_runner_selects_claude_backend():
    llm_cfg = {"mode": "agent_cli", "agent_backend": "claude"}
    assert resolve_agent_backend(llm_cfg) == "claude"


def test_agent_runner_selects_codex_backend():
    llm_cfg = {"mode": "agent_cli", "agent_backend": "codex"}
    assert resolve_agent_backend(llm_cfg) == "codex"
