# Review Desk

[简体中文](README.zh-CN.md) · [Installation guide](INSTALL.md)

Review HTML and Markdown documents in your browser. Select text, leave shared notes, and copy the feedback into Codex CLI or another AI tool. Review project files in place, or put standalone documents in a dedicated content directory.

## Quick start

Install from source with Python 3.10 or later.

```sh
git clone https://github.com/charlieYong/review-desk.git
cd review-desk
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py --directory ./examples --bind 127.0.0.1 --port 8088
```

Open <http://127.0.0.1:8088/> and choose the [Markdown example](examples/README.md) or the [HTML example](examples/welcome.html). Choose a file name to review it or the preview action to read it separately. The application currently displays its controls in Simplified Chinese. [Watch the basic review workflow (MP4)](docs/assets/intro-demo.mp4) · [Animated demo (GIF)](docs/assets/intro-demo.gif)

Run the same start command with `--directory` set to your own existing content directory to serve your documents. Supported extensions are `.html`, `.htm`, `.md`, and `.markdown`. Save Markdown as UTF-8 and keep relative resources alongside the source. See the [installation guide](INSTALL.md) for Windows, offline team bundles, and deployment verification.

## Review workflow

1. Open a file from the home page or enter its absolute path **on the server machine**. The review page also accepts a same-site URL, file name, or absolute path. Successfully locating an external document or opening its review adds it to the shared library, even before anyone leaves a note.
2. Select text and add an annotation, or leave a note on the whole document. Saved quotes are highlighted when they can be matched to the displayed revision. You can edit or delete your notes from the list.
3. Open the standalone preview in a new tab to see the latest content while keeping your review draft. The preview and review pages can open the containing directory. From the directory, select a file to preview it or use its review action. Navigation reaches the configured content root, an external file's Git worktree root, or a standalone external file's containing directory.
4. Copy the review summary into your AI conversation. It includes the source, review round, content revision, and current notes with their quotes. If clipboard access fails, copy the selected text manually.
5. When the source changes in place, return to the review page or wait for the update check. Save or discard any draft, then start a new round to load the latest revision and archive the previous notes. In the history, mark an item resolved or follow up by bringing it into the current draft. Select a new quote if the old one cannot be uniquely located.

The browser tab uses the format `审批 <document title>` (Review <document title>). It takes the title from the first level-one Markdown heading or the HTML title and falls back to the file name.

Document changes are detected from the content, so changing only the modification time leaves the revision intact. An update prompt leaves the displayed document in place. A browser reload shows the latest document and prompts you to start a new round if the shared round is still on an older revision. History stores notes and quotes. Keep older source revisions in your project's version control.

### Library and shared reviews

The home page scans the content directory recursively and merges it with registered paths. Search by file name or directory and filter by format. Available files are sorted by modification time. Missing or unreadable files are listed separately, and their registration and notes remain available when the source returns. The list refreshes on demand, when you return to the window, and every 15 seconds while visible.

External review links use `/_review/<short-title>/<document-id>`. The name comes from the Markdown heading, HTML title, or file name. The document ID stays stable across edits and restarts. Old links, including absolute-path bookmarks and earlier titles, open the same review. The review toolbar and library show project-relative locations or standalone file names. External directory links use `/_browse/<project-label>/<scope-id>/<relative-directory>` and navigate up to the worktree root or the standalone directory.

Files within the content directory use source URLs such as `/plan.md` and review URLs such as `/_review?page=%2Fplan.md`. External sources use scoped URLs such as `/_d/<scope-id>/docs/plan.md`. Relative links and images resolve within that scope. HTML is served as authored. A direct Markdown URL displays rendered Markdown, with `?raw=1` available for the source. All review entries resolve to the real source path, so symlink aliases share notes, and identical file names in separate locations have separate reviews. Renaming or moving a source creates a new document identity.

Registration stores the path independently of the review round. The library recovers paths from older shared state, including documents opened without notes. If an older external document was only located and never registered or reviewed, locate it again. A registration failure makes the locate request fail explicitly. Opening an existing review can still load and save notes and reports the registration failure separately. An unreadable catalog raises a list error. Individual unreadable legacy records are skipped and logged.

Visitors to the same service share reviews. Updates are read on open, reload, window focus or visibility changes, and every 15 seconds while visible. Independent additions can be saved concurrently. A stale edit, delete, history change, or save to an archived round returns HTTP 409 and preserves the draft. Starting a round archives all notes already saved in the previous round. If another visitor starts a round while you have a draft, the review page keeps the draft for you to check.

