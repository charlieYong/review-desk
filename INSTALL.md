# Review Desk：Agent 安装指引

收到安装请求后，按下面步骤完成安装、启动和验收。默认使用解压目录作为安装目录、`127.0.0.1:8088` 作为访问地址；用户已指定的目录、端口和访问范围优先。常规安装直接执行，仅在缺少系统安装权限或必须由用户选择时询问。

## 1. 检查环境

- 将 ZIP 完整解压，进入包含本文件和 `server.py` 的 `review-desk` 目录。路径包含空格时给命令参数加引号。
- 检查 Python 版本，要求 3.10 或更新版本，且可创建带 pip 的虚拟环境。Linux/macOS 使用 `python3 --version`，Windows PowerShell 使用 `py -3 --version`（没有 `py` 时检查 `python`）。
- 检查预定端口是否占用；占用时保留已有服务，选用可用端口并在后续命令和交付地址中统一替换。

ZIP 包含系统源码、体验示例、浏览器测试及 `wheels/` 中的通用 Python 依赖包，不包含 Python 解释器。已有合适 Python 时可离线安装和运行；普通使用无需 Node.js 或前端构建。

## 2. 安装依赖

Linux / macOS：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links ./wheels -r requirements.txt
.venv/bin/python -m pip check
```

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links ./wheels -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

完成条件：依赖安装成功，`pip check` 无依赖冲突。直接调用虚拟环境里的 Python，无需激活脚本。

若 Python 缺失，使用目标机器原有的软件管理方式安装 Python 3.10+；Ubuntu/Debian 创建环境提示缺少 ensurepip 时通常需要安装匹配版本的 `python3-venv`。需要管理员权限且尚未获授权时，报告具体缺项并申请权限。若使用的是源码仓库而非 ZIP、没有 `wheels/`，改用虚拟环境里的 `python -m pip install -r requirements.txt` 联网安装。

## 3. 启动与内容目录

先用自带示例验证。Linux / macOS：

```sh
.venv/bin/python server.py --directory ./examples --bind 127.0.0.1 --port 8088
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe server.py --directory ./examples --bind 127.0.0.1 --port 8088
```

服务为前台进程，保持终端运行；`Ctrl+C` 停止。使用 Agent 的后台终端运行能力时，记录进程或会话及停止方法。用户需要长期运行时，复用目标环境现有的服务管理方式，配置绝对路径、日志和重启命令；交付前确认服务在 Agent 命令结束后仍存活。

验收后，用用户指定的内容目录重新启动；未指定时在安装目录创建 `content/`，将两个示例复制进去作为初始内容，再将 `--directory` 改成该目录。保留已有文件，不覆盖同名用户文件。内容目录须存在，支持 HTML、Markdown 及其相对图片等资源。

仅当用户需要局域网共享时，将 `--bind` 改为 `0.0.0.0`，交付机器的实际局域网 IP 地址，并从访问端验证连通性。`0.0.0.0` 是监听地址，不是交付 URL。本工具没有账号系统，内容目录只放准备分享的可信材料；具体使用边界见 `README.md`。

## 4. 验收实际运行结果

对最终运行的服务执行以下检查，使用实际端口和目录：

1. 请求 `/`、`/_preview/files`、`/_preview/theme.css`，确认 HTTP 200，文件列表包含内容目录中的示例或方案。
2. 浏览器打开首页，分别进入 Markdown 和 HTML；确认正文、Markdown 表格与代码块正常展示。
3. 选择正文文字添加批注，刷新后确认恢复；点击「汇总并复制」，确认汇总含选中原文和意见。浏览器不允许剪贴板操作时，验证手动复制文本可用。
4. 确认最终服务仍运行，并记录访问地址、内容目录、启动和停止方法。

可用浏览器自动化时直接完成交互检查。若环境没有浏览器能力，完成 HTTP 检查并明确列出待用户完成的交互检查，不能将 HTTP 200 当作全部功能通过。

需要自动回归验证时，按 `README.md` 的「浏览器验证」使用随包 `tests/browser.cjs`；测试使用临时目录并自行停止测试服务。Node.js、Playwright 和 Chromium 仅用于此测试，安装它们通常需要联网。测试通过后仍需检查最终服务地址。

## 5. 配置 Agent 自动发布

按 `README.md` 的「让 Agent 自动发布方案」生成指令，将占位符替换为本次安装的最终内容目录绝对路径和用户可访问的根地址。

用户要求配置自动发布时，将生成的段落合并到所用 Agent 实际加载的用户级全局 `AGENTS.md` / `CLAUDE.md`；已有同用途段落则更新，保留其他规则。仅有安装请求时，在交付中附上可直接复制的完整段落，供用户启用。全局配置使其他项目也能触发发布，项目仓库内的说明不具备这一作用。

完成条件：生成的指令无未替换占位符，目录和地址与已验收服务一致；已写入时记录配置文件位置，否则明确为待用户配置。后续发布直接复用现有服务，无需每次重新安装或启动。

## 6. 向用户交付

简洁报告：安装位置、可访问 URL、放置方案的目录、实际启动与停止命令、已通过和未完成的验收项。提醒批注保存在当前浏览器，分享链接只分享方案入口；保留访问域名与端口有助于继续使用原批注。

常见失败按证据处理：`ModuleNotFoundError` 检查是否用了虚拟环境 Python；地址占用检查端口；局域网不可达检查监听地址和防火墙；Markdown 读取失败检查 UTF-8 编码。修改后重试对应检查。
