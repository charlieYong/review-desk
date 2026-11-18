# Install Review Desk

[简体中文](INSTALL.zh-CN.md) · [Project README](README.md)

Use Python 3.10 or later. The examples bind explicitly to `127.0.0.1:8088`. If the port is busy, choose a free one and use it consistently. Quote paths that contain spaces.

## 1. Get the source

```sh
git clone https://github.com/charlieYong/review-desk.git
cd review-desk
```

If you received a team bundle separately, extract it and open the directory containing `server.py`. A bundle with `wheels/` can be installed offline with an existing Python interpreter. Use a bundle that matches the version you intend to run. A GitHub source archive provides the source and uses the normal dependency installation below.

## 2. Install dependencies

Linux or macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

For an offline bundle, add `--no-index --find-links ./wheels` to the `pip install` command. Call the venv's Python directly. Normal operation requires no Node.js or frontend build.

## 3. Start the service

Linux or macOS:

```sh
.venv/bin/python server.py --directory ./examples --bind 127.0.0.1 --port 8088
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe server.py --directory ./examples --bind 127.0.0.1 --port 8088
```

Open <http://127.0.0.1:8088/>. The server runs in the foreground and stops with Ctrl+C. For a long-running deployment, use the target machine's service manager and record the start and stop commands. After trying the examples, point `--directory` at your existing content directory or create a dedicated one. Keep any existing content and give the server only the permissions it needs.

The CLI listens on `0.0.0.0` if you omit `--bind`. Keep the explicit loopback binding for local use. For LAN sharing, restrict network access first, bind to the intended interface, and verify connectivity from the intended client. The service has no accounts, shares notes among reachable clients, and can serve files readable by its process outside the content directory. See the [deployment boundaries](README.md#use-and-deployment-boundaries).

## 4. Verify the running service

1. Request `/`, `/_preview/files`, and `/_preview/theme.css` and check that each returns HTTP 200. Verify that the library lists the expected documents, that locating an external document adds it, and that missing files are listed separately.
2. Open a Markdown and an HTML example. Check the Markdown table, code block, Mermaid diagram, and relative links. Open a standalone preview from the library, go to its containing directory, and return to the review. From an existing review with a draft, open preview and directory links and confirm that the draft stays in the review tab.
3. Select text and save an annotation. Refresh and verify that the note and highlight return. Open the summary and copy it, or check the manual copy fallback. Confirm the summary includes the quote and the note.
4. In two independent browser contexts, check that both visitors see saved notes, concurrent additions are retained, and a stale edit preserves its draft. On a test document, change the source in place and check the update prompt, new round, and archived notes. Verify persistence after a service restart when the deployment can be restarted. Record actual cross-device network checks separately.
5. Confirm the final process is still running. Record its URL, content directory, state directory, and start and stop commands.

When browser interaction is unavailable, record which checks remain unverified. For automated regression testing, follow [Browser tests](README.md#browser-tests) and run the full `npm test` suite. The temporary test services are separate from the final deployment.

## 5. Configure agent review links

Use the [agent template](README.md#give-your-agent-review-links) with the verified service origin and actual standalone content directory. For cross-project use, place the template in the agent's user-level instructions only when configuring that agent was requested. Update any existing section with the same purpose. The agent should verify the source and review URLs before handing off a document.

## 6. Back up and upgrade

Back up the full state directory, including `catalog.json` and shared review files. The default is `data/` under the application directory. Set `--state-directory` to store it elsewhere. Keep the chosen directory when upgrading and use a single server process to write it. Preserve the source document paths to retain their review identity.

After an upgrade, refresh open review tabs. To import old browser-local notes, open each affected document in the original browser at the original service origin. See [Upgrading from browser-local notes](README.md#upgrading-from-browser-local-notes).

If startup fails with `ModuleNotFoundError`, check that you are using the venv's Python. If a LAN client cannot connect, check the bind address and firewall. If Markdown fails to render, check its UTF-8 encoding.
