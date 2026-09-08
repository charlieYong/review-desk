# Review Desk

一个轻量的 HTML / Markdown 方案审查工作台。选中文字，连续添加批注，最后将原文和修改意见汇总复制到 Codex CLI 或其他对话工具。

无需修改方案文件，也不需要前端构建。将文件放入内容目录，浏览器即可开始审查。

## 功能

- 自动发现 HTML、Markdown 和子目录中的方案，按文件修改时间倒序展示。
- 按文件名搜索、按 HTML / Markdown 类型筛选，每 15 秒刷新列表。
- Markdown 使用接近 GitHub README 的排版，支持表格、代码块、任务列表、图片和章节锚点。
- 划词批注、整体意见、多条编辑与删除。
- 按方案地址在浏览器保存批注，刷新后恢复。
- 汇总包含方案来源、引用原文和修改意见，支持一键复制和手动复制回退。
- 可分享审查链接，适配桌面与手机。

## 快速开始

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

## 审查流程

1. 在首页点击文件名，进入左侧正文、右侧批注的工作台。
2. 选中原文，点击「＋ 批注」，填写意见并保存；也可直接写整体意见。
3. 重复操作，完成后点击「汇总并复制」。
4. 将文本粘贴到终端对话，交给 Agent 继续修改。

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
