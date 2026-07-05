#!/usr/bin/env python3
"""
One-shot installer for the CapCut MCP server.

Run:  python install.py

It will:
  1. Verify Python >= 3.10
  2. Create a local virtual environment (.venv)
  3. Install dependencies
  4. Locate your CapCut drafts folder (so new drafts show up in the app)
  5. Write a local config.json
  6. Smoke-test that the server imports cleanly
  7. Register the server with Claude Code (if the `claude` CLI is available),
     or print the exact command to run.

Designed to be run by a human OR by an AI coding agent (see AGENTS.md).
"""
import os
import sys
import json
import shutil
import platform
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent
VENV = REPO / ".venv"
MIN_PY = (3, 10)


def log(msg):
    print(f"[install] {msg}", flush=True)


def die(msg):
    print(f"[install] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def venv_python():
    if platform.system() == "Windows":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def check_python():
    if sys.version_info < MIN_PY:
        die(f"Python {MIN_PY[0]}.{MIN_PY[1]}+ required, found {sys.version.split()[0]}")
    log(f"Python {sys.version.split()[0]} OK")


def create_venv():
    if venv_python().exists():
        log(".venv already exists, reusing it")
        return
    log("Creating virtual environment (.venv) ...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)


def pip_install():
    py = str(venv_python())
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    reqs = []
    for fname in ("requirements.txt", "requirements-mcp.txt"):
        p = REPO / fname
        if p.exists():
            reqs += ["-r", str(p)]
    if not reqs:
        die("No requirements files found")
    log("Installing dependencies (this can take a few minutes) ...")
    subprocess.run([py, "-m", "pip", "install", *reqs], check=True)


def capcut_draft_folder():
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(base) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    if system == "Darwin":
        return Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    # CapCut desktop is not officially supported on Linux.
    return None


def write_config():
    cfg = REPO / "config.json"
    if cfg.exists():
        log("config.json already exists, leaving it untouched")
        return
    data = {
        "draft_profile": "capcut",
        "is_capcut_env": True,
        "draft_domain": "http://localhost:9001",
        "port": 9001,
        "preview_router": "/draft/downloader",
        "is_upload_draft": False,
        "oss_config": [],
        "mp4_oss_config": [],
    }
    cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log("Wrote config.json (local-only defaults)")


def smoke_test():
    py = str(venv_python())
    log("Smoke-testing the server import ...")
    r = subprocess.run(
        [py, "-c",
         "import mcp_server as m; assert m.CAPCUT_AVAILABLE, 'modules failed to import'; print(len(m.TOOLS))"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    if r.returncode != 0:
        die("Smoke test failed:\n" + r.stdout + r.stderr)
    log(f"Server imports cleanly; {r.stdout.strip()} tools available")


def _register_via_config(draft_folder):
    """Fallback registration for when the `claude` CLI isn't on PATH
    (e.g. the VS Code extension): write the server straight into
    ~/.claude.json, the same file the CLI would update. Returns True on success."""
    cfg = Path.home() / ".claude.json"
    entry = {
        "type": "stdio",
        "command": str(venv_python()),
        "args": [str(REPO / "mcp_server.py")],
        "env": {"CAPCUT_DRAFT_FOLDER": draft_folder} if draft_folder else {},
    }
    data = {}
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            return False
        backup = cfg.with_name(".claude.json.capcut-backup")
        if not backup.exists():
            backup.write_text(cfg.read_text(encoding="utf-8"), encoding="utf-8")
    if not isinstance(data.get("mcpServers"), dict):
        data["mcpServers"] = {}
    data["mcpServers"]["capcut"] = entry  # replaces any existing entry
    cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def register(draft_folder):
    py = str(venv_python())
    server = str(REPO / "mcp_server.py")
    cmd = ["claude", "mcp", "add", "capcut", "--scope", "user"]
    if draft_folder:
        cmd += ["--env", f"CAPCUT_DRAFT_FOLDER={draft_folder}"]
    cmd += ["--", py, server]
    printable = " ".join(f'"{c}"' if " " in c else c for c in cmd)

    if shutil.which("claude"):
        # Idempotent: replace any existing 'capcut' registration first.
        if subprocess.run(["claude", "mcp", "get", "capcut"],
                          capture_output=True, text=True).returncode == 0:
            log("Found an existing 'capcut' registration - replacing it.")
            for _scope in ("user", "local", "project"):
                subprocess.run(["claude", "mcp", "remove", "capcut", "--scope", _scope],
                               capture_output=True)
            subprocess.run(["claude", "mcp", "remove", "capcut"], capture_output=True)
        log("Registering with Claude Code (CLI) ...")
        if subprocess.run(cmd).returncode == 0:
            log("Registered as MCP server 'capcut'. Restart Claude Code to load it.")
            return
        log("CLI registration failed; using the config file instead ...")

    # No `claude` CLI (e.g. the VS Code extension) -> write ~/.claude.json directly.
    if _register_via_config(draft_folder):
        log("Registered 'capcut' in ~/.claude.json. Restart Claude Code / your editor to load it.")
    else:
        log("Could not auto-register. Add this MCP server manually:")
        print("\n  " + printable + "\n")


def main():
    log(f"Installing into {REPO}")
    check_python()
    create_venv()
    pip_install()

    df = capcut_draft_folder()
    if df and df.exists():
        log(f"Found CapCut drafts folder: {df}")
    elif df:
        log(f"CapCut drafts folder not found at: {df}")
        log("Make sure CapCut desktop is installed. You can set CAPCUT_DRAFT_FOLDER later.")
    else:
        log("Could not auto-detect a CapCut drafts folder on this OS; set CAPCUT_DRAFT_FOLDER manually.")

    write_config()
    smoke_test()
    register(str(df) if df else None)
    log("Done.")


if __name__ == "__main__":
    main()
