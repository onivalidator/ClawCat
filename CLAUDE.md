# CLAUDE.md - ClawCat Project

## Project Overview

ClawCat is a Telegram bot for remote control of Claude Code CLI on Windows.

## Project Structure

```
ClawCat/
├── clawcat/
│   ├── bot.py           # Telegram bot commands and handlers
│   ├── claude_runner.py # Claude CLI subprocess management
│   ├── config.py        # Configuration loading
│   ├── session_store.py # Session persistence (JSON)
│   ├── session_monitor.py # Desktop monitor window (tkinter)
│   └── service.py       # Windows service wrapper
├── config.yaml          # Active configuration (gitignored)
├── config.example.yaml  # Configuration template
├── run.py               # Console entry point
└── install_service.py   # Service installer
```

## Development Rules

### Command Registry

When adding or modifying Telegram commands, you MUST update the `COMMANDS` dictionary in `clawcat/bot.py`. This dictionary is the single source of truth for the `/commands` command output.

```python
# In ClawCatBot class
COMMANDS = {
    "command_name": "Description of what this command does",
    ...
}
```

Also ensure:
1. Add the command handler method (`cmd_<name>`)
2. Register the handler in `build_application()`
3. Update `COMMANDS` dictionary

### Session Storage

Sessions are stored as JSON files in `{working_dir}/ClawCat_sessions/`. Each session file is named by its Claude session ID.

### Configuration

- Config is loaded from `config.yaml`
- Never commit `config.yaml` (contains secrets)
- Update `config.example.yaml` when adding new options

## Running

```powershell
# Console mode
python run.py

# As Windows service
python install_service.py install
python install_service.py start
```
