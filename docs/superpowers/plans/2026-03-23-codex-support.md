# Codex Support Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏现有 Claude 工作流的前提下，为 AgentTheSpire 增加 Codex 支持，并把当前“Claude 写死”改造成可扩展的多后端 LLM/Agent 接入结构。

**Architecture:** 采用“双通道抽象”方案：一条是 Agent CLI 通道，供代码生成/构建修复类任务使用；另一条是文本 LLM 通道，供规划、分析和 Prompt 适配使用。保持现有业务流程不变，只把底层“调用谁”从写死的 `claude` 提升为可配置后端，并通过配置归一化兼容现有 `claude_subscription` / `api_key` 配置。

**Tech Stack:** FastAPI, React, WebSocket, subprocess CLI integration, pytest, LiteLLM, Claude CLI, Codex CLI（默认假设）/ OpenAI API（可替代实现）

---

## Assumption

本计划默认“Codex”指本机可调用的 **Codex CLI**，接入方式与当前 Claude CLI 类似。

如果实际目标是“OpenAI API 中的 Codex/Responses 模型”，则保留本计划整体结构，但把“Codex CLI 适配器”替换为“OpenAI Responses API 适配器”；其它任务拆分和文件边界保持不变。

## File Map

### Existing files to modify

- `backend/config.py`
  归一化 LLM 配置结构，兼容旧值并暴露新字段。
- `config.example.json`
  提供 Codex/Claude 两种配置样例。
- `backend/agents/code_agent.py`
  从“直接调用 Claude CLI”改为“调用统一 Agent Runner”。
- `backend/agents/planner.py`
  规划逻辑改为通过统一文本 LLM 解析层选择 Claude / Codex 兼容路径。
- `backend/image/prompt_adapter.py`
  Prompt 适配从“Claude CLI 或 LiteLLM”提升为统一文本 LLM 调度。
- `backend/llm/stream.py`
  分析流式逻辑接入统一文本 LLM 通道。
- `frontend/src/components/SettingsPanel.tsx`
  调整配置表单，支持选择 `agent_backend=claude|codex`，并统一模式枚举。
- `tools/install.bat`
  安装检查提示不再只写 Claude。
- `tools/install.sh`
  安装检查提示不再只写 Claude。
- `README.md`
  补充 Codex 支持说明和配置方式。
- `TUTORIAL.md`
  补充 Codex 安装、切换、验证说明。

### New files to create

- `backend/llm/agent_runner.py`
  统一代码代理入口，对外暴露 `run_agent_task(...)`。
- `backend/llm/agent_backends/__init__.py`
  Agent CLI 后端注册入口。
- `backend/llm/agent_backends/claude_cli.py`
  Claude CLI 适配器，从 `code_agent.py` 中拆出。
- `backend/llm/agent_backends/codex_cli.py`
  Codex CLI 适配器，负责命令拼装、输出解析、错误包装。
- `backend/llm/text_runner.py`
  统一文本 LLM 入口，供 planner / analysis / prompt adapter 共用。
- `backend/tests/test_llm_config_normalization.py`
  配置兼容与归一化测试。
- `backend/tests/test_agent_runner_selection.py`
  Agent Runner 选择后端的测试。
- `backend/tests/test_text_runner_selection.py`
  文本 LLM Runner 路由选择测试。

### Optional follow-up files

- `backend/tests/test_prompt_adapter_backends.py`
  如果 prompt adapter 拆分后逻辑较多，补独立测试。
- `backend/tests/test_settings_payload_contract.py`
  如果前后端配置契约继续复杂化，增加契约测试。

---

## Chunk 1: 配置契约统一

### Task 1: 定义新的 LLM 配置结构并保留兼容层

**Files:**
- Modify: `backend/config.py`
- Modify: `config.example.json`
- Test: `backend/tests/test_llm_config_normalization.py`

- [ ] **Step 1: 写失败测试，覆盖旧配置到新配置的兼容归一化**

```python
def test_normalize_legacy_claude_subscription_config():
    raw = {"llm": {"mode": "claude_subscription"}}
    cfg = normalize_llm_config(raw)
    assert cfg["llm"]["mode"] == "agent_cli"
    assert cfg["llm"]["agent_backend"] == "claude"

def test_normalize_legacy_api_key_config():
    raw = {"llm": {"mode": "api_key", "provider": "anthropic"}}
    cfg = normalize_llm_config(raw)
    assert cfg["llm"]["mode"] == "api"
    assert cfg["llm"]["provider"] == "anthropic"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest .\backend\tests\test_llm_config_normalization.py -v`
Expected: FAIL，提示 `normalize_llm_config` 未定义或行为不符。

- [ ] **Step 3: 在 `backend/config.py` 增加统一配置模型**

建议目标结构：