### Upgrading from browser-local notes

On each browser that holds legacy notes, open the document using the same site origin you used before upgrading. Review Desk imports the browser's legacy notes for the same real source file while preserving the original local data. Each snapshot is imported once. Same-round, same-revision notes merge with shared state. Notes from another revision go into history, and the first import preserves recorded rounds and resolution states. Older notes without a recorded revision are associated with the content at import time. Refresh any review tab left open during the upgrade before saving again.

## Use and deployment boundaries

Run Review Desk on loopback for personal use or behind access controls on a trusted network. The server has no accounts or authentication. Always pass `--bind 127.0.0.1` for local-only use. The CLI defaults to `0.0.0.0` when `--bind` is omitted. Restrict network access before enabling a LAN deployment. The directory browser limits what it lists. Direct file serving can reach files outside the configured content directory that the server process can read. Reachable clients can also read and change shared notes. Run the service with only the filesystem permissions it needs. Serve trusted HTML, which runs as authored.

The state directory defaults to `data/` under the application directory. Use `--state-directory` to override it. Preserve the whole directory across backups and upgrades. `catalog.json` maps public document and scope IDs to real absolute paths. The other JSON files hold reviews. Use one server process per state directory.

Markdown supports tables, code blocks, tasks, images, section anchors, and Mermaid diagrams. Embedded HTML is displayed as text. Code blocks retain formatting without syntax highlighting. Mermaid runs locally, scales tall diagrams to fit the viewport, and leaves the source visible if rendering fails. Text selection in a Mermaid diagram depends on the browser's SVG support. Annotations cannot select text inside images, canvas elements, or cross-origin frames.

## Give your agent review links

Copy the following template into the agent's user-level instructions, such as `AGENTS.md` or `CLAUDE.md`, to use it across projects. Replace `<review-origin>` with an address reachable from your browser and `<content-directory>` with the absolute directory used for standalone documents.

```markdown
## Share documents for review

- Save project documents in the project's documentation directory, using docs/ when no convention exists. Save standalone drafts under <content-directory>. Keep related resources beside the source.
- Request <review-origin>/_preview/locate?path=<URL-encoded absolute source path> and read the returned page and review values. Use both values as returned, including their escaping.
- Open the source at <review-origin> plus page and the review at <review-origin> plus review. If the server returns only page, use <review-origin>/_review?page= plus the URL-encoded page value.
- Verify that the source and review URL both return HTTP 200 and that the source is the intended document. Include the full clickable review URL when handing off the document. Report a failed check with its actual error.
- Revise the same file in place so readers keep their notes and review history. Use the current review URL from locate when sharing again.
```

## Project structure

| File | Responsibility |
| --- | --- |
| `server.py` | File discovery, directory navigation, Markdown rendering, and HTTP endpoints |
| `review_store.py` | Shared reviews, rounds, legacy imports, and the document catalog |
| `index.html`, `review.html`, `preview.html` | Library, review workspace, and standalone preview |
| `theme.css`, `vendor/` | Styles and the bundled Mermaid runtime |
| `examples/` | Sample Markdown and HTML |
| `tests/` | Browser, shared review, and document library regression suites |

The Python server serves HTML, CSS, and JavaScript directly. Runtime dependencies are [markdown-it-py](https://markdown-it-py.readthedocs.io/en/latest/using.html) and the bundled Mermaid script. Node.js is used for browser testing.

## Browser tests

With the Python dependencies installed, run the full Playwright suite.

```sh
npm ci
npx playwright install chromium
PYTHON=.venv/bin/python npm test
```

On Windows PowerShell, set `$env:PYTHON = ".\.venv\Scripts\python.exe"` before `npm test`. Set `CHROMIUM_EXECUTABLE_PATH` to use an existing Chromium binary.

- `tests/browser.cjs` covers Markdown and Mermaid rendering, selection and highlights, copying, legacy notes, review rounds, standalone previews, directory navigation, relative resources, and mobile layout.
- `tests/shared.cjs` uses independent browser contexts to cover concurrent changes, conflicts, polling, migration, and persistence across server restarts.
- `tests/library.cjs` covers registration, historical backfill, Unicode paths, deduplication, missing-file recovery, and storage errors.

The suite uses temporary services and fixtures. For checks against an actual deployment, see the [installation guide](INSTALL.md#4-verify-the-running-service).
