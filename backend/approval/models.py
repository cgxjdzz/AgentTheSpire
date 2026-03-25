from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

RiskLevel = Literal["low", "medium", "high"]
ApprovalStatus = Literal["pending", "approved", "rejected", "running", "succeeded", "failed"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ActionRequest:
    kind: str
    title: str
    reason: str
    payload: dict[str, Any]
    risk_level: RiskLevel
    requires_approval: bool
    source_backend: str
    source_workflow: str
    action_id: str = field(default_factory=lambda: uuid4().hex)
    status: ApprovalStatus = "pending"
    created_at: str = field(default_factory=_utc_now_iso)
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