```json
"llm": {
  "mode": "agent_cli" | "api",
  "agent_backend": "claude" | "codex",
  "provider": "anthropic" | "openai" | "moonshot" | "deepseek" | "qwen" | "zhipu",
  "model": "",
  "api_key": "",
  "base_url": ""
}
```

兼容规则：

- `claude_subscription` -> `mode=agent_cli`, `agent_backend=claude`
- `api_key` -> `mode=api`
- 未设置 `provider` 时保留原默认值
- 旧配置读取后立刻归一化到内存，但不要强制重写用户文件，除非用户保存设置

- [ ] **Step 4: 更新 `config.example.json`**

至少给出两份可复制示例：

- Claude CLI 模式
- Codex CLI 模式

并保留一份 API 模式示例（OpenAI/Anthropic 兼容）

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest .\backend\tests\test_llm_config_normalization.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/config.py config.example.json backend/tests/test_llm_config_normalization.py
git commit -m "refactor: normalize llm config for multi-backend support"
```

---

## Chunk 2: Agent CLI 抽象层

### Task 2: 把 Claude CLI 运行逻辑从 `code_agent.py` 拆出为独立后端

**Files:**
- Create: `backend/llm/agent_backends/__init__.py`
- Create: `backend/llm/agent_backends/claude_cli.py`
- Create: `backend/llm/agent_runner.py`
- Modify: `backend/agents/code_agent.py`
- Test: `backend/tests/test_agent_runner_selection.py`

- [ ] **Step 1: 写失败测试，验证 Agent Runner 会按配置选后端**

```python
def test_agent_runner_selects_claude_backend(monkeypatch):
    cfg = {"llm": {"mode": "agent_cli", "agent_backend": "claude"}}
    assert resolve_agent_backend(cfg["llm"]) == "claude"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest .\backend\tests\test_agent_runner_selection.py -v`
Expected: FAIL

- [ ] **Step 3: 新建 `agent_runner.py`**

对外只暴露一套接口：

```python
async def run_agent_task(prompt: str, project_root: Path, stream_callback=None) -> str:
    ...
```

内部职责：

- 读取归一化后的 `llm` 配置
- 分派到 `claude_cli.py` 或 `codex_cli.py`
- 统一异常格式，避免上层逻辑感知具体 CLI 实现

- [ ] **Step 4: 从 `code_agent.py` 抽出 Claude 专属实现**

将下面这些职责迁到 `claude_cli.py`：

- `subprocess.Popen(...)`
- `stream-json` 解析
- `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` 环境变量设置
- 输出文本提取

保留 `code_agent.py` 里的高层任务函数不变，只把 `run_claude_code(...)` 替换为 `run_agent_task(...)`

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest .\backend\tests\test_agent_runner_selection.py -v`
Expected: PASS

- [ ] **Step 6: 针对 `code_agent.py` 相关测试或最小导入检查**

Run: `pytest .\backend\tests\test_docs.py .\backend\tests\test_planner.py -v`
Expected: 现有测试不因导入变更而失败

- [ ] **Step 7: Commit**

```bash
git add backend/llm/agent_backends backend/llm/agent_runner.py backend/agents/code_agent.py backend/tests/test_agent_runner_selection.py
git commit -m "refactor: extract agent cli runner from code agent"
```

---

## Chunk 3: 新增 Codex CLI 适配器

### Task 3: 增加 `codex_cli.py`，实现与 Claude 并列的代码代理后端

**Files:**
- Create: `backend/llm/agent_backends/codex_cli.py`
- Modify: `backend/llm/agent_backends/__init__.py`
- Modify: `backend/llm/agent_runner.py`
- Test: `backend/tests/test_agent_runner_selection.py`

- [ ] **Step 1: 先写失败测试，验证 `agent_backend=codex` 能路由到 Codex 后端**

```python
def test_agent_runner_selects_codex_backend():
    cfg = {"llm": {"mode": "agent_cli", "agent_backend": "codex"}}
    assert resolve_agent_backend(cfg["llm"]) == "codex"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest .\backend\tests\test_agent_runner_selection.py -v`
Expected: FAIL

- [ ] **Step 3: 先把 Codex CLI 行为封装成单文件适配器**

适配器必须独立承担：

- CLI 命令行拼装
- 环境变量注入
- 标准输出/错误读取
- 文本流解析
- 返回码错误包装

不要把 Codex 特判继续堆回 `code_agent.py`

- [ ] **Step 4: 在实现前确认 CLI 契约**

实现前必须先核实本机/目标环境中 Codex CLI 的：

- 可执行名（例如 `codex`）
- 是否支持非交互 prompt 参数
- 是否支持 JSON/流式输出
- 认证方式（环境变量或本地登录态）

