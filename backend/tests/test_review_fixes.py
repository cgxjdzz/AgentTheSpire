"""Regression tests for review findings fixed on 2026-03-24."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import code_agent
from routers import batch_workflow


@pytest.mark.asyncio
async def test_create_asset_prompt_uses_mod_localization_root(tmp_path, monkeypatch):
    captured: dict[str, str] = {}

    async def fake_run(prompt: str, project_root: Path, stream_callback=None) -> str:
        captured["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(code_agent, "run_claude_code", fake_run)

    project_root = tmp_path / "SampleMod"
    project_root.mkdir()

    await code_agent.create_asset(
        design_description="测试描述",
        asset_type="card",
        asset_name="DarkBlade",
        image_paths=[],
        project_root=project_root,
    )

    prompt = captured["prompt"]
    assert f"{project_root.name}/localization/eng/<type>s.json" in prompt
    assert f"{project_root.name}/localization/zhs/<type>s.json" in prompt
    assert "DarkBlade/localization/eng/<type>s.json" not in prompt
    assert "DarkBlade/localization/zhs/<type>s.json" not in prompt


def test_batch_workflow_imports_build_and_fix():
    assert callable(batch_workflow.build_and_fix)


def test_batch_workflow_retry_path_does_not_call_missing_process_item():
    source = Path(batch_workflow.__file__).read_text(encoding="utf-8")
    assert "process_item(" not in source
