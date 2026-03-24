from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from approval.runtime import get_approval_executor, get_approval_store

router = APIRouter(prefix="/approvals")


@router.get("")
def list_approvals():
    store = get_approval_store()
    return [request.to_dict() for request in store.list_requests()]


@router.get("/{action_id}")
def get_approval(action_id: str):
    store = get_approval_store()
    try:
        return store.get_request(action_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval request not found") from exc


@router.post("/{action_id}/approve")
def approve_approval(action_id: str):
    store = get_approval_store()
    try:
        return store.approve_request(action_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval request not found") from exc


@router.post("/{action_id}/reject")
def reject_approval(action_id: str, body: dict):
    store = get_approval_store()
    try:
        return store.reject_request(action_id, body.get("reason", "")).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval request not found") from exc


@router.post("/{action_id}/execute")
def execute_approval(action_id: str):
    store = get_approval_store()
    executor = get_approval_executor()
    try:
        action = store.get_request(action_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval request not found") from exc

    if action.requires_approval and action.status != "approved":
        raise HTTPException(status_code=409, detail="Approval request must be approved before execution")

    try:
        store.mark_running(action_id)
        result = asyncio.run(executor.execute_action(action))
        updated = store.mark_succeeded(action_id, {
            "output": result.output,
            **result.metadata,
        })
        return updated.to_dict()
    except Exception as exc:
        updated = store.mark_failed(action_id, str(exc))
        return updated.to_dict()
