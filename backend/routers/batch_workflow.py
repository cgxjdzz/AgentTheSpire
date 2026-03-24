"""
批量 Mod 工作流 API。
支持用户输入自由文本需求 → LLM 规划 → 批量创建多个资产。

并发模型：
- 图片生成：最多 2 个并发（image_gen_sem），等待图片选择时不阻塞其他 item
- 代码生成：串行（code_gen_lock）
- 依赖管理：item_done_events，被依赖的 item 完成后其他 item 才能继续
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import traceback as tb_module
from pathlib import Path

_log = logging.getLogger("batch")

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from approval.action_prompt import build_action_prompt
from approval.runtime import get_approval_service
from agents.code_agent import (
    build_and_fix,
    create_asset,
    create_asset_group,
    create_custom_code,
    create_mod_project,
)
from agents.planner import plan_mod, plan_from_dict, topological_sort, find_groups, PlanItem
from config import get_config
from image.generator import generate_images
from image.postprocess import process_image
from image.prompt_adapter import adapt_prompt, ImageProvider
from llm.text_runner import complete_text
from llm.stage_events import build_stage_event

router = APIRouter()

TRANSPARENT_TYPES = {"relic", "power"}


def _needs_transparent(asset_type: str) -> bool:
    return asset_type in TRANSPARENT_TYPES


def _img_provider_to_adapter(provider: str) -> ImageProvider:
    mapping = {"bfl": "flux2", "fal": "flux2", "volcengine": "jimeng", "wanxiang": "wanxiang"}
    return mapping.get(provider, "flux2")


async def _run_postprocess(img, asset_type, asset_name, project_root):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, process_image, img, asset_type, asset_name, project_root)


async def _send_item_approval_pending(ws: WebSocket, item_id: str, summary: str, requests: list):
    await ws.send_text(json.dumps({
        "event": "item_approval_pending",
        "item_id": item_id,
        "summary": summary,
        "requests": [request.to_dict() for request in requests],
    }))


async def _plan_group_approval_requests(group: list[PlanItem], llm_cfg: dict, project_root: Path):
    requirements = "\n".join(
        f"- [{item.type}] {item.name}: {item.description or item.implementation_notes}"
        for item in group
    )
    prompt = build_action_prompt(requirements)
    raw = await complete_text(prompt, llm_cfg, cwd=project_root)
    plan = json.loads(raw)
    summary = plan.get("summary", "This group requires approval before execution")
    actions = get_approval_service().create_requests_from_plan(
        plan,
        source_backend=llm_cfg.get("agent_backend", "unknown"),
        source_workflow="batch",
    )
    return summary, actions


# ── HTTP 端点：规划 ────────────────────────────────────────────────────────────

@router.post("/plan")
async def api_plan(body: dict):
    """接收用户需求文本，返回结构化 Mod 计划（JSON）。"""
    requirements: str = body.get("requirements", "")
    if not requirements.strip():
        return {"error": "requirements 不能为空"}
    plan = await plan_mod(requirements)
    return plan.to_dict()


# ── WebSocket：批量执行 ────────────────────────────────────────────────────────

@router.websocket("/ws/batch")
async def ws_batch(ws: WebSocket):
    """
    批量创建 Mod 资产的 WebSocket 端点。

    协议（客户端 → 服务端）：
      1. {"action":"start", "requirements":"...", "project_root":"..."}
      2. {"action":"confirm_plan", "plan": {...}}         # 用户审阅后确认（可编辑）
      3. {"action":"select_image", "item_id":"...", "index":0}
      4. {"action":"generate_more", "item_id":"...", "prompt":"..."}

    协议（服务端 → 客户端）：
      planning / plan_ready / batch_progress / batch_started /
      item_started / item_progress / item_image_ready / item_agent_stream /
      item_done / item_error / batch_done / error
    """
    await ws.accept()

    selection_futures: dict[str, asyncio.Future] = {}
    cfg = get_config()
    concurrency = int(cfg.get("image_gen", {}).get("concurrency", 1))
    image_gen_sem = asyncio.Semaphore(max(1, concurrency))
    code_gen_lock = asyncio.Lock()
    item_done_events: dict[str, asyncio.Event] = {}

    async def send(event: str, **data):
        await ws.send_text(json.dumps({"event": event, **data}))

    async def send_stage(scope: str, stage: str, message: str, item_id: str | None = None):
        payload = build_stage_event(scope, stage, message, item_id=item_id)
        if payload:
            await send("stage_update", **payload)

    try:
        # ── 1. 接收启动参数 ──────────────────────────────────────────────────
        raw = await ws.receive_text()
        params = json.loads(raw)
        action = params.get("action")

        project_root = Path(params["project_root"])
        cfg_loaded = get_config()
        img_provider = _img_provider_to_adapter(cfg_loaded["image_gen"]["provider"])

        if action == "start_with_plan":
            # 直接用已有 plan 执行，跳过规划阶段（恢复上次规划用）
            plan = plan_from_dict(params["plan"])
        else:
            assert action == "start", "期望 action=start 或 start_with_plan"
            requirements: str = params["requirements"]

            # ── 2. 规划 ──────────────────────────────────────────────────────
            await send_stage("text", "planning", "正在规划 Mod...")
            await send("planning")
            plan = await plan_mod(requirements)
            await send("plan_ready", plan=plan.to_dict())

            # ── 3. 等待用户确认计划 ───────────────────────────────────────────
            raw = await ws.receive_text()
            confirm = json.loads(raw)
            assert confirm.get("action") == "confirm_plan", "期望 action=confirm_plan"
            if confirm.get("plan"):
                plan = plan_from_dict(confirm["plan"])

        sorted_items = topological_sort(plan.items)
        groups = find_groups(sorted_items)          # 按依赖关系分组
        item_done_events = {item.id: asyncio.Event() for item in sorted_items}
        item_image_events: dict[str, asyncio.Event] = {item.id: asyncio.Event() for item in sorted_items}
        item_image_paths: dict[str, list[Path]] = {}
        error_ids: set[str] = set()

        # ── 4. 检查/初始化项目 ────────────────────────────────────────────────
        if not list(project_root.glob("*.csproj")):
            project_name = project_root.name
            parent_dir = project_root.parent
            await send_stage("project", "project_init", f"正在初始化项目 {project_name}...")
            await send("batch_progress", message=f"未检测到项目，正在创建 {project_name}...")

            async def _init_stream(chunk: str):
                await send("batch_progress", message=chunk)

            project_root = await create_mod_project(project_name, parent_dir, _init_stream)
            await send("batch_progress", message=f"项目创建完成: {project_root}")

        group_by_item = {
            item.id: group
            for group in groups
            for item in group
        }
        if any(len(g) > 1 for g in groups):
            multi = [g for g in groups if len(g) > 1]
            await send("batch_progress", message=f"发现 {len(multi)} 个依赖组，将合并生成代码（更快）")

        _log.info("batch_started: %d items, %d groups: %s",
                  len(sorted_items), len(groups),
                  [(it.id, it.type) for it in sorted_items])
        await send("batch_started", items=[it.to_dict() for it in sorted_items])

        # ── 5a. 图片阶段协程（每个 item 独立运行）────────────────────────────
        async def process_item_images(item: PlanItem):
            _log.info("[%s] image task started (needs_image=%s)", item.id, item.needs_image)
            await send("item_started", item_id=item.id, name=item.name, type=item.type)
            try:
                if item.needs_image:
                    if item.provided_image_b64:
                        await send("item_progress", item_id=item.id, message="使用用户提供的图片...")
                        from PIL import Image as PilImage
                        img_data = base64.b64decode(item.provided_image_b64)
                        selected_img = PilImage.open(io.BytesIO(img_data)).convert("RGBA")
                    else:
                        img_desc = item.image_description or item.description
                        async with image_gen_sem:
                            await send_stage("text", "prompt_adapting", "正在整理图像提示词...", item.id)
                            await send("item_progress", item_id=item.id, message="正在优化图像提示词...")
                            adapted = await adapt_prompt(
                                img_desc, item.type, img_provider,
                                needs_transparent_bg=_needs_transparent(item.type),
                            )
                        current_prompt = adapted["prompt"]
                        current_neg = adapted.get("negative_prompt")
                        all_images: list = []
                        while True:
                            async with image_gen_sem:
                                idx = len(all_images)
                                await send_stage("image", "image_generating", f"正在生成第 {idx + 1} 张图像...", item.id)
                                await send("item_progress", item_id=item.id, message=f"正在生成第 {idx + 1} 张图像...")
                                async def _img_progress(msg: str, _id=item.id):
                                    await send("item_progress", item_id=_id, message=msg)
                                for _attempt in range(3):
                                    try:
                                        [img] = await generate_images(
                                            current_prompt, item.type, current_neg,
                                            batch_size=1, progress_callback=_img_progress,
                                        )
                                        break
                                    except Exception as _e:
                                        if _attempt == 2:
                                            raise
                                        await send("item_progress", item_id=item.id, message=f"图像生成失败，重试 {_attempt+2}/3...")
                                        await asyncio.sleep(2)
                                all_images.append(img)
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            b64 = base64.b64encode(buf.getvalue()).decode()
                            await send("item_image_ready", item_id=item.id, image=b64, index=idx, prompt=current_prompt)
                            fut: asyncio.Future = asyncio.get_running_loop().create_future()
                            selection_futures[item.id] = fut
                            result = await fut
                            selection_futures.pop(item.id, None)
                            if result["action"] == "select":
                                selected_img = all_images[result["index"]]
                                break
                            if result.get("prompt"):
                                current_prompt = result["prompt"]
                            if result.get("negative_prompt") is not None:
                                current_neg = result["negative_prompt"]

                    await send_stage("image", "postprocess", "正在处理图像资产...", item.id)
                    await send("item_progress", item_id=item.id, message="正在处理图像资产...")
                    paths = await _run_postprocess(selected_img, item.type, item.name, project_root)
                    item_image_paths[item.id] = paths
                    await send("item_progress", item_id=item.id, message="图像资产处理完成，等待组内其他资产...")
                else:
                    item_image_paths[item.id] = []
            except Exception as e:
                try:
                    await send("item_error", item_id=item.id, message=str(e), traceback=tb_module.format_exc())
                except Exception:
                    pass
                error_ids.add(item.id)
            finally:
                item_image_events[item.id].set()

        # ── 5b. 代码阶段协程（按组合并，等所有图片就绪后统一生成）────────────
        async def process_group_code(group: list[PlanItem]):
            _log.info("[group %s] code task waiting for images", [it.id for it in group])
            # 等待组内所有图片就绪
            for item in group:
                await item_image_events[item.id].wait()
            _log.info("[group %s] all images ready, proceeding to code gen", [it.id for it in group])

            # 如果组内有失败的 item，跳过代码生成
            failed = [it.id for it in group if it.id in error_ids]
            if failed:
                for item in group:
                    if item.id not in error_ids:
                        await send("item_error", item_id=item.id,
                                   message=f"组内资产 {failed} 图片生成失败，跳过代码生成")
                        error_ids.add(item.id)
                        item_done_events[item.id].set()
                return

            async with code_gen_lock:
                # 向所有 item 发送代码生成开始的通知
                first_id = group[0].id
                for item in group:
                    await send_stage("agent", "agent_running", "正在生成代码...", item.id)
                    await send("item_progress", item_id=item.id, message="Code Agent 开始生成代码...")

                async def _stream(chunk: str):
                    await send("item_agent_stream", item_id=first_id, chunk=chunk)

                try:
                    if cfg_loaded["llm"].get("execution_mode") == "approval_first":
                        summary, actions = await _plan_group_approval_requests(group, cfg_loaded["llm"], project_root)
                        for item in group:
                            await _send_item_approval_pending(ws, item.id, summary, actions)
                        return

                    if len(group) == 1:
                        item = group[0]
                        if item.needs_image:
                            await create_asset(
                                item.description, item.type, item.name,
                                item_image_paths[item.id], project_root, _stream,
                                name_zhs=item.name_zhs,
                                skip_build=True,
                            )
                        else:
                            await create_custom_code(
                                item.description, item.implementation_notes,
                                item.name, project_root, _stream,
                                skip_build=True,
                            )
                    else:
                        # 多资产合并生成
                        assets_spec = [
                            {"item": it, "image_paths": item_image_paths.get(it.id, [])}
                            for it in group
                        ]
                        await create_asset_group(assets_spec, project_root, _stream)

                    for item in group:
                        await send("item_done", item_id=item.id, success=True)

                except Exception as e:
                    tb = tb_module.format_exc()
                    for item in group:
                        try:
                            await send("item_error", item_id=item.id, message=str(e), traceback=tb)
                        except Exception:
                            pass
                        error_ids.add(item.id)
                finally:
                    for item in group:
                        item_done_events[item.id].set()

        async def retry_group_for_item(item_id: str):
            group = group_by_item[item_id]
            retry_item = items_by_id[item_id]

            for item in group:
                error_ids.discard(item.id)
                item_done_events[item.id] = asyncio.Event()

            rerun_images = retry_item.needs_image and retry_item.id not in item_image_paths
            if rerun_images:
                item_image_events[retry_item.id] = asyncio.Event()
                tasks.append(asyncio.create_task(process_item_images(retry_item)))
            else:
                item_image_events.setdefault(retry_item.id, asyncio.Event()).set()

            tasks.append(asyncio.create_task(process_group_code(group)))

        # ── 6. 启动所有任务 ───────────────────────────────────────────────────
        items_by_id = {item.id: item for item in sorted_items}
        tasks = [asyncio.create_task(process_item_images(item)) for item in sorted_items]
        tasks += [asyncio.create_task(process_group_code(group)) for group in groups]

        # ── 7. 消息接收循环（路由 select/generate_more/retry_item 到对应 future）
        pending = set(item.id for item in sorted_items)
        while pending:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                msg = json.loads(raw)
                action = msg.get("action")
                item_id = msg.get("item_id")

                if action == "select_image" and item_id in selection_futures:
                    fut = selection_futures.get(item_id)
                    if fut and not fut.done():
                        fut.set_result({"action": "select", "index": msg["index"]})

                elif action == "generate_more" and item_id in selection_futures:
                    fut = selection_futures.get(item_id)
                    if fut and not fut.done():
                        fut.set_result({
                            "action": "generate_more",
                            "prompt": msg.get("prompt"),
                            "negative_prompt": msg.get("negative_prompt"),
                        })

                elif action == "retry_item" and item_id in items_by_id:
                    # 重置状态，重新跑该 item
                    pending.add(item_id)
                    await retry_group_for_item(item_id)

            except asyncio.TimeoutError:
                pass

            done_now = {item.id for item in sorted_items if item_done_events[item.id].is_set()}
            pending -= done_now

        # 等待所有 task 真正结束
        await asyncio.gather(*tasks)

        # ── 最终统一编译（所有资产代码写完后只编译一次）────────────────────────
        if len(error_ids) < len(sorted_items) and cfg_loaded["llm"].get("execution_mode") != "approval_first":
            await send_stage("build", "build_running", "正在统一编译与部署...")
            await send("batch_progress", message="所有资产代码生成完毕，开始统一编译...")
            async def _build_stream(chunk: str):
                await send("batch_progress", message=chunk)
            success, _ = await build_and_fix(project_root, _build_stream)
            if success:
                await send("batch_progress", message="✓ 编译成功，DLL 和 .pck 已部署")
            else:
                await send("batch_progress", message="⚠ 编译失败，请检查代码错误")

        await send("batch_done", success_count=len(sorted_items) - len(error_ids), error_count=len(error_ids))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await send("error", message=str(e), traceback=tb_module.format_exc())
        except Exception:
            pass
