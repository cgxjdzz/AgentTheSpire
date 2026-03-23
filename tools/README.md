# tools 目录说明

本目录集中存放 AgentTheSpire 的安装、启动、开发辅助和沙箱验证脚本。

## 常用入口

- `tools\install.bat` / `./tools/install.sh`
  安装后端依赖、前端依赖并构建前端。
- `tools\setup_mod_deps.bat` / `./tools/setup_mod_deps.sh`
  安装或配置 Mod 开发依赖，如 .NET 9 和 Godot 4.5.1。
- `tools\start.bat` / `./tools/start.sh`
  启动生产模式服务。
- `tools\start_dev.bat`
  启动开发模式，拉起后端热重载和 Vite 前端开发服务器。

## 辅助脚本

- `tools\decompile_sts2.py`
  反编译 `sts2.dll`，并把输出路径写入 `config.json`。
- `tools\generate_sandbox_wsb.bat`
  根据当前仓库路径生成 Windows Sandbox 配置文件 `tools\sandbox_test.wsb`。
- `tools\sandbox_setup.bat`
  在 Windows Sandbox 中执行安装验证。
- `tools\verify-install-bat.ps1`
  校验 `tools\install.bat` 的关键行为和格式。

## 说明

- 所有脚本都按“脚本目录的上一级是仓库根目录”处理路径。
- `godot/`、`backend/`、`frontend/`、`config.json` 仍保留在仓库根目录，不随脚本移动。
- 生成型文件如 `tools\sandbox_test.wsb` 不应提交到仓库。
