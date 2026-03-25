"""
Code Agent：通过 subprocess 调用 Claude Code CLI。
负责生成/修改 C# 代码、dotnet build、错误修复、打包。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from config import get_config, get_decompiled_src_path
from agents.sts2_docs import get_docs_for_type, API_REF_PATH, BASELIB_SRC_PATH
from llm.agent_runner import run_agent_task


async def run_claude_code(prompt: str, project_root: Path, stream_callback=None) -> str:
    """兼容旧调用名，实际走统一 agent runner。"""
    return await run_agent_task(prompt, project_root, stream_callback)


# ── API lookup prompt 段落（根据配置动态生成）────────────────────────────────

def _build_api_lookup_section() -> str:
    """
    生成注入到 agent prompt 的 API 查找指引段落。
    - 若 decompiled_src_path 已配置：告知 agent 可直接 Read/Grep
    - 否则：告知用 ilspycmd（降级模式）
    BaseLib 反编译始终可用（在仓库内）。
    """
    baselib_note = (
        f"BaseLib (Alchyr.Sts2.BaseLib) decompiled source: `{BASELIB_SRC_PATH}`\n"
        "Read this file directly for CustomCardModel, CustomPotionModel, PlaceholderCharacterModel, etc.\n"
        "Do NOT curl GitHub for BaseLib — the local decompiled copy is authoritative."
    )

    decompiled_path = get_decompiled_src_path()
    if decompiled_path:
        sts2_note = (
            f"Full decompiled sts2.dll source: `{decompiled_path}` (Read/Grep directly).\n"
            "Key subdirs: `MegaCrit.Sts2.Core.Commands\\` (DamageCmd, PowerCmd, CreatureCmd…),\n"
            "`MegaCrit.Sts2.Core.Models.Cards\\` (StrikeIronclad etc.), `MegaCrit.Sts2.Core.Models\\`.\n"
            "Only fall back to ilspycmd if a specific class is missing from this directory."
        )
    else:
        sts2_note = (
            "sts2.dll decompiled source is NOT available on this machine.\n"
            "Use `ilspycmd <path_to_sts2.dll>` to look up specific classes when needed.\n"
            "Game DLL is typically at: `<STS2GamePath>/data_sts2_windows_x86_64/sts2.dll`"
        )

    return f"## API Lookup\n{baselib_note}\n\n{sts2_note}"


# ── 高层任务 ─────────────────────────────────────────────────────────────────

async def create_asset(
    design_description: str,
    asset_type: str,          # "card" | "relic" | "power" | "character"
    asset_name: str,
    image_paths: list[Path],  # 后处理后的图片路径列表
    project_root: Path,
    stream_callback=None,
    name_zhs: str = "",       # Simplified Chinese display name (optional)
    skip_build: bool = False, # True = skip dotnet publish (batch mode: build once at end)
) -> str:
    """
    让 Code Agent 为新资产生成完整 C# 代码。
    """
    img_list = "\n".join(f"  - {p}" for p in image_paths)
    docs = get_docs_for_type(asset_type)
    zhs_hint = f"\nSimplified Chinese display name (name_zhs): {name_zhs}" if name_zhs else ""
    api_lookup = _build_api_lookup_section()
    _build_note = (
        "NOTE: Godot headless export always exits with code -1, but if MSBuild reports '0 Error(s)' "
        "and the overall dotnet exit code is 0 — that is SUCCESS. Do NOT re-run just because of Godot's -1."
    )
    if skip_build:
        build_step = "6. Do NOT run dotnet publish — the build will be done later after all assets are created."
    else:
        build_step = (
            f"6. Run `dotnet publish` (NOT dotnet build) to compile AND export the Godot .pck file.\n"
            f"   {_build_note}\n"
            f"   Fix any actual compilation errors and re-run until it succeeds.\n"
            f"7. Confirm both the .dll and .pck were deployed to the mods folder."
        )
    prompt = f"""You are an expert STS2 (Slay the Spire 2) mod developer using Godot 4 + C# + BaseLib (Alchyr.Sts2.BaseLib).

{docs}

---

{api_lookup}

---

Task: Create a new {asset_type} named "{asset_name}".{zhs_hint}

Design description (Chinese):
{design_description}

Image assets already generated and placed at:
{img_list}

## Project already initialized
The project at `{project_root}` is already set up (copied from a working template).
- `MainFile.cs` — entry point (read it to confirm the exact namespace and ModId)
- `local.props` — already correct for this machine (do NOT recreate)
- `nuget.config` — already correct (do NOT recreate)
- `Extensions/StringExtensions.cs` — image path helpers, already present
- `{project_root.name}/` — Godot resource dir (named after the MOD, NOT the asset). Images and localization go here.

