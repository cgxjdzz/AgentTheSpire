from __future__ import annotations

from approval.models import ActionRequest
from approval.policies import infer_risk_level, should_require_approval
from approval.store import InMemoryApprovalStore


class ApprovalService:
    def __init__(self, store: InMemoryApprovalStore):
        self.store = store

    def _build_request(
        self,
        raw_action: dict,
        *,
        source_backend: str,
        source_workflow: str,
    ) -> ActionRequest:
        if "kind" not in raw_action:
            raise ValueError("Action plan item is missing required field: kind")
        if "title" not in raw_action:
            raise ValueError("Action plan item is missing required field: title")

        kind = raw_action["kind"]
        risk_level = infer_risk_level(kind)
        return ActionRequest(
            kind=kind,
            title=raw_action["title"],
            reason=raw_action.get("reason", ""),
            payload=raw_action.get("payload", {}),
            risk_level=risk_level,
            requires_approval=should_require_approval(risk_level),
            source_backend=source_backend,
            source_workflow=source_workflow,
        )

    def create_requests_from_plan(
        self,
        plan: dict,
        *,
        source_backend: str,
        source_workflow: str,
    ) -> list[ActionRequest]:
        pending_requests = [
            self._build_request(
                raw_action,
                source_backend=source_backend,
                source_workflow=source_workflow,
            )
            for raw_action in plan.get("actions", [])
        ]

        created: list[ActionRequest] = []
        for action in pending_requests:
            created.append(self.store.create_request(action))

        return created
