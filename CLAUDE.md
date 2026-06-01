# CLAUDE.md - ClawCat Project

## Project Overview

ClawCat is a single-user Telegram controller for local coding-agent CLIs. Codex
is the default public provider; legacy Claude CLI support remains available for
existing private installs.

## Project Structure

```text
ClawCat/
├── clawcat/
│   ├── agent_runner.py   # Provider-aware local agent subprocess management
│   ├── bot.py            # Telegram bot commands and handlers
│   ├── claude_runner.py  # Backward-compatible imports
│   ├── config.py         # Configuration loading and validation
│   ├── session_store.py  # Session persistence metadata
│   ├── session_monitor.py # Optional desktop monitor window
│   └── service.py        # Windows service wrapper
├── tests/                # Unit tests
├── config.example.yaml   # Configuration template
├── run.py                # Console entry point
└── install_service.py    # Optional Windows service installer
```

## Development Rules

### Command Registry

When adding or modifying Telegram commands, update the `COMMANDS` dictionary in
`clawcat/bot.py`. This dictionary is the source of truth for `/commands` output.

Also ensure:

1. Add the command handler method (`cmd_<name>`)
2. Register the handler in `build_application()`
3. Update `COMMANDS`

### Security Defaults

- Keep Codex as the public default provider.
- Keep remote runs sandboxed by default.
- Do not expose full-access mode unless `allow_dangerous_mode` is explicitly
  enabled in config.
- Do not commit `config.yaml`, logs, session files, tokens, or local workspaces.
- Preserve macOS/Linux console mode when changing Windows service code.

### Configuration

- Config is loaded from `config.yaml`.
- `config.yaml` is gitignored because it contains the Telegram bot token.
- Update `config.example.yaml` when adding new options.

## Running

```bash
python run.py
python -m unittest discover -s tests
```

Windows service mode is optional:

```powershell
python install_service.py
```