IMPORTANT: The Godot resource directory is `{project_root.name}/`, not `{asset_name}/`.
All image paths and res:// references must use `{project_root.name}` as the root.

DO NOT re-clone from GitHub. DO NOT recreate local.props or nuget.config.
Read MainFile.cs first to confirm the exact namespace and ModId.

Steps to complete:
1. Read `MainFile.cs` to confirm the namespace and ModId. Read `{asset_name}.csproj` to understand project structure.
2. If you are unsure of an exact API signature, method name, or base class, read `{API_REF_PATH}` before writing code.
3. Create the C# class file for this {asset_type} following BaseLib conventions (see reference above).
   CRITICAL rules for cards:
   - Cards MUST have [Pool(typeof(SomeCardPool))] attribute (e.g. ColorlessCardPool) — without it the game crashes on startup.
   - Do NOT create a Harmony patch to manually add cards to pools — BaseLib autoAdd handles this.
4. Create BOTH localization files:
   - `{project_root.name}/localization/eng/<type>s.json` — English
   - `{project_root.name}/localization/zhs/<type>s.json` — Simplified Chinese
5. Register it in MainFile.cs if needed (BaseLib handles most registration automatically).
{build_step}

Follow the existing code style in the project."""

    return await run_claude_code(prompt, project_root, stream_callback)


async def create_custom_code(
    description: str,
    implementation_notes: str,
    name: str,
    project_root: Path,
    stream_callback=None,
    skip_build: bool = False,
) -> str:
    """
    让 Code Agent 生成不需要图片的自定义代码（mechanic、power、event、passive 等）。
    """
    docs = get_docs_for_type("custom_code")
    api_lookup = _build_api_lookup_section()
    _build_note = (
        "NOTE: Godot headless export always exits with code -1, but if MSBuild reports '0 Error(s)' "
        "and the overall dotnet exit code is 0 — that is SUCCESS. Do NOT re-run just because of Godot's -1."
    )
    if skip_build:
        build_steps = "5. Do NOT run dotnet publish — the build will be done later after all assets are created."
    else:
        build_steps = (
            f"5. Run `dotnet publish` (NOT dotnet build). {_build_note}\n"
            f"   Fix any actual compilation errors and re-run until it succeeds.\n"
            f"6. Confirm the build succeeded and files deployed to mods folder."
        )
    mod_name = project_root.name
    prompt = f"""You are an expert STS2 (Slay the Spire 2) mod developer using Godot 4 + C# + BaseLib (Alchyr.Sts2.BaseLib).

{docs}

---

{api_lookup}

---

Task: Implement a custom code component named "{name}".

Design description:
{description}

Technical implementation notes:
{implementation_notes}

## Project already initialized
The project at `{project_root}` is already set up (copied from a working template).
- `MainFile.cs` — entry point with `harmony.PatchAll()` already wired up
- `local.props` and `nuget.config` — already correct, do NOT recreate
- `{mod_name}/` — Godot resource dir (named after the MOD: "{mod_name}")

DO NOT re-clone from GitHub. DO NOT recreate local.props or nuget.config.

Steps to complete:
1. Read `MainFile.cs` to confirm the namespace and ModId.
2. If you are unsure of an exact API signature, read `{API_REF_PATH}` before writing code.
3. Create the C# implementation file(s) following BaseLib/Harmony conventions.
4. `MainFile.cs` already calls `harmony.PatchAll()` — Harmony patches are auto-discovered, no manual registration needed.
{build_steps}

Do not create any image assets."""

    return await run_claude_code(prompt, project_root, stream_callback)


async def create_asset_group(
    assets: list[dict],   # [{"item": PlanItem, "image_paths": list[Path]}]
    project_root: Path,
    stream_callback=None,
) -> str:
    """
    一次 Code Agent 调用生成一组相互依赖的资产（卡牌+Power 等）。
    比分别调用更快，且可以在同一个 prompt 里正确处理跨资产引用。
    """
    from agents.planner import PlanItem

    # 收集组内所有涉及的类型，合并文档（去重 _COMMON_DOCS）
    seen_types: set[str] = set()
    type_docs_parts: list[str] = []
    common_included = False
    for a in assets:
        t = a["item"].type
        if t not in seen_types:
            seen_types.add(t)
            doc = get_docs_for_type(t)
            if not common_included:
                type_docs_parts.append(doc)   # 第一次包含 common
                common_included = True
            else:
                # 只追加 type-specific 部分（跳过 common）
                from agents.sts2_docs import _COMMON_DOCS
                type_docs_parts.append(doc[len(_COMMON_DOCS):])

    combined_docs = "\n\n".join(type_docs_parts)
    api_lookup = _build_api_lookup_section()

    # 每个资产的规格描述
    assets_section = ""
    class_names = [a["item"].name for a in assets]
    for i, a in enumerate(assets, 1):
        item: PlanItem = a["item"]
        img_paths: list[Path] = a["image_paths"]
        img_list = "\n".join(f"      - {p}" for p in img_paths) if img_paths else "      (no image — code-only asset)"
        zhs = f"\n  - Chinese name: {item.name_zhs}" if item.name_zhs else ""
        assets_section += f"""
