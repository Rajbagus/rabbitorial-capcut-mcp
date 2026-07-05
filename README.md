# CapCut MCP — edit CapCut videos with an AI agent

This is a local [MCP](https://modelcontextprotocol.io) server that lets an AI
assistant (like **Claude Code**) build and edit **CapCut** video projects for
you — creating drafts, adding video/audio/images/text/subtitles/effects, and
saving projects that open straight in the CapCut desktop app.

It runs **entirely on your machine** and makes **no outbound calls** to do its
work. (See [Security](#security).)

## The easy way: let the AI install it

1. Install [CapCut desktop](https://www.capcut.com/) and
   [Claude Code](https://claude.com/claude-code), and make sure you have
   **Python 3.10+**.
2. Clone this repo and open it in Claude Code:
   ```
   git clone <your-repo-url> capcut-mcp
   cd capcut-mcp
   claude
   ```
3. Tell Claude: **"Set this up."** It will read `CLAUDE.md` / `AGENTS.md` and
   install, configure, and register everything itself.
4. Restart Claude Code. You now have `capcut` tools — ask it to edit a video.

## The manual way

```
python install.py
```

This creates a virtual environment, installs dependencies, finds your CapCut
drafts folder, writes a local `config.json`, verifies the server, and registers
it with Claude Code. Full manual steps are in **[AGENTS.md](AGENTS.md)**.

## What it can do

Once registered, the assistant can call tools including:

- `create_draft` — start a new CapCut project
- `add_video`, `add_audio`, `add_image` — place media on the timeline
- `add_text`, `add_subtitle` — captions and titles
- `add_effect`, `add_sticker`, `add_video_keyframe` — effects and animation
- `get_video_duration` — inspect media
- `list_drafts`, `load_draft`, `save_draft` — open and save projects

Drafts are written into CapCut's projects folder, so they show up in the CapCut
app automatically.

## Requirements

- Python 3.10+
- CapCut desktop (Windows or macOS)
- An MCP client — Claude Code recommended

## Security

This is a hardened redistribution. The upstream project it derives from
contacted two remote endpoints; **both have been disabled** so the tool stays
fully local:

- a remote draft-retrieval cloud function, and
- a remote default `draft_domain`.

`config.json` (which can hold cloud-storage keys if you opt in) and `.venv` are
git-ignored and never published. Remote draft upload is **off by default**.

See [`NOTICE`](NOTICE) for attribution and the full list of changes.

## License

Licensed under the **Apache License 2.0** (see [`LICENSE`](LICENSE)). This
project is a modified redistribution of
[CapCutAPI](https://github.com/sun-guannan/CapCutAPI); see [`NOTICE`](NOTICE).
