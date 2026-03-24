"""Tests for approval action models and policy defaults."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.models import ActionRequest
from approval.policies import infer_risk_level, should_require_approval


def test_action_request_serializes_minimum_fields():
    action = ActionRequest(
        kind="run_command",
        title="Build project",
        reason="Need to compile the generated mod",
        payload={"command": ["dotnet", "publish"]},
        risk_level="high",
        requires_approval=True,
        source_backend="codex",
        source_workflow="single_asset",
    )

    data = action.to_dict()
    assert data["kind"] == "run_command"
    assert data["title"] == "Build project"
    assert data["payload"]["command"] == ["dotnet", "publish"]
    assert data["status"] == "pending"
    assert data["action_id"]


def test_infer_risk_level_defaults_by_action_kind():
    assert infer_risk_level("read_file") == "low"
    assert infer_risk_level("write_file") == "medium"
    assert infer_risk_level("run_command") == "high"
    assert infer_risk_level("build_project") == "high"


def test_should_require_approval_for_medium_and_high_risk():
    assert should_require_approval("low") is False
    assert should_require_approval("medium") is True
    assert should_require_approval("high") is True