### Asset {i}: [{item.type}] {item.name}{zhs}
  - Description: {item.description}
  - Implementation notes: {item.implementation_notes}
  - Image files:
{img_list}
  - Depends on: {', '.join(item.depends_on) if item.depends_on else 'none'}
"""

    mod_name = project_root.name
    prompt = f"""You are an expert STS2 (Slay the Spire 2) mod developer using Godot 4 + C# + BaseLib (Alchyr.Sts2.BaseLib).

{combined_docs}

---

{api_lookup}

---

## Task: Create {len(assets)} related assets in ONE batch

These assets are grouped because they depend on each other. Generate ALL of them in this single session.
Class names in this group: {', '.join(class_names)}

{assets_section}

## Project already initialized
The project at `{project_root}` is set up. Read `MainFile.cs` first to confirm namespace and ModId.
- `local.props` and `nuget.config` — already correct, do NOT recreate
- `Extensions/StringExtensions.cs` — image path helpers, already present
- `{mod_name}/` — Godot resource dir (named after the MOD: "{mod_name}"). All images and localization go here.

IMPORTANT: The Godot resource directory is `{mod_name}/`, NOT individual asset names.
All res:// paths must use `{mod_name}` as root.

DO NOT re-clone from GitHub. DO NOT recreate local.props or nuget.config.

## Steps

1. Read `MainFile.cs` to confirm the exact namespace and ModId.
2. For each asset in the group (in dependency order — dependencies first):
   a. Create the C# class file following BaseLib conventions.
   b. Create localization files (eng + zhs) under `<ModDir>/localization/`.
   When an asset references another asset in this group, use its exact class name from the list above.
3. After ALL assets are written, run `dotnet publish` ONCE (not once per asset).
4. Fix any compilation errors and re-run until it succeeds.
5. Confirm both .dll and .pck deployed to the mods folder.

Write all assets before running dotnet publish — do not build after each individual asset."""

    return await run_claude_code(prompt, project_root, stream_callback)


async def build_and_fix(
    project_root: Path,
    stream_callback=None,
    max_attempts: int = 3,
) -> tuple[bool, str]:
    """
    运行 dotnet build，自动修复错误，最多重试 max_attempts 次。
    返回 (success: bool, output: str)。
    """
    prompt = f"""Run `dotnet publish` in this STS2 mod project (this builds the DLL and exports the Godot .pck file).
If there are compilation errors, fix them and re-run dotnet publish.
Repeat until it succeeds or you've tried {max_attempts} times.
Report the final status clearly."""

    output = await run_claude_code(prompt, project_root, stream_callback)
    success = "Build succeeded" in output or "0 Error(s)" in output or "publish succeeded" in output.lower()
    return success, output


async def create_mod_project(
    project_name: str,
    target_dir: Path,
    stream_callback=None,
) -> Path:
    """
    从 ModTemplate 创建新 mod 项目。
    克隆模板并初始化项目名。
    返回新项目路径。
    """
    project_path = target_dir / project_name
    prompt = f"""Create a new STS2 mod project named "{project_name}" at {project_path}.

Steps:
1. Clone the ModTemplate from https://github.com/Alchyr/ModTemplate-StS2 into {project_path}
2. Rename the project: update .csproj file, ModEntry.cs class name, and any other references to the template name.
3. Check that `dotnet build` works (may fail without local.props, that's OK — just note it).
4. Report what was created and what the user needs to configure next (local.props paths)."""

    await run_claude_code(prompt, target_dir, stream_callback)
    return project_path


async def package_mod(
    project_root: Path,
    stream_callback=None,
) -> bool:
    """触发完整打包流程（dotnet build + Godot .pck 导出）。"""
    prompt = """Build and package this STS2 mod completely:
1. Run `dotnet build` with Release configuration.
2. Verify the .dll and .pck output files exist in the expected output directory.
3. Report the output file paths."""

    output = await run_claude_code(prompt, project_root, stream_callback)
    return "Build succeeded" in output or "0 Error(s)" in output
