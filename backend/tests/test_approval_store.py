"""Tests for approval request store lifecycle."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.models import ActionRequest
from approval.store import InMemoryApprovalStore


def _make_action(title: str = "Write file") -> ActionRequest:
    return ActionRequest(
        kind="write_file",
        title=title,
        reason="Need to update generated source",
        payload={"path": "Cards/TestCard.cs", "content": "class TestCard {}"},
        risk_level="medium",
        requires_approval=True,
        source_backend="claude",
        source_workflow="batch",
    )


def test_store_tracks_pending_and_approved_items():
    store = InMemoryApprovalStore()
    action = _make_action()

    created = store.create_request(action)
    assert store.get_request(created.action_id).status == "pending"
    assert len(store.list_requests()) == 1

    approved = store.approve_request(created.action_id)
    assert approved.status == "approved"
    assert store.get_request(created.action_id).status == "approved"


def test_store_tracks_running_and_terminal_states():
    store = InMemoryApprovalStore()
    action = store.create_request(_make_action("Run build"))

    store.approve_request(action.action_id)
    running = store.mark_running(action.action_id)
    assert running.status == "running"

    succeeded = store.mark_succeeded(action.action_id, {"exit_code": 0})
    assert succeeded.status == "succeeded"
    assert succeeded.result == {"exit_code": 0}


def test_store_can_reject_request_with_reason():
    store = InMemoryApprovalStore()
    action = store.create_request(_make_action("Delete file"))

    rejected = store.reject_request(action.action_id, "Too risky")
    assert rejected.status == "rejected"
    assert rejected.error == "Too risky"
