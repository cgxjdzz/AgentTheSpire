"""Tests for approval-related config defaults."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import normalize_config


def test_approval_mode_defaults_to_legacy_direct():
    cfg = normalize_config(None)
    assert cfg["llm"]["execution_mode"] == "legacy_direct"


def test_approval_defaults_include_policy_flags():
    cfg = normalize_config(None)
    assert cfg["approval"]["auto_execute_low_risk"] is False
    assert cfg["approval"]["allowed_commands"] == []
    assert cfg["approval"]["allowed_roots"] == []


def test_approval_default_lists_are_not_shared_between_configs():
    cfg1 = normalize_config(None)
    cfg1["approval"]["allowed_commands"].append("dotnet")
    cfg1["approval"]["allowed_roots"].append("I:/WebCode/AgentTheSpire")

    cfg2 = normalize_config(None)
    assert cfg2["approval"]["allowed_commands"] == []
    assert cfg2["approval"]["allowed_roots"] == []
