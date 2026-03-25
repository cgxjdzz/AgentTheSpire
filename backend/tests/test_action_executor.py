"""Tests for approval executor behavior."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.executor import ActionResult, ApprovalExecutor, LocalApprovalExecutor
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


@pytest.mark.asyncio
async def test_local_executor_writes_file_inside_allowed_root(tmp_path):
    executor = LocalApprovalExecutor(allowed_roots=[tmp_path], allowed_commands=[])
    action = ActionRequest(
        kind="write_file",
        title="Write file",
        reason="Need generated source",
        payload={"path": "Cards/TestCard.cs", "content": "class TestCard {}"},
        risk_level="medium",
        requires_approval=True,
        source_backend="codex",
        source_workflow="single_asset",
    )

    result = await executor.execute_action(action)

    written = tmp_path / "Cards" / "TestCard.cs"
    assert result.success is True
    assert written.read_text(encoding="utf-8") == "class TestCard {}"


@pytest.mark.asyncio
async def test_local_executor_rejects_command_outside_allowlist(tmp_path):
    executor = LocalApprovalExecutor(allowed_roots=[tmp_path], allowed_commands=[["dotnet"]])
    action = ActionRequest(
        kind="run_command",
        title="Run npm",
        reason="Should be blocked",
        payload={"command": ["npm", "--version"], "cwd": "."},
        risk_level="high",
        requires_approval=True,
        source_backend="codex",
        source_workflow="single_asset",
    )

    with pytest.raises(PermissionError):
        await executor.execute_action(action)
