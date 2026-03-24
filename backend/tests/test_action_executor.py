"""Tests for approval executor abstraction."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.executor import ActionResult, ApprovalExecutor
from approval.models import ActionRequest


def _make_action() -> ActionRequest:
    return ActionRequest(
        kind="run_command",
        title="Build project",
        reason="Need to compile generated files",
        payload={"command": ["dotnet", "publish"]},
        risk_level="high",
        requires_approval=True,
        source_backend="codex",
        source_workflow="single_asset",
    )


def test_action_result_keeps_success_payload():
    result = ActionResult(success=True, output="ok", metadata={"exit_code": 0})
    assert result.success is True
    assert result.output == "ok"
    assert result.metadata == {"exit_code": 0}


@pytest.mark.asyncio
async def test_executor_interface_requires_subclass_implementation():
    executor = ApprovalExecutor()

    with pytest.raises(NotImplementedError):
        await executor.execute_action(_make_action())
