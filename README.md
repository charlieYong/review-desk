# Review Desk

一个轻量的 HTML / Markdown 方案审查工作台。选中文字，连续添加批注，最后将原文和修改意见汇总复制到 Codex CLI 或其他对话工具。

无需修改方案文件，也不需要前端构建。将文件放入内容目录，浏览器即可开始审查。

## 介绍视频

约 15 秒看完经典用法：打开方案列表 → 进入审查页 → 划词批注 → 汇总并复制到对话工具。

![Review Desk 经典用法演示](docs/assets/intro-demo.mp4)

若无法内嵌播放，可直接打开 [intro-demo.mp4](docs/assets/intro-demo.mp4)。

## 功能

- 自动发现 HTML、Markdown 和子目录中的方案，按文件修改时间倒序展示。
- 按文件名搜索、按 HTML / Markdown 类型筛选，每 15 秒刷新列表。
- Markdown 使用接近 GitHub README 的排版，支持表格、代码块、任务列表、图片和章节锚点。
- 划词批注、整体意见、多条编辑与删除。
- 按方案地址和审查轮次在浏览器保存批注，刷新后恢复。
- 检测文档内容更新，手动开始新一轮并归档旧批注；历史意见可标记已解决或继续跟进。
- 汇总包含方案来源、引用原文和修改意见，支持一键复制和手动复制回退。
- 可分享审查链接，适配桌面与手机。

## 快速开始

使用团队 ZIP 安装包时，解压后让 Agent 按 [INSTALL.md](INSTALL.md) 完成安装和验收；包内附带离线 Python 依赖。

需要 Python 3.10 或更新版本。

```sh
git clone https://github.com/charlieYong/review-desk.git
cd review-desk
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py --directory ./examples --bind 127.0.0.1 --port 8088
```

打开 <http://127.0.0.1:8088/>，点击示例文件名进入批注页。Windows 使用 `.venv\Scripts\python.exe` 替换 `.venv/bin/python`。

使用自己的内容目录：

```sh
mkdir -p ~/preview-docs
.venv/bin/python server.py --directory ~/preview-docs --bind 127.0.0.1 --port 8088
```

把 `.html`、`.htm`、`.md`、`.markdown` 文件及其相对资源放入目录。Markdown 使用 UTF-8 编码。局域网访问时使用 `--bind 0.0.0.0`，然后通过该机器的 IP 访问。

## 让 Agent 自动发布方案

建议在安装时，将下面的指令配置到所用 Agent 的用户级全局 `AGENTS.md` / `CLAUDE.md`，这样在其他项目生成方案时也能自动发布。本项目 README 提供配置模板；仅在本仓库添加指令，无法覆盖其他项目的会话。

先将 `<内容目录绝对路径>` 和 `<访问根地址>` 替换为实际部署值，例如 `/home/<用户名>/html-preview/` 和 `http://<服务器IP>:8088`。其中 `<用户名>` 和 `<服务器IP>` 均为占位符，使用时需替换；地址应从用户浏览器可达。

```markdown
## 方案远程审查

- 生成供用户远程审查、预览或批注的临时独立 HTML / Markdown 方案、报告或原型时，无需再次确认，自动将最终文件发布到 `<内容目录绝对路径>`。
- 新方案使用 `<topic>-YYYYMMDD-HHMMSS.html` 或 `.md` 格式的 ASCII 文件名。HTML 优先使用单文件；有相对资源时一并发布并保持相对路径。
- 项目正式源文件保留在项目约定位置，需要远程审查时另发布一份。同一方案按批注修改时，更新已发布的同名文件，沿用原审查地址，以保留审查轮次和历史。
- 发布后请求 `<访问根地址>/<filename>` 和 `<访问根地址>/_review?page=<URL编码后的站内文件路径>`，确认均返回 HTTP 200；失败时说明具体原因。
- 最终回复优先给出可直接批注的审查链接；用户只需预览时给出原文链接。
```

例如文件名为 `checkout-20260911-103000.html`，审查链接为 `http://<服务器IP>:8088/_review?page=%2Fcheckout-20260911-103000.html`。文件复制到内容目录后即由现有服务提供，无需重启。HTTP 检查用于确认发布可达，首次安装的交互验收见 [INSTALL.md](INSTALL.md)。

## 审查流程

1. 在首页点击文件名，进入左侧正文、右侧批注的工作台。
2. 选中原文，点击「＋ 批注」，填写意见并保存；也可直接写整体意见。
3. 重复操作，完成后点击「汇总并复制」。
4. 将文本粘贴到终端对话，交给 Agent 继续修改。汇总只包含本轮批注，并注明轮次和内容版本。
5. Agent 覆盖同名文档后，切回窗口或等待自动检查，页面提示文档更新。点击「开始新一轮」加载新版，上一轮批注归档，当前清单和高亮清空。存在草稿时须先保存或取消。
6. 展开「历史批注」核对旧意见，可标记「已解决」或「继续跟进」。继续跟进会将意见带入编辑区，保存后加入本轮；引用无法唯一定位时需要在新正文重新选段。

内容变化通过文件内容指纹判断，仅修改时间变化不会触发新轮次。发现更新时不会自动替换正在审查的正文；刷新页面会显示最新正文，同时提示开始新一轮，旧批注不再高亮。历史仅保存意见和引用，不保存完整旧文档。旧版浏览器批注首次使用时关联到当时内容，无法追溯此前对应的文件版本。不同文件名仍作为不同方案处理。

审查地址使用 `/_review?page=...`，`page` 是经过 URL 编码的站内文件路径。复制浏览器地址即可分享方案入口，批注本身仅保存在当前浏览器中，不随链接分享。

原始 HTML URL 保持原样。Markdown 原地址显示排版后的正文，加 `?raw=1` 可读取源文。相对图片和链接继续按原文件位置解析。

## 使用边界

这是面向个人或可信局域网的文件预览工具，没有账号系统。内容目录中的文件会被提供给访问者，HTML 按原样运行；请只放入准备预览的可信文件，不要把整个代码仓库或含凭证的目录作为内容目录。

批注依赖浏览器 localStorage；更换浏览器、域名或端口后不会自动迁移。图片和 Canvas 内的文字、跨域 iframe 不支持划词。Markdown 内嵌 HTML 按文本展示；代码块保留格式，不提供语法高亮。复制结果受浏览器权限影响，失败时可手动复制。

## 项目结构

| 文件 | 用途 |
| --- | --- |
| `server.py` | 文件列表、Markdown 渲染和静态资源服务 |
| `index.html` | 方案目录、搜索和类型筛选 |
| `review.html` | 划词批注与汇总复制 |
| `theme.css` | 工作台与 Markdown 正文样式 |
| `examples/` | 不含业务数据的体验示例 |
| `tests/browser.cjs` | 使用独立临时目录的浏览器验收 |

运行时仅依赖 [markdown-it-py](https://markdown-it-py.readthedocs.io/en/latest/using.html)，不依赖外部 CDN。

## 浏览器验证

需要 Node.js 和 Chromium。测试自动启动临时服务，创建并清理独立夹具，不使用日常预览目录。

```sh
npm install
npx playwright install chromium
PYTHON=.venv/bin/python npm test
```

测试覆盖 Markdown 渲染、相对图片、划词批注、复制结果提示、刷新恢复、排序、筛选、新文件发现、原始 HTML 和手机布局。`PYTHON` 可指定 Python 可执行文件；`CHROMIUM_EXECUTABLE_PATH` 可指定已有 Chromium。
