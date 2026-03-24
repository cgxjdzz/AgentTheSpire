from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from approval.models import ActionRequest


@dataclass
class ActionResult:
    success: bool
    output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ApprovalExecutor:
    async def execute_action(self, action: ActionRequest) -> ActionResult:
        raise NotImplementedError("ApprovalExecutor subclasses must implement execute_action")
