"""Tests for approval service orchestration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.service import ApprovalService
from approval.store import InMemoryApprovalStore


def test_service_converts_ai_plan_into_pending_requests():
    store = InMemoryApprovalStore()
    service = ApprovalService(store)

    plan = {
        "summary": "Create one card and then build",
        "actions": [
            {
                "kind": "write_file",
                "title": "Write card source",
                "reason": "Need the new card implementation",
                "payload": {"path": "Cards/TestCard.cs", "content": "class TestCard {}"},
            },
            {
                "kind": "build_project",
                "title": "Build mod",
                "reason": "Need to validate generated files",
                "payload": {"command": ["dotnet", "publish"]},
            },
        ],
    }

    actions = service.create_requests_from_plan(
        plan,
        source_backend="codex",
        source_workflow="single_asset",
    )

    assert len(actions) == 2
    assert actions[0].risk_level == "medium"
    assert actions[0].requires_approval is True
    assert actions[0].status == "pending"
    assert actions[1].risk_level == "high"
    assert len(store.list_requests()) == 2


def test_service_uses_low_risk_policy_for_reads():
    service = ApprovalService(InMemoryApprovalStore())

    actions = service.create_requests_from_plan(
        {
            "actions": [
                {
                    "kind": "read_file",
                    "title": "Read MainFile.cs",
                    "reason": "Need namespace and ModId",
                    "payload": {"path": "MainFile.cs"},
                }
            ]
        },
        source_backend="claude",
        source_workflow="batch",
    )

    assert actions[0].risk_level == "low"
    assert actions[0].requires_approval is False


def test_service_rejects_invalid_plan_without_persisting_partial_requests():
    store = InMemoryApprovalStore()
    service = ApprovalService(store)

    bad_plan = {
        "actions": [
            {
                "kind": "write_file",
                "title": "Write card source",
                "reason": "Need the new card implementation",
                "payload": {"path": "Cards/TestCard.cs", "content": "class TestCard {}"},
            },
            {
                "title": "Broken action",
                "payload": {},
            },
        ]
    }

    try:
        service.create_requests_from_plan(
            bad_plan,
            source_backend="codex",
            source_workflow="single_asset",
        )
    except ValueError as exc:
        assert "kind" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid action plan")

    assert store.list_requests() == []
