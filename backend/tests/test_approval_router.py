"""Tests for approval HTTP router."""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.models import ActionRequest
from approval.runtime import get_approval_store, get_approval_executor, reset_approval_runtime
from routers.approval_router import router


def _create_action() -> ActionRequest:
    return ActionRequest(
        kind="write_file",
        title="Write source",
        reason="Need generated file",
        payload={"path": "Cards/TestCard.cs"},
        risk_level="medium",
        requires_approval=True,
        source_backend="codex",
        source_workflow="single_asset",
    )


def test_approval_router_lists_and_updates_requests():
    reset_approval_runtime()
    store = get_approval_store()
    action = store.create_request(_create_action())

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    listed = client.get("/api/approvals")
    assert listed.status_code == 200
    assert listed.json()[0]["action_id"] == action.action_id

    fetched = client.get(f"/api/approvals/{action.action_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Write source"

    approved = client.post(f"/api/approvals/{action.action_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    rejected = client.post(f"/api/approvals/{action.action_id}/reject", json={"reason": "Not safe"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["error"] == "Not safe"


def test_approval_router_execute_runs_approved_action(tmp_path):
    reset_approval_runtime()
    store = get_approval_store()
    executor = get_approval_executor()
    executor.allowed_roots = [tmp_path]
    executor.allowed_commands = []

    action = store.create_request(_create_action())
    store.approve_request(action.action_id)
    action.payload = {"path": "Cards/TestCard.cs", "content": "class TestCard {}"}

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    executed = client.post(f"/api/approvals/{action.action_id}/execute")
    assert executed.status_code == 200
    assert executed.json()["status"] == "succeeded"
    assert (tmp_path / "Cards" / "TestCard.cs").exists()
