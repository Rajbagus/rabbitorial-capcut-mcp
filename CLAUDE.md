# For AI agents: set up this CapCut MCP server

If you are an AI coding agent (Claude Code or similar) and the user has opened
this repository, they almost certainly want you to **install and register this
CapCut editing server** so they can edit CapCut videos by talking to you.

**Do this:**
1. Read **[AGENTS.md](AGENTS.md)** and follow it exactly.
2. The fast path is: run `python install.py` from this directory.
3. Verify the `capcut` MCP server registered, then tell the user to restart
   their client so the tools load.

If a step fails, use the Troubleshooting section of AGENTS.md — diagnose the
actual error, don't guess. This tool runs **fully locally**; it does not call
any remote server.
