"""Tests for single-asset approval-first workflow helpers."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from approval.runtime import reset_approval_runtime
from routers import workflow


@pytest.mark.asyncio
async def test_plan_approval_requests_creates_pending_actions(monkeypatch, tmp_path):
    reset_approval_runtime()

    async def fake_complete_text(prompt: str, llm_cfg: dict, cwd: Path | None = None) -> str:
        assert "Output ONLY JSON" in prompt
        assert cwd == tmp_path
        return json.dumps(
            {
                "summary": "Need approval before modifying project files",
                "actions": [
                    {
                        "kind": "write_file",
                        "title": "Write card source",
                        "reason": "Need generated implementation",
                        "payload": {"path": "Cards/TestCard.cs"},
                    }
                ],
            }
        )

    monkeypatch.setattr(workflow, "complete_text", fake_complete_text)

    llm_cfg = {"agent_backend": "codex", "execution_mode": "approval_first"}
    summary, actions = await workflow._plan_approval_requests(
        "描述一个遗物",
        llm_cfg,
        tmp_path,
    )

    assert summary == "Need approval before modifying project files"
    assert len(actions) == 1
    assert actions[0].kind == "write_file"
    assert actions[0].status == "pending"
    assert actions[0].source_workflow == "single_asset"


@pytest.mark.asyncio
async def test_send_approval_pending_emits_expected_event():
    class DummyWs:
        def __init__(self):
            self.messages: list[dict] = []

        async def send_text(self, text: str):
            self.messages.append(json.loads(text))

    ws = DummyWs()
    await workflow._send_approval_pending(ws, "Need approval", [])

    assert ws.messages[-1]["event"] == "approval_pending"
    assert ws.messages[-1]["summary"] == "Need approval"
    assert ws.messages[-1]["requests"] == []
