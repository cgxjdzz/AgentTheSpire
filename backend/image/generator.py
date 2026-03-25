"""
图像生成：调用各云端 API，支持 FLUX.2 / 即梦 / 通义万相。
返回图片字节流列表（每次 batch_size 张）。
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import threading
from typing import AsyncIterator

import httpx
from PIL import Image

from config import get_config

logger = logging.getLogger(__name__)

# ── FLUX.2 via BFL 官方 API ─────────────────────────────────────────────────

BFL_MODELS = {
    "flux.2-pro":   "flux_2/flux2_text_to_image",
    "flux.2-flex":  "flux_2/flux2_text_to_image",   # flex 通过 model 参数区分
    "flux.2-klein": "flux_2/flux2_text_to_image",
    "flux.2-max":   "flux_2/flux2_text_to_image",
    "flux.2-dev":   "flux_2/flux2_text_to_image",
    "flux.1.1-pro": "flux/flux_text_to_image",       # fallback
}

BFL_MODEL_IDS = {
    "flux.2-pro":   "flux.2-pro",
    "flux.2-flex":  "flux.2-flex",
    "flux.2-klein": "flux.2-klein",
    "flux.2-max":   "flux.2-max",
    "flux.2-dev":   "flux.2-dev",
    "flux.1.1-pro": "flux1.1-pro",
}

BFL_BASE = "https://api.bfl.ml/v1"


async def _generate_bfl(
    prompt: str,
    model: str,
    api_key: str,
    width: int,
    height: int,
    batch_size: int,
) -> list[Image.Image]:
    endpoint = BFL_MODELS.get(model, "flux_2/flux2_text_to_image")
    model_id = BFL_MODEL_IDS.get(model, "flux.2-pro")
    logger.info("[BFL] 提交 %d 张 model=%s %dx%d", batch_size, model_id, width, height)

    async with httpx.AsyncClient(timeout=120) as client:
        tasks = []
        for _ in range(batch_size):
            tasks.append(
                client.post(
                    f"{BFL_BASE}/{endpoint}",
                    headers={"x-key": api_key, "Content-Type": "application/json"},
                    json={
                        "prompt": prompt,
                        "model": model_id,
                        "width": width,
                        "height": height,
                        "output_format": "png",
                    },
                )
            )
        responses = await asyncio.gather(*tasks)

    images = []
    poll_tasks = []
    for resp in responses:
        resp.raise_for_status()
        task_id = resp.json()["id"]
        poll_tasks.append(_poll_bfl_result(task_id, api_key))

    results = await asyncio.gather(*poll_tasks)
    for url in results:
        async with httpx.AsyncClient(timeout=60) as client:
            img_resp = await client.get(url)
            images.append(Image.open(io.BytesIO(img_resp.content)))
    logger.info("[BFL] 下载完成，共 %d 张", len(images))
    return images


async def _poll_bfl_result(task_id: str, api_key: str, max_wait: int = 120) -> str:
    """轮询 BFL 任务，返回图片 URL。"""
    logger.debug("[BFL] 开始轮询 task_id=%s", task_id)
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(max_wait // 2):
            await asyncio.sleep(2)
            resp = await client.get(
                f"{BFL_BASE}/get_result",
                headers={"x-key": api_key},
                params={"id": task_id},
            )
            data = resp.json()
            if data.get("status") == "Ready":
                logger.debug("[BFL] task_id=%s Ready", task_id)
                return data["result"]["sample"]
            if data.get("status") in ("Error", "Failed"):
                logger.error("[BFL] task_id=%s 失败: %s", task_id, data)
                raise RuntimeError(f"BFL task failed: {data}")
    logger.error("[BFL] task_id=%s 超时 (max_wait=%ds)", task_id, max_wait)
    raise TimeoutError(f"BFL task {task_id} timed out")


# ── 火山引擎 Visual API (即梦 Seedream) ────────────────────────────────────
# 正确接口：https://visual.volcengineapi.com（非 Ark LLM 接口）
# 认证：AK/SK 签名（volcengine Python SDK 处理）
# 文档：https://www.volcengine.com/docs/86753

JIMENG_REQ_KEY = "high_aes_general_v30l_zt2i"

# 尺寸约束：512-2048，宽*高 ≤ 2048*2048
# 推荐 1.3K 分辨率
_JIMENG_ASPECT = {
    # (target_w, target_h): (jimeng_w, jimeng_h)
    "1:1":  (1328, 1328),
    "4:3":  (1472, 1104),
    "3:4":  (1104, 1472),
    "16:9": (1664, 936),
    "9:16": (936, 1664),
    "3:2":  (1584, 1056),
    "2:3":  (1056, 1584),
}


def _snap_jimeng_size(width: int, height: int) -> tuple[int, int]:
    """把目标宽高映射为最接近的即梦推荐分辨率（保持横竖比方向）。"""
    ratio = width / height
    best = min(_JIMENG_ASPECT.values(), key=lambda s: abs(s[0] / s[1] - ratio))
    return best


# VisualService 是单例且 __init__ 每次重置 credentials+session。
# 用锁保证每次调用时 init→set_ak→set_sk→API call 是原子的，避免竞态。
_jimeng_lock = threading.Lock()


def _run_jimeng_sync(ak: str, sk: str, body: dict) -> dict:
    """在线程中运行同步 volcengine SDK 调用。每次持锁完整执行，避免单例竞态。"""
    import requests as _requests
    from volcengine.visual.VisualService import VisualService
    with _jimeng_lock:
        svc = VisualService()
        # 每次刷新凭据和 session，避免过期连接和竞态导致的签名失败
        svc.set_ak(ak)
        svc.set_sk(sk)
        svc.session = _requests.Session()
        svc.set_connection_timeout(15)
        svc.set_socket_timeout(120)
        action = body.pop("_action")
        if action == "submit":
            return svc.cv_sync2async_submit_task(body)
        else:
            return svc.cv_sync2async_get_result(body)


async def _generate_volcengine(
    prompt: str,
    ak: str,
    sk: str,
    width: int,
    height: int,
    batch_size: int,
    progress_callback=None,
) -> list[Image.Image]:
    import json as _json
    loop = asyncio.get_running_loop()
    w, h = _snap_jimeng_size(width, height)
    logger.info("[即梦] 提交 %d 张 %dx%d (snap from %dx%d)", batch_size, w, h, width, height)

    async def _progress(msg: str):
        if progress_callback:
            await progress_callback(msg)

    # 完全串行：提交→等结果→下载→再提交下一张（免费版并发=1）
    images = []
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(batch_size):
            # 提交
            await _progress(f"正在提交第 {i+1} 张生成任务…")
            submit_body = {
                "_action": "submit",
                "req_key": JIMENG_REQ_KEY,
                "prompt": prompt,
                "width": w,
                "height": h,
                "seed": -1,
                "use_pre_llm": False,
            }
            res = await loop.run_in_executor(None, _run_jimeng_sync, ak, sk, submit_body)
            if res.get("code") != 10000:
                logger.error("[即梦] 第%d张提交失败: %s", i+1, res)
                raise RuntimeError(f"即梦提交任务失败 (第{i+1}张): {res}")
            task_id = res["data"]["task_id"]
            logger.info("[即梦] 第%d张 task_id=%s", i+1, task_id)

            # 轮询直到完成
            for attempt in range(60):
                await asyncio.sleep(3)
                elapsed = (attempt + 1) * 3
                await _progress(f"等待图像生成… 已等 {elapsed}s (task: {task_id[:8]}…)")
                query_body = {
                    "_action": "query",
                    "req_key": JIMENG_REQ_KEY,
                    "task_id": task_id,
                    "req_json": _json.dumps({"return_url": True}),
                }
                result = await loop.run_in_executor(None, _run_jimeng_sync, ak, sk, query_body)
                if result.get("code") != 10000:
                    raise RuntimeError(f"即梦查询失败 (第{i+1}张): {result}")
                data = result.get("data", {})
                status = data.get("status", "")
                if status in ("done", "success", 2, "2"):
                    await _progress(f"第 {i+1} 张生成完成，正在下载…")
                    logger.info("[即梦] 第%d张完成 task_id=%s", i+1, task_id)
                    urls = data.get("image_urls") or []
                    if not urls and data.get("binary_data_base64"):
                        for b64 in data["binary_data_base64"]:
                            images.append(Image.open(io.BytesIO(base64.b64decode(b64))))
                    else:
                        for url in urls:
                            resp = await client.get(url)
                            images.append(Image.open(io.BytesIO(resp.content)))
                    break
                if status in ("failed", "error", 3, "3"):
                    logger.error("[即梦] 第%d张任务失败 task_id=%s: %s", i+1, task_id, result)
                    raise RuntimeError(f"即梦任务失败 (第{i+1}张): {result}")
            else:
                logger.error("[即梦] 第%d张超时 task_id=%s", i+1, task_id)
                raise TimeoutError(f"即梦任务 {task_id} 超时 (第{i+1}张)")
    return images


# ── 通义万相 ─────────────────────────────────────────────────────────────────

async def _generate_wanxiang(
    prompt: str,
    api_key: str,
    width: int,
    height: int,
    batch_size: int,
) -> list[Image.Image]:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            },
            json={
                "model": "wanx2.1-t2i-turbo",
                "input": {"prompt": prompt},
                "parameters": {
                    "size": f"{width}*{height}",
                    "n": batch_size,
                    "prompt_extend": True,
                },
            },
        )
        resp.raise_for_status()
        task_id = resp.json()["output"]["task_id"]

    # 轮询结果
    async with httpx.AsyncClient(timeout=120) as client:
        for _ in range(60):
            await asyncio.sleep(3)
            result_resp = await client.get(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            result = result_resp.json()
            if result["output"]["task_status"] == "SUCCEEDED":
                urls = [item["url"] for item in result["output"]["results"]]
                break
            if result["output"]["task_status"] == "FAILED":
                raise RuntimeError(f"Wanxiang task failed: {result}")
        else:
            raise TimeoutError("Wanxiang task timed out")

    images = []
    async with httpx.AsyncClient(timeout=60) as client:
        for url in urls:
            img_resp = await client.get(url)
            images.append(Image.open(io.BytesIO(img_resp.content)))
    return images


# ── 本地 ComfyUI ─────────────────────────────────────────────────────────────

async def _generate_comfyui(
    prompt: str,
    comfyui_url: str,
    model: str,
    width: int,
    height: int,
    batch_size: int,
) -> list[Image.Image]:
    """通过 ComfyUI API 调用本地 FLUX.2 模型。"""
    workflow = _build_flux2_workflow(prompt, model, width, height, batch_size)
    async with httpx.AsyncClient(timeout=300) as client:
        # 提交 workflow
        resp = await client.post(f"{comfyui_url}/prompt", json={"prompt": workflow})
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        # 轮询完成
        for _ in range(150):
            await asyncio.sleep(2)
            hist = await client.get(f"{comfyui_url}/history/{prompt_id}")
            hist_data = hist.json()
            if prompt_id in hist_data and hist_data[prompt_id].get("status", {}).get("completed"):
                outputs = hist_data[prompt_id]["outputs"]
                break
        else:
            raise TimeoutError("ComfyUI task timed out")

    # 下载图片
    images = []
    for node_output in outputs.values():
        for img_info in node_output.get("images", []):
            async with httpx.AsyncClient(timeout=30) as client:
                img_resp = await client.get(
                    f"{comfyui_url}/view",
                    params={"filename": img_info["filename"], "subfolder": img_info.get("subfolder", ""), "type": img_info["type"]},
                )
                images.append(Image.open(io.BytesIO(img_resp.content)))
    return images


def _build_flux2_workflow(prompt: str, model: str, width: int, height: int, batch_size: int) -> dict:
    """构建 ComfyUI FLUX.2 workflow JSON。"""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": f"{model}.safetensors"}},
        "2": {"class_type": "CLIPTextEncode",          "inputs": {"clip": ["1", 1], "text": prompt}},
        "3": {"class_type": "EmptyLatentImage",        "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "4": {"class_type": "KSampler",                "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["2", 0],
            "latent_image": ["3", 0], "seed": 0, "steps": 20, "cfg": 3.5,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
        }},
        "5": {"class_type": "VAEDecode",       "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
        "6": {"class_type": "SaveImage",       "inputs": {"images": ["5", 0], "filename_prefix": "spireforge"}},
    }


# ── 公共入口 ─────────────────────────────────────────────────────────────────

async def generate_images(
    prompt: str,
    asset_type: str,
    negative_prompt: str | None = None,
    batch_size: int | None = None,
    progress_callback=None,
) -> list[Image.Image]:
    """
    根据 config 选择图生后端，返回 PIL Image 列表。
    asset_type 用于推断合适的生成尺寸。
    batch_size 可外部覆盖 config 默认值。
    """
    cfg = get_config()
    img_cfg = cfg["image_gen"]
    if batch_size is None:
        batch_size = img_cfg.get("batch_size", 3)
    width, height = _resolve_gen_size(asset_type)

    if img_cfg["mode"] == "local":
        return await _generate_comfyui(
            prompt,
            img_cfg["local"]["comfyui_url"],
            img_cfg["model"],
            width, height, batch_size,
        )

    provider = img_cfg["provider"]
    api_key = img_cfg["api_key"]

    if provider in ("bfl", "fal"):
        return await _generate_bfl(prompt, img_cfg["model"], api_key, width, height, batch_size)
    elif provider == "volcengine":
        api_secret = img_cfg.get("api_secret", "")
        return await _generate_volcengine(prompt, api_key, api_secret, width, height, batch_size, progress_callback)
    elif provider == "wanxiang":
        return await _generate_wanxiang(prompt, api_key, width, height, batch_size)
    else:
        raise ValueError(f"Unknown image provider: {provider}")


def _resolve_gen_size(asset_type: str) -> tuple[int, int]:
    """根据资产类型返回合适的生成分辨率（略大于最终尺寸）。"""
    sizes = {
        "card":            (1024, 800),
        "card_fullscreen": (640, 900),
        "relic":           (512, 512),
        "power":           (512, 512),
        "character":       (512, 760),
    }
    return sizes.get(asset_type, (512, 512))
