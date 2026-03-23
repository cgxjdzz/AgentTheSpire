# AgentTheSpire 使用教程

## 目录

1. [环境准备](#1-环境准备)
2. [安装](#2-安装)
3. [配置](#3-配置)
4. [创建第一个 Mod](#4-创建第一个-mod)
5. [工作流详解](#5-工作流详解)
6. [提升 AI 代码质量（可选）](#6-提升-ai-代码质量可选)
7. [常见问题](#7-常见问题)

---

## 1. 环境准备

安装以下工具后再继续：

### 必须安装

**Python 3.11+**
- 下载：https://www.python.org/downloads/
- 安装时勾选 **Add Python to PATH**

**Node.js 18+**
- 下载：https://nodejs.org/

**.NET 9 SDK**
- 下载：https://dotnet.microsoft.com/download/dotnet/9.0
- 或通过 `tools\setup_mod_deps.bat` 自动安装（见第 2 步）

**Godot 4.5.1 Mono**
- 必须是 **4.5.1** 版本，其他版本无法正确打包 .pck
- 或通过 `tools\setup_mod_deps.bat` 自动安装（见第 2 步）

### 选择 LLM（二选一）

**方案 A：Claude Code CLI（推荐，需要 Anthropic 订阅）**
```bash
npm install -g @anthropic-ai/claude-code
claude login   # 完成浏览器登录授权
```

**方案 B：API Key（Kimi/DeepSeek/通义/智谱等）**
- 注册对应平台账号获取 Key，在第 3 步填入

### 选择图生 API（可选）

不配置图生 API 也可以使用——创建 mod 时手动上传图片即可。

| Provider | 申请地址 | 说明 |
|----------|---------|------|
| BFL（FLUX.2） | https://api.bfl.ml | 需要信用卡，质量最好 |
| FAL（FLUX.2） | https://fal.ai | 按量计费 |
| 即梦（火山引擎） | https://console.volcengine.com | 国内，需要 Access Key + Secret Key |
| 通义万相 | https://dashscope.aliyun.com | 国内，阿里云账号 |

---

## 2. 安装

```bash
# 克隆仓库
git clone https://github.com/yourname/AgentTheSpire.git
cd AgentTheSpire
```

**第一步：安装 Python 依赖 + 构建前端**
```
tools\install.bat
```
完成后会提示是否安装本地 ComfyUI（12GB 磁盘），一般选 N 跳过。

**第二步：安装 mod 编译工具**
```
tools\setup_mod_deps.bat
```
自动完成：
- 检测并安装 .NET 9 SDK（通过 winget）
- 下载 Godot 4.5.1 Mono（~130MB）并解压到 `godot/` 目录
- 将 Godot 路径写入 `config.json`

> Linux/macOS 用户：使用 `./tools/install.sh` 和 `./tools/setup_mod_deps.sh`

---

## 3. 配置

复制配置模板：
```bash
cp config.example.json config.json
```

用文本编辑器打开 `config.json`，按需填写：

### LLM 配置

**方案 A：Claude 订阅（已完成 `claude login`）**
```json
"llm": {
  "mode": "claude_subscription"
}
```

**方案 B：API Key**
```json
"llm": {
  "mode": "api_key",
  "provider": "moonshot",
  "api_key": "sk-xxxxxxxx"
}
```
`provider` 可选值：`anthropic` / `moonshot` / `deepseek` / `qwen` / `zhipu`

### 图生配置

**FLUX.2（BFL）**
```json
"image_gen": {
  "mode": "cloud",
  "provider": "bfl",
  "model": "flux.2-flex",
  "api_key": "your-bfl-key"
}
```

**即梦（火山引擎）**
```json
"image_gen": {
  "mode": "cloud",
  "provider": "jimeng",
  "model": "doubao-seedream-3-0-t2i-250415",
  "api_key": "your-access-key-id",
  "api_secret": "your-secret-access-key"
}
```

### 游戏路径

```json
"sts2_path": "C:/Steam/steamapps/common/Slay the Spire 2",
"default_project_root": "C:/STS2Mods"
```

`default_project_root` 是新建 mod 项目的默认存放目录，提前创建好该文件夹。

---

## 4. 创建第一个 Mod

**启动**
```
tools\start.bat
```
浏览器自动打开 `http://localhost:7860`。

**第一次使用：新建 Mod 项目**

1. 点击 **新建 Mod**
2. 填写 Mod 名称（英文，无空格，例如 `MyFirstMod`）
3. 点击确认，工具自动从模板复制项目结构

**创建一张卡牌**

1. 选择目标 mod 项目
2. 点击 **创建素材**，选择类型 **卡牌**
3. 填写：
   - **名称**：英文类名，如 `FrostBlade`
   - **描述**：中文描述效果，如"造成 8 点伤害，若手牌中有技能牌则多造成 4 点伤害"
4. 点击生成
5. AI 自动：
   - 调用图生 API 生成 3 张候选卡图
   - 你从中选一张（或跳过使用默认图）
   - Code Agent 生成 C# 代码
   - 自动编译，如有报错自动修复
6. 完成后点击 **编译部署**，mod 自动复制到游戏 mods 目录

**在游戏中测试**

启动 STS2，进入 mod 列表，启用你的 mod，开始一局新游戏验证效果。

---

## 5. 工作流详解

### 批量创建（推荐）

适合一次性创建整套 mod 内容：

1. 点击 **批量规划**
2. 用自然语言描述你的 mod 主题，例如：
   > "一个冰霜法师角色，有 5 张攻击卡（造成伤害+施加冻结）、3 张技能（产生防御/加速）、2 件遗物（强化冻结效果）"
3. AI 自动生成规划，列出所有素材清单
4. 确认规划后，批量生成所有素材

### 修改已有代码

1. 在项目面板选择已有素材
2. 点击 **重新生成** 或直接描述改动
3. Code Agent 读取现有代码后按要求修改
4. 自动重新编译

### 部署方式

`dotnet publish` 完成后自动复制到：
```
<sts2_path>/mods/<ModName>/
    <ModName>.dll
    <ModName>.pck
```
游戏同时需要这两个文件才能加载 mod。

---

## 6. 提升 AI 代码质量（可选）

默认情况下，Code Agent 通过内置的 API 参考文档生成代码。
反编译游戏 DLL 后，AI 可以直接查阅原始实现，显著减少错误。

```bash
python tools/decompile_sts2.py --game-path "C:/Steam/steamapps/common/Slay the Spire 2"
```

完成后会在仓库外自动创建 `sts2_decompiled/` 目录（22MB，版权内容，不进 git），
并将路径写入 `config.json`。重启后端后立即生效。

依赖 `ilspycmd`，若未安装：
```bash
dotnet tool install -g ilspycmd
```

---

## 7. 常见问题

**Q：编译报错 `Pack created with a newer version of the engine`**
A：Godot 版本必须是 **4.5.1**，不能用 4.5.2 或其他版本。重新运行 `tools\setup_mod_deps.bat`。

**Q：游戏不加载 mod**
A：mods 目录下需要同时存在 `.dll` 和 `.pck`，缺一不可。检查 `<sts2_path>/mods/<ModName>/` 目录。

**Q：游戏启动闪退**
A：通常是代码错误导致。常见原因：
- 卡牌缺少 `[Pool]` 属性
- 遗物缺少 `ShouldReceiveCombatHooks => true`
- 本地化 JSON 格式错误（必须是平铺 key-value，不能嵌套）
- 检查游戏日志：`%APPDATA%/Godot/app_userdata/Slay the Spire 2/logs/`

**Q：图生 API 报错**
A：检查 `config.json` 中的 `api_key` 是否正确。即梦（volcengine）需要同时填写 `api_key`（Access Key ID）和 `api_secret`（Secret Access Key）。

**Q：Code Agent 不响应 / 超时**
A：
- `claude_subscription` 模式：确认已运行 `claude login` 且订阅有效
- `api_key` 模式：检查 key 余额和网络连通性

**Q：`dotnet publish` 报错 DLL 被锁定**
A：游戏运行时 DLL 会被占用。先退出游戏，再重新部署。