如果 Codex CLI 无法提供流式 JSON，就对齐 `llm/stream.py` 的做法：先收全量文本，再分片模拟流式输出。

- [ ] **Step 5: 把 `agent_runner.py` 接到 Codex 后端**

要求：

- `mode=agent_cli && agent_backend=codex` 时走 `codex_cli.py`
- 未安装 Codex CLI 时抛出清晰错误，例如：
  `未找到 Codex CLI，请先安装并完成登录`

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest .\backend\tests\test_agent_runner_selection.py -v`
Expected: PASS

- [ ] **Step 7: 做一次最小人工烟测（只验证 runner，不跑完整业务）**

Run: 设计一个针对 `run_agent_task()` 的最小 mock / fake CLI 测试或本地脚本验证
Expected: Claude 与 Codex 两种后端都能返回统一文本结果

- [ ] **Step 8: Commit**

```bash
git add backend/llm/agent_backends backend/llm/agent_runner.py backend/tests/test_agent_runner_selection.py
git commit -m "feat: add codex cli backend for agent tasks"
```

---

## Chunk 4: 文本 LLM 抽象层

### Task 4: 统一 planner / analysis / prompt adapter 的文本 LLM 调用

**Files:**
- Create: `backend/llm/text_runner.py`
- Modify: `backend/llm/stream.py`
- Modify: `backend/agents/planner.py`
- Modify: `backend/image/prompt_adapter.py`
- Test: `backend/tests/test_text_runner_selection.py`

- [ ] **Step 1: 写失败测试，验证文本任务路由策略**

```python
def test_text_runner_uses_cli_when_mode_is_agent_cli():
    llm_cfg = {"mode": "agent_cli", "agent_backend": "codex"}
    assert resolve_text_backend(llm_cfg) == "codex_cli_fallback"

def test_text_runner_uses_api_when_mode_is_api():
    llm_cfg = {"mode": "api", "provider": "openai"}
    assert resolve_text_backend(llm_cfg) == "litellm"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest .\backend\tests\test_text_runner_selection.py -v`
Expected: FAIL

- [ ] **Step 3: 新建 `text_runner.py`**

建议对外提供两个入口：

```python
async def complete_text(prompt: str, llm_cfg: dict) -> str: ...
async def stream_text(system_prompt: str, user_prompt: str, llm_cfg: dict, on_chunk) -> str: ...
```

策略建议：

- `mode=api`：走 LiteLLM
- `mode=agent_cli && agent_backend=claude`：保留现有 Claude CLI 兼容路径
- `mode=agent_cli && agent_backend=codex`：若 Codex CLI 不支持可靠流式结构化输出，则先用全量文本，再模拟流式

- [ ] **Step 4: 改造 `planner.py`**

去掉 `_plan_via_claude_cli()` 的专属入口，把它接到 `text_runner.complete_text()`

- [ ] **Step 5: 改造 `prompt_adapter.py`**

去掉 `_adapt_via_claude_cli()` 的业务暴露入口，把它接到统一文本 runner

- [ ] **Step 6: 改造 `llm/stream.py`**

当前 `stream_analysis()` 也应接到统一文本 runner，避免未来再次出现“分析支持 Claude，但代码生成支持 Codex”的割裂状态

- [ ] **Step 7: 运行测试确认通过**

Run: `pytest .\backend\tests\test_text_runner_selection.py .\backend\tests\test_planner.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/llm/text_runner.py backend/llm/stream.py backend/agents/planner.py backend/image/prompt_adapter.py backend/tests/test_text_runner_selection.py
git commit -m "refactor: unify text llm routing for multi-backend support"
```

---

## Chunk 5: 前端设置与契约对齐

### Task 5: 调整设置页，让用户可显式选择 Claude / Codex

**Files:**
- Modify: `frontend/src/components/SettingsPanel.tsx`
- Modify: `config.example.json`
- Test: `backend/tests/test_llm_config_normalization.py`

- [ ] **Step 1: 先写契约测试，覆盖前端提交值与后端兼容值**

```python
def test_frontend_agent_cli_codex_payload_is_accepted():
    payload = {"llm": {"mode": "agent_cli", "agent_backend": "codex"}}
    cfg = normalize_llm_config(payload)
    assert cfg["llm"]["agent_backend"] == "codex"
