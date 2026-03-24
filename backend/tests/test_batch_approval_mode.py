"""Tests for batch approval-first helpers."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.runtime import reset_approval_runtime
from agents.planner import PlanItem
from routers import batch_workflow


@pytest.mark.asyncio
async def test_plan_group_approval_requests_creates_pending_actions(monkeypatch, tmp_path):
    reset_approval_runtime()

    group = [
        PlanItem(
            id="power_burn",
            type="power",
            name="BurnPower",
            description="一个灼烧 power",
            implementation_notes="实现 PowerModel",
            needs_image=False,
        ),
        PlanItem(
            id="card_ignite",
            type="card",
            name="IgniteCard",
            description="引用 BurnPower 的卡牌",
            implementation_notes="调用 BurnPower",
            needs_image=False,
            depends_on=["power_burn"],
        ),
    ]

    async def fake_complete_text(prompt: str, llm_cfg: dict, cwd: Path | None = None) -> str:
        assert "Output ONLY JSON" in prompt
        assert cwd == tmp_path
        return json.dumps(
            {
                "summary": "Need approval for this asset group",
                "actions": [
                    {
                        "kind": "write_file",
                        "title": "Write grouped source",
                        "reason": "Need generated files for the group",
                        "payload": {"path": "Cards/IgniteCard.cs"},
                    }
                ],
            }
        )

    monkeypatch.setattr(batch_workflow, "complete_text", fake_complete_text)

    summary, actions = await batch_workflow._plan_group_approval_requests(
        group,
        {"agent_backend": "codex", "execution_mode": "approval_first"},
        tmp_path,
    )

    assert summary == "Need approval for this asset group"
    assert len(actions) == 1
    assert actions[0].source_workflow == "batch"
    assert actions[0].status == "pending"


@pytest.mark.asyncio
async def test_send_item_approval_pending_emits_expected_event():
    class DummyWs:
        def __init__(self):
            self.messages: list[dict] = []

        async def send_text(self, text: str):
            self.messages.append(json.loads(text))

    ws = DummyWs()
    await batch_workflow._send_item_approval_pending(ws, "card_ignite", "Need approval", [])

    assert ws.messages[-1]["event"] == "item_approval_pending"
    assert ws.messages[-1]["item_id"] == "card_ignite"
    assert ws.messages[-1]["summary"] == "Need approval"
    assert ws.messages[-1]["requests"] == []
