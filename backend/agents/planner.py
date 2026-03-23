"""
Mod Planner：将用户的自由文本需求解析为结构化的 Mod 计划。
使用与 prompt_adapter 相同的 LLM 路由（claude_subscription 或 litellm）。
"""
from __future__ import annotations

import json
import asyncio
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Literal

import litellm

from config import get_config
from agents.sts2_docs import get_planner_api_hints
from llm.text_runner import complete_text, resolve_model

AssetItemType = Literal["card", "card_fullscreen", "relic", "power", "character", "custom_code"]


@dataclass
class PlanItem:
    id: str                          # snake_case 唯一标识，如 "card_dark_ritual"
    type: AssetItemType
    name: str                        # PascalCase 英文名，如 "DarkRitual"
    name_zhs: str = ""               # 简体中文显示名，如 "暗黑仪式"
    description: str = ""            # 面向用户的中文描述
    implementation_notes: str = ""   # 技术实现说明（给 Code Agent 的）
    needs_image: bool = True
    image_description: str = ""      # 画什么（只有 needs_image=true 时有意义）
    depends_on: list[str] = field(default_factory=list)
    provided_image_b64: str = ""     # 用户上传的图片 base64（非空时跳过 AI 生图）

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ModPlan:
    mod_name: str
    summary: str
    items: list[PlanItem]

    def to_dict(self) -> dict:
        return {
            "mod_name": self.mod_name,
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
        }


# 类型是否需要图片
_NEEDS_IMAGE_TYPES: set[AssetItemType] = {"card", "card_fullscreen", "relic", "power", "character"}


def _build_planner_prompt(requirements: str) -> str:
    api_hints = get_planner_api_hints()
    return f"""You are an expert STS2 (Slay the Spire 2) mod developer and designer.
The user wants to create a Slay the Spire 2 mod. Analyze their requirements and produce a detailed, structured mod plan.

{api_hints}

User requirements:
{requirements}

Output a JSON object with this exact structure:
{{
  "mod_name": "EnglishModName",
  "summary": "一句话中文描述这个mod的主题",
  "items": [
    {{
      "id": "type_name_snake",
      "type": "card" | "card_fullscreen" | "relic" | "power" | "character" | "custom_code",
      "name": "PascalCaseEnglishName",
      "name_zhs": "简体中文显示名称",
      "description": "中文描述：这个资产是什么，玩法效果是什么",
      "implementation_notes": "Technical C# implementation guidance: which base class to inherit, key methods to override, fields to set, interactions with other items in this mod. Be specific and technical.",
      "needs_image": true | false,
      "image_description": "中文视觉描述：画面主体、外观风格、颜色、氛围（不含游戏机制数值）",
      "depends_on": ["id_of_item_this_depends_on"]
    }}
  ]
}}

Rules:
- type "custom_code": mechanics, buffs, passives, events, anything without a dedicated visual asset. needs_image = false.
- type "power": buff/debuff icons shown during battle. needs_image = true (needs a small icon).
- type "character": full player character. needs_image = true.
- For items with no visual asset (custom_code): image_description = "".
- depends_on: list IDs of items whose C# code must exist first (e.g. a card that uses a custom power depends on that power).
- implementation_notes must be detailed enough that a developer can write the C# without looking anything up. Include: base class, constructor params, methods to override, logic description, references to other items by their C# class name.
- name_zhs: the in-game display name for Simplified Chinese players. For custom_code items with no display name, use "".
- Create ONLY what the user asked for. Do not add extra items unless they are clearly implied by the requirements.
- Output ONLY the JSON, no markdown, no explanation.
- All string values must be valid JSON strings: escape double quotes as \\", backslashes as \\\\, newlines as \\n. Do NOT include raw newlines or unescaped quotes inside string values.
- implementation_notes must be a single JSON string (no embedded code blocks with triple backticks — use plain text descriptions instead).
"""


async def plan_mod(requirements: str) -> ModPlan:
    """将用户需求文本转换为结构化 ModPlan。"""
    cfg = get_config()
    llm_cfg = cfg["llm"]
    prompt = _build_planner_prompt(requirements)

    try:
        raw_json = await complete_text(prompt, llm_cfg)
        return _parse_plan(raw_json)
    except Exception as e:
        raise RuntimeError(f"规划失败: {type(e).__name__}: {e}") from e


