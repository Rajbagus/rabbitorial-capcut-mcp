# Agent setup playbook

This file tells an AI coding agent how to install, register, and verify this
CapCut MCP server end-to-end. Follow it in order. The goal state: the user's
Claude Code (or other MCP client) exposes a `capcut` server whose tools can
create and edit CapCut drafts that open directly in the CapCut desktop app.

## What this is
A local [MCP](https://modelcontextprotocol.io) server that drives CapCut by
writing/editing its native draft files. It runs **entirely on the user's
machine** and makes **no outbound network calls** for its core editing work.
(Two remote "phone-home" endpoints present in the original upstream project
have been removed — see `NOTICE`.)

## Prerequisites — check these first
1. **Python 3.10+** on PATH. Check: `python --version` (or `python3`).
2. **CapCut desktop installed.** The server writes drafts into CapCut's
   projects folder; if CapCut isn't installed, drafts have nowhere to appear.
3. **An MCP client with a CLI** — normally Claude Code (`claude`). If the
   `claude` CLI isn't available, you'll register the server manually (below).
4. **git** (only needed if the user hasn't already cloned this repo).

Do not proceed to registration until Python is confirmed ≥ 3.10.

## Fast path (preferred)
From the repository root, run:

```
python install.py
```

`install.py` will: create `.venv`, install dependencies, locate the CapCut
drafts folder for this OS, write a local `config.json`, smoke-test that the
server imports, and register the server with Claude Code (or print the exact
registration command if the `claude` CLI is missing).

If `install.py` completes and prints "Registered as MCP server 'capcut'",
you are done — tell the user to **restart their MCP client** so the tools load,
then verify (below).

## Manual path (if the fast path fails or you prefer explicit steps)
Run these from the repository root. Adjust `python`/`python3` to the platform.

1. **Create + populate a virtual environment**
   ```
   python -m venv .venv
   # Windows:  .venv\Scripts\python -m pip install --upgrade pip
   # macOS:    .venv/bin/python  -m pip install --upgrade pip
   <venv-python> -m pip install -r requirements.txt -r requirements-mcp.txt
   ```

2. **Write `config.json`** (only if it doesn't already exist) with local
   defaults:
   ```json
   {
     "draft_profile": "capcut",
     "is_capcut_env": true,
     "draft_domain": "http://localhost:9001",
     "port": 9001,
     "preview_router": "/draft/downloader",
     "is_upload_draft": false,
     "oss_config": [],
     "mp4_oss_config": []
   }
   ```

3. **Determine the CapCut drafts folder** for this OS:
   - **Windows:** `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`
   - **macOS:** `~/Movies/CapCut/User Data/Projects/com.lveditor.draft`

   The server also reads the `CAPCUT_DRAFT_FOLDER` environment variable and
   uses that path if set. Confirm the folder exists; if not, CapCut may not be
   installed or may use a custom location — ask the user.

4. **Smoke-test the import** (must print a tool count with no error):
   ```
   <venv-python> -c "import mcp_server as m; assert m.CAPCUT_AVAILABLE; print(len(m.TOOLS))"
   ```

5. **Register with Claude Code** (user scope so it's always available). Use the
   venv's Python and the absolute path to `mcp_server.py`:
   ```
   claude mcp add capcut --scope user \
     --env CAPCUT_DRAFT_FOLDER="<drafts-folder-from-step-3>" \
     -- "<absolute-path-to>/.venv/<Scripts|bin>/python" "<absolute-path-to>/mcp_server.py"
   ```
   The server inserts its own directory onto `sys.path`, so no `PYTHONPATH` or
   working-directory setting is needed.

## Verify it worked
1. Restart the MCP client (Claude Code) so it picks up the new server.
2. Confirm the client lists a `capcut` server with tools such as
   `create_draft`, `add_video`, `add_audio`, `add_text`, `add_subtitle`,
   `save_draft`.
3. Optional live check: ask the client to `create_draft` and then `save_draft`,
   then confirm a new project appears in the CapCut desktop app.

## Troubleshooting
- **`ModuleNotFoundError` during the smoke test** — a dependency didn't
  install. Re-run the pip install; if one package is missing, install it into
  `.venv` and re-test. Do not switch to the system Python.
- **Smoke test prints nothing / `CAPCUT_AVAILABLE` is False** — read the stderr;
  it names the failed import. Usually a missing dependency (see above).
- **Drafts don't appear in CapCut** — the drafts folder path is wrong. Find the
  real `com.lveditor.draft` folder, set `CAPCUT_DRAFT_FOLDER` to it, and
  re-register (or re-run `install.py`).
- **`claude: command not found`** — the user isn't using Claude Code, or its CLI
  isn't on PATH. Register with whatever MCP client they use; the server is a
  standard stdio MCP server launched as `<python> mcp_server.py`.
- **Windows execution/quoting** — always pass absolute paths; paths with spaces
  must be quoted.

## Do NOT
- Do not commit `config.json` or `.venv` (both are git-ignored).
- Do not re-enable remote draft upload/retrieval unless the user asks; it's off
  by design to keep everything local.
- Do not edit files under `pyJianYingDraft/` or `template*/` — they are the
  engine and the draft scaffolding.
