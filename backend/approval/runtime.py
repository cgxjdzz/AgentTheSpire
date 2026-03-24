from __future__ import annotations

from pathlib import Path

from approval.executor import LocalApprovalExecutor
from approval.service import ApprovalService
from approval.store import InMemoryApprovalStore

_store: InMemoryApprovalStore | None = None
_service: ApprovalService | None = None
_executor: LocalApprovalExecutor | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_approval_store() -> InMemoryApprovalStore:
    global _store
    if _store is None:
        _store = InMemoryApprovalStore()
    return _store


def get_approval_service() -> ApprovalService:
    global _service
    if _service is None:
        _service = ApprovalService(get_approval_store())
    return _service


def get_approval_executor() -> LocalApprovalExecutor:
    global _executor
    if _executor is None:
        _executor = LocalApprovalExecutor(
            allowed_roots=[_repo_root()],
            allowed_commands=[],
        )
    return _executor


def reset_approval_runtime() -> None:
    global _store, _service, _executor
    _store = InMemoryApprovalStore()
    _service = ApprovalService(_store)
    _executor = LocalApprovalExecutor(
        allowed_roots=[_repo_root()],
        allowed_commands=[],
    )