```

- [ ] **Step 2: 运行测试确认失败或不完整**

Run: `pytest .\backend\tests\test_llm_config_normalization.py -v`
Expected: FAIL 或缺少对应覆盖

- [ ] **Step 3: 修改设置页 UI**

把当前：

- `claude_subscription`
- `api`
- `litellm`

改为更清晰的两层配置：

- 模式：`Agent CLI` / `API`
- Agent 后端：`Claude` / `Codex`（仅 CLI 模式显示）
- API 提供商：`Anthropic` / `OpenAI` / `Moonshot` / ...

目标是避免把“运行方式”和“提供商”混在一个枚举里。

- [ ] **Step 4: 保存时只发送归一化后的结构**

前端保存 payload 时不要再发旧值 `api` / `litellm`，而是统一发：

```json
"llm": {
  "mode": "agent_cli",
  "agent_backend": "codex"
}
```

或：

```json
"llm": {
  "mode": "api",
  "provider": "openai"
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest .\backend\tests\test_llm_config_normalization.py -v`
Expected: PASS

- [ ] **Step 6: 手工检查设置页最小行为**

Run: 启动前端，切换 Claude / Codex / API 三种配置组合
Expected: 表单显示逻辑正确，无旧枚举残留

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/SettingsPanel.tsx config.example.json backend/tests/test_llm_config_normalization.py
git commit -m "feat: add codex option to llm settings"
```

---

## Chunk 6: 安装脚本、文档与运行提示

### Task 6: 把“只支持 Claude”的安装提示和文档改为多后端说明

**Files:**
- Modify: `tools/install.bat`
- Modify: `tools/install.sh`
- Modify: `README.md`
- Modify: `TUTORIAL.md`

- [ ] **Step 1: 更新安装脚本提示**

把“检查 claude CLI”改为“检查已选择的 Agent CLI”或至少改为中性提示：

- Claude CLI 可选
- Codex CLI 可选
- API 模式可跳过 CLI 安装

- [ ] **Step 2: 更新 README**

明确写出：

- 支持的代码代理后端：Claude / Codex
- 支持的文本 API 模式
- 选择 Codex 时需要的安装/登录方式

- [ ] **Step 3: 更新 TUTORIAL**

补充：

- 如何切到 Codex
- 如何验证 Codex CLI 可用
- 常见失败场景（命令不存在、未登录、权限不足）

- [ ] **Step 4: 做最小文档一致性检查**

Run: `rg -n "只支持 Claude|claude_subscription|claude CLI|Codex" README.md TUTORIAL.md tools`
Expected: 文案不再暗示“只支持 Claude”

- [ ] **Step 5: Commit**

```bash
git add tools/install.bat tools/install.sh README.md TUTORIAL.md
git commit -m "docs: document codex support and setup flow"
```

---

## Chunk 7: 端到端验证

### Task 7: 验证 Claude 不回归、Codex 可用、API 模式仍工作

**Files:**
- Test: `backend/tests/test_llm_config_normalization.py`
- Test: `backend/tests/test_agent_runner_selection.py`
- Test: `backend/tests/test_text_runner_selection.py`
- Test: `backend/tests/test_planner.py`
- Test: `backend/tests/test_docs.py`

- [ ] **Step 1: 运行后端自动化测试**

Run: `pytest .\backend\tests -v`
Expected: PASS

- [ ] **Step 2: Claude CLI 冒烟**

配置：

```json
"llm": { "mode": "agent_cli", "agent_backend": "claude" }
```

Run: 单资产创建最小流程
Expected: 与当前行为一致，不回归

- [ ] **Step 3: Codex CLI 冒烟**

配置：

```json
"llm": { "mode": "agent_cli", "agent_backend": "codex" }
```

Run: 只做一个最小 `custom_code` 请求
Expected: 能收到 `agent_stream`，最终成功或至少返回清晰错误，不出现后端协议崩溃

- [ ] **Step 4: API 模式冒烟**

配置：

```json
"llm": { "mode": "api", "provider": "anthropic" | "openai" }
```

Run: 触发 planner 或 log analysis
Expected: 文本任务仍可运行

- [ ] **Step 5: 手工检查设置页保存后的配置文件**

Expected:

- 新配置字段正确写入
- 旧配置仍可读
- 脱敏显示正常

- [ ] **Step 6: Commit**

```bash
git add backend/tests
git commit -m "test: verify codex and claude multi-backend workflow"
```

---

## Notes for the Implementer

- 第一优先级不是“尽快跑通 Codex”，而是**先把 Claude 写死点抽象掉**。
- 不要把 `if backend == "codex"` 继续散落到 `code_agent.py`、`planner.py`、`prompt_adapter.py` 里。
- 配置迁移必须做兼容层，否则现有用户的 `config.json` 会直接失效。
- 如果 Codex CLI 不支持结构化流输出，允许在适配器内部做“全量输出 -> 分片模拟流式”，但这个兼容应只存在于适配器层。
- 如果确认 Codex CLI 不能稳定胜任文本分析任务，允许暂时做“Codex 仅用于 code agent；planner/prompt/analysis 继续走 API 模式”的阶段性落地，但必须在文档中明确这一限制。

---

Plan complete and saved to `docs/superpowers/plans/2026-03-23-codex-support.md`. Ready to execute?
