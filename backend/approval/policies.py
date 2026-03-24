from __future__ import annotations

from approval.models import RiskLevel

_DEFAULT_RISK_BY_KIND: dict[str, RiskLevel] = {
    "read_file": "low",
    "write_file": "medium",
    "run_command": "high",
    "build_project": "high",
    "deploy_mod": "high",
}


def infer_risk_level(kind: str) -> RiskLevel:
    return _DEFAULT_RISK_BY_KIND.get(kind, "medium")


def should_require_approval(risk_level: RiskLevel) -> bool:
    return risk_level in {"medium", "high"}
