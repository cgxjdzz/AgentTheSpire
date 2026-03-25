<p align="center">
  <img src="project_image/AgentTheSpire_icon.png" width="360" alt="AgentTheSpire" />
</p>

<h3 align="center">AI-powered mod generator for Slay the Spire 2</h3>
<h3 align="center">《杀戮尖塔 2》AI mod 生成器</h3>

---

## English

Describe your card, relic, or power in plain text — AgentTheSpire generates the C# code, creates the artwork, compiles the mod, and deploys it to your game automatically.

### Features

- **AI code generation** — Claude writes complete C# implementations from your description
- **AI image generation** — FLUX.2 / 即梦 / 通义万相 generate card art and relic icons, background removed and cropped automatically
- **One-click build & deploy** — `dotnet publish` + Godot PCK packaging, copied straight to your game's mods folder
- **Batch creation** — describe a full mod theme, AI plans and generates all assets in one go

### Requirements

| Tool | Version | Required |
|------|---------|----------|
| Python | 3.11+ | Yes |
| Node.js | 18+ | Yes |
| .NET SDK | 9.x | Yes |
| Godot Mono | **4.5.1 exactly** | Yes |
| Slay the Spire 2 | latest | Yes |
| Claude Code CLI | latest | One of two LLM options |
| LLM API Key | — | One of two LLM options |
| Image Gen API Key | — | Optional |

### Quick Start

```bash
git clone https://github.com/yourname/AgentTheSpire.git
cd AgentTheSpire

tools\install.bat           # Python deps + frontend build
tools\setup_mod_deps.bat    # .NET 9 + Godot 4.5.1

# Copy config.example.json → config.json, fill in your API keys and game path

tools\start.bat             # Opens http://localhost:7860
```

See [TUTORIAL.md](TUTORIAL.md) for full setup and configuration guide.

### LLM Options

| Mode | Provider |
|------|---------|
| `claude_subscription` | Claude Code CLI — best quality, requires Anthropic subscription |
| `api_key` | Anthropic / Moonshot (Kimi) / DeepSeek / Qwen / Zhipu |

### Image Generation Options

| Provider | Notes |
|----------|-------|
| `bfl` | FLUX.2 via Black Forest Labs API |
| `fal` | FLUX.2 via FAL.ai |
| `jimeng` | 即梦 via Volcengine — requires Access Key + Secret Key |
| `wanxiang` | 通义万相 via Aliyun |

---

## 中文

用自然语言描述你的卡牌、遗物、能力效果，AgentTheSpire 自动生成 C# 代码、生成配图、编译并部署到游戏。

### 功能

- **AI 写代码** — Claude 根据描述生成完整 C# 实现，编译报错自动修复
- **AI 生图** — FLUX.2 / 即梦 / 通义万相生成卡图/遗物图标，自动去背景裁剪
- **一键编译部署** — `dotnet publish` + Godot PCK 打包，自动复制到游戏 mods 目录
- **批量创建** — 描述整个 mod 主题，AI 规划并批量生成所有素材

### 快速开始

```bash
git clone https://github.com/yourname/AgentTheSpire.git
cd AgentTheSpire

tools\install.bat           # 安装 Python 依赖，构建前端
tools\setup_mod_deps.bat    # 安装 .NET 9 + Godot 4.5.1

# 复制 config.example.json → config.json，填入 API Key 和游戏路径

tools\start.bat             # 打开 http://localhost:7860
```

详细配置说明见 [TUTORIAL.md](TUTORIAL.md)。

---

## What it can do / 已验证场景

<p align="center">
  <img src="project_image/Neow_fire.png" width="340" alt="Neow: 开除速度一定要快" />
</p>

| # | Asset | Description | Difficulty |
|---|-------|-------------|------------|
| S01 | Attack Card | Fixed-cost single-target damage card with upgrade | ⭐ |
| S02 | Relic | Combat-start trigger relic (e.g. gain Block) | ⭐ |
| S03 | Power | Multi-turn buff that decrements each turn and auto-removes at 0 | ⭐⭐ |
| S04 | Card (X-cost) | X-energy AoE attack scaling with energy spent | ⭐⭐ |
| S05 | Relic (counter) | Counter relic with `ShowCounter` + reward at threshold | ⭐⭐ |
| S06 | Custom mechanic | Harmony patch with no image asset | ⭐⭐ |
| S07 | Batch (2 assets) | Card + Power with dependency ordering | ⭐⭐⭐ |
| S08 | Card (end-of-turn) | Card that triggers when held in hand at turn end | ⭐⭐⭐ |
| S09 | Full mini-mod | 5-asset mod — mixed types, batch image generation | ⭐⭐⭐⭐ |
| S10 | Full mod (complex) | 4-asset pack with three-level dependency chain | ⭐⭐⭐⭐⭐ |

---

## Project Structure

```
AgentTheSpire/
├── backend/          # Python FastAPI backend
│   ├── agents/       # Code Agent, Planner
│   ├── image/        # Image generation pipeline
│   ├── llm/          # Unified LLM streaming
│   └── routers/      # API routes
├── frontend/         # React + TypeScript UI
├── mod_template/     # C#/.NET Godot mod template
└── tools/            # Install/start helpers, decompiler, sandbox tests
```

## License

MIT