async def _plan_via_litellm(prompt: str, llm_cfg: dict) -> str:
    provider = llm_cfg.get("provider", "anthropic")
    _model_map = {
        "anthropic": "claude-sonnet-4-6",
        "moonshot":  "moonshot/moonshot-v1-8k",
        "deepseek":  "deepseek/deepseek-chat",
        "qwen":      "openai/qwen-plus",
        "zhipu":     "zhipuai/glm-4-flash",
    }
    model = resolve_model({"provider": provider, **llm_cfg})
    response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        api_key=llm_cfg.get("api_key") or None,
        api_base=llm_cfg.get("base_url") or None,
        temperature=0.3,
        max_tokens=2048,
    )
    text = response.choices[0].message.content.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError(f"LLM 返回了无效 JSON: {text[:200]}")
    return text[start:end]


def _parse_plan(raw_json: str) -> ModPlan:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json
            data = json.loads(repair_json(raw_json))
        except Exception:
            raise
    items = []
    for it in data.get("items", []):
        item_type: AssetItemType = it.get("type", "custom_code")
        needs_image = it.get("needs_image", item_type in _NEEDS_IMAGE_TYPES)
        items.append(PlanItem(
            id=it["id"],
            type=item_type,
            name=it["name"],
            name_zhs=it.get("name_zhs", ""),
            description=it.get("description", ""),
            implementation_notes=it.get("implementation_notes", ""),
            needs_image=needs_image,
            image_description=it.get("image_description", ""),
            depends_on=it.get("depends_on", []),
        ))
    return ModPlan(
        mod_name=data.get("mod_name", "MyMod"),
        summary=data.get("summary", ""),
        items=items,
    )


def plan_from_dict(data: dict) -> ModPlan:
    """从前端返回的（可能经用户编辑过的）dict 重建 ModPlan。"""
    items = [
        PlanItem(
            id=it["id"],
            type=it["type"],
            name=it["name"],
            name_zhs=it.get("name_zhs", ""),
            description=it.get("description", ""),
            implementation_notes=it.get("implementation_notes", ""),
            needs_image=it.get("needs_image", True),
            image_description=it.get("image_description", ""),
            depends_on=it.get("depends_on", []),
            provided_image_b64=it.get("provided_image_b64", ""),
        )
        for it in data.get("items", [])
    ]
    return ModPlan(
        mod_name=data.get("mod_name", "MyMod"),
        summary=data.get("summary", ""),
        items=items,
    )


def find_groups(items: list[PlanItem]) -> list[list[PlanItem]]:
    """
    把有 depends_on 关系的资产聚合成组，共享一次 Code Agent 调用。
    无依赖关系的资产单独成组（size=1）。使用无向图连通分量算法。
    """
    id_to_item = {it.id: it for it in items}
    neighbors: dict[str, set[str]] = {it.id: set() for it in items}
    for it in items:
        for dep in it.depends_on:
            if dep in id_to_item:
                neighbors[it.id].add(dep)
                neighbors[dep].add(it.id)

    visited: set[str] = set()
    groups: list[list[PlanItem]] = []
    for it in items:
        if it.id in visited:
            continue
        group_ids: list[str] = []
        queue = [it.id]
        while queue:
            curr = queue.pop()
            if curr in visited:
                continue
            visited.add(curr)
            group_ids.append(curr)
            queue.extend(neighbors[curr] - visited)
        # 组内保持拓扑顺序（被依赖的先）
        ordered = topological_sort([id_to_item[i] for i in group_ids if i in id_to_item])
        groups.append(ordered)
    return groups


def topological_sort(items: list[PlanItem]) -> list[PlanItem]:
    """拓扑排序：依赖靠前，被依赖的先执行。依赖不存在时忽略（容错）。"""
    id_map = {item.id: item for item in items}
    visited: set[str] = set()
    result: list[PlanItem] = []

    def visit(item_id: str):
        if item_id in visited or item_id not in id_map:
            return
        visited.add(item_id)
        for dep in id_map[item_id].depends_on:
            visit(dep)
        result.append(id_map[item_id])

    for item in items:
        visit(item.id)
    return result
