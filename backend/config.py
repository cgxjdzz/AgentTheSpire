import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Optional

# 环境变量名映射（用户级，通过 setx 写入，重启后生效）
_ENV_KEYS = {
    "llm.api_key":          "SPIREFORGE_LLM_KEY",
    "image_gen.api_key":    "SPIREFORGE_IMG_KEY",
    "image_gen.api_secret": "SPIREFORGE_IMG_SECRET",
}

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

DEFAULT_LLM_CONFIG = {
    "mode": "agent_cli",             # "agent_cli" | "api"
    "agent_backend": "claude",       # "claude" | "codex"
    "provider": "anthropic",         # "anthropic" | "openai" | "moonshot" | "deepseek" | "qwen" | "zhipu"
    "model": "",
    "api_key": "",
    "base_url": "",                  # 留空则使用各 provider 默认值
    "custom_prompt": "",             # 追加到全部 AI 调用的全局提示词
    "execution_mode": "legacy_direct",  # "legacy_direct" | "approval_first"
}

DEFAULT_CONFIG = {
    "llm": DEFAULT_LLM_CONFIG,
    "approval": {
        "auto_execute_low_risk": False,
        "allowed_commands": [],
        "allowed_roots": [],
    },
    "image_gen": {
        "mode": "cloud",                # "cloud" | "local"
        "provider": "bfl",             # "bfl" | "fal" | "jimeng" | "wanxiang"
        "model": "flux.2-flex",        # flux.2-pro | flux.2-flex | flux.2-klein | flux.1.1-pro
        "api_key": "",
        "api_secret": "",          # 火山引擎即梦专用：Secret Access Key
        "batch_size": 3,
        "concurrency": 1,              # 同时并发生图的最大数量（1=串行，推荐；API 限流时设低）
        "rembg_model": "birefnet-general",  # 背景去除模型：birefnet-general/birefnet-lite/u2net/isnet-general-use
        "local": {
            "comfyui_url": "http://127.0.0.1:8188",
            "installed": False,
            "model_path": "",
        }
    },
    "godot_exe_path": "",              # Godot 4.5.1 Mono exe 绝对路径（.pck 打包必须）
    "dotnet_path": "dotnet",           # dotnet CLI 路径，默认在 PATH 里
    "sts2_path": "",                   # STS2 游戏根目录，用于一键部署 mod
    "default_project_root": "",        # 新建 Mod 时的默认目录
    "mod_template_path": "",           # 自定义模板路径，留空使用仓库内 mod_template/
    "mod_projects": [],                 # 最近打开的 mod 项目路径列表
    "active_project": "",              # 当前激活的 mod 项目路径
    # sts2.dll 反编译输出目录（由用户运行 tools/decompile_sts2.py 生成）
    # 不在 git 中（22MB 版权内容）。留空时 agent 退化为 ilspycmd 查询。
    "decompiled_src_path": "",
}


def normalize_llm_config(llm_cfg: Optional[dict]) -> dict:
    cfg = _deep_merge(DEFAULT_LLM_CONFIG, llm_cfg or {})
    mode = cfg.get("mode", "agent_cli")

    if mode == "claude_subscription":
        cfg["mode"] = "agent_cli"
        cfg["agent_backend"] = "claude"
    elif mode in {"api_key", "api", "litellm"}:
        cfg["mode"] = "api"
    elif mode != "agent_cli":
        cfg["mode"] = "agent_cli"

    if cfg.get("agent_backend") not in {"claude", "codex"}:
        cfg["agent_backend"] = "claude"

    if not cfg.get("provider"):
        cfg["provider"] = DEFAULT_LLM_CONFIG["provider"]

    return cfg


def normalize_config(config: Optional[dict]) -> dict:
    cfg = _deep_merge(DEFAULT_CONFIG, config or {})
    cfg["llm"] = normalize_llm_config(cfg.get("llm"))
    return cfg


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        cfg = normalize_config(saved)
    else:
        cfg = normalize_config(None)
    # 环境变量覆盖（优先级最高，首次启动时也能读到之前保存的 key）
    # 跳过被脱敏的占位值（以 **** 开头），避免历史错误覆盖真实 key
    for dotpath, envname in _ENV_KEYS.items():
        val = os.environ.get(envname, "")
        if val and not val.startswith("****"):
            section, key = dotpath.split(".")
            cfg[section][key] = val
    return cfg


def save_config(config: dict) -> None:
    config = normalize_config(config)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    # 同步写入 Windows 用户环境变量（下次启动自动读取，无需重新输入）
    # 不保存脱敏占位值（以 **** 开头），避免污染环境变量
    for dotpath, envname in _ENV_KEYS.items():
        section, key = dotpath.split(".")
        val = config.get(section, {}).get(key, "")
        if val and not val.startswith("****"):
            os.environ[envname] = val  # 当前进程立即生效
            try:
                subprocess.run(["setx", envname, val], capture_output=True, check=False)
            except Exception:
                pass


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


# 全局单例，运行时使用
_config: Optional[dict] = None


def get_config() -> dict:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def update_config(patch: dict) -> dict:
    global _config
    cfg = get_config()
    _config = normalize_config(_deep_merge(cfg, patch))
    save_config(_config)
    return _config


def get_decompiled_src_path() -> Optional[str]:
    """
    返回 sts2.dll 反编译目录路径（若已配置且存在）。
    优先读 config.json 的 decompiled_src_path，
    其次检测环境变量 SPIREFORGE_DECOMPILED_SRC。
    返回 None 表示未配置，调用方应退化为 ilspycmd 查询。
    """
    # 环境变量覆盖（CI/Docker 场景下有用）
    env_val = os.environ.get("SPIREFORGE_DECOMPILED_SRC", "")
    if env_val and Path(env_val).is_dir():
        return env_val

    cfg_val = get_config().get("decompiled_src_path", "")
    if cfg_val and Path(cfg_val).is_dir():
        return cfg_val

    return None

