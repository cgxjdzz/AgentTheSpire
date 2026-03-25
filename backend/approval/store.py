from __future__ import annotations

from approval.models import ActionRequest


class InMemoryApprovalStore:
    def __init__(self):
        self._requests: dict[str, ActionRequest] = {}

    def create_request(self, action: ActionRequest) -> ActionRequest:
        self._requests[action.action_id] = action
        return action

    def list_requests(self) -> list[ActionRequest]:
        return list(self._requests.values())

    def get_request(self, action_id: str) -> ActionRequest:
        return self._requests[action_id]

    def approve_request(self, action_id: str) -> ActionRequest:
        action = self.get_request(action_id)
        action.status = "approved"
        action.error = None
        return action

    def reject_request(self, action_id: str, reason: str) -> ActionRequest:
        action = self.get_request(action_id)
        action.status = "rejected"
        action.error = reason
        return action

    def mark_running(self, action_id: str) -> ActionRequest:
        action = self.get_request(action_id)
        action.status = "running"
        return action

    def mark_succeeded(self, action_id: str, result: dict | None = None) -> ActionRequest:
        action = self.get_request(action_id)
        action.status = "succeeded"
        action.result = result or {}
        action.error = None
        return action

    def mark_failed(self, action_id: str, reason: str) -> ActionRequest:
        action = self.get_request(action_id)
        action.status = "failed"
        action.error = reason
        return action
