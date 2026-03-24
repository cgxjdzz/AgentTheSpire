"""Tests for the action prompt builder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.action_prompt import build_action_prompt


def test_action_prompt_includes_required_keywords():
    requirements = "描述用户对关键要素的要求。"
    prompt = build_action_prompt(requirements)

    assert "Output ONLY JSON" in prompt
    assert "actions" in prompt
    assert "User Input Requirements" in prompt
    assert requirements in prompt


def test_action_prompt_delivers_action_template():
    prompt = build_action_prompt("需要明确的步骤")

    assert '{"actions"' in prompt
    assert '"kind"' in prompt
    assert "title" in prompt
    assert '"reason"' in prompt
    assert "payload" in prompt
