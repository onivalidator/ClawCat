# ClawCat

ClawCat is a single-user Telegram controller for local coding-agent CLIs. The
public-ready path is centered on Codex/OpenAI-compatible workflows: a trusted
user can send a task from Telegram, ClawCat runs the local Codex CLI in a
configured workspace, and the final answer comes back to Telegram.

The bot stores no OpenAI API key. It relies on the local Codex CLI auth and
config already present on the machine.

## Why This Exists

Maintainers often need to check a build, triage a small bug, or start a coding
agent while away from the keyboard. ClawCat keeps that workflow local and
auditable instead of forwarding broad shell access to a hosted bot.

## Features

- Telegram command surface for one authorized user
- Codex CLI provider by default
- Legacy Claude CLI provider for existing private installs
- Read-only sandbox by default for remote tasks
- Optional workspace-write mode for controlled edits
- Full-access mode hidden unless explicitly enabled in config
- Session nicknames, pause/resume metadata, and cancellation
- Optional local monitor window for desktop/server visibility
- Windows service helper for always-on use
- macOS/Linux console mode support

## Safety Model

ClawCat is intentionally conservative by default:

- The bot only accepts commands from `telegram.authorized_user_id`.
- Codex runs locally with your existing Codex auth; no API key is stored in
  `config.yaml`.
- `sandbox_mode` defaults to `read-only`.
- ClawCat uses `codex exec`, Codex's non-interactive command path, rather than
  an interactive terminal session.
- Full-access mode is not shown in Telegram unless
  `agent.allow_dangerous_mode: true`.
- Keep `config.yaml` private because it contains the Telegram bot token.

Remote access to a coding agent is still powerful. Use a dedicated workspace
with a clean git history and avoid pointing ClawCat at sensitive directories.

## Setup

### 1. Install Requirements

```powershell
pip install -r requirements.txt
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install and authenticate the Codex CLI on the same machine:

```powershell
codex --version
codex login
```

### 2. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts.
3. Copy the bot token.

### 3. Get Your Telegram User ID

Message [@userinfobot](https://t.me/userinfobot). It will return a numeric user
ID.

### 4. Configure ClawCat

```powershell
copy config.example.yaml config.yaml
```

On macOS or Linux:

```bash
cp config.example.yaml config.yaml
```

Minimal Codex configuration:

```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  authorized_user_id: 123456789

agent:
  provider: "codex"
  executable: "codex"
  working_dir: "C:\\Users\\YOUR_USER\\ClawCatWorkspace"
  timeout_seconds: 300
  model: null
  sandbox_mode: "read-only"
  allow_dangerous_mode: false
```

macOS example:

```yaml
agent:
  provider: "codex"
  executable: "codex"
  working_dir: "/Users/YOUR_USER/ClawCatWorkspace"
  sandbox_mode: "read-only"
  allow_dangerous_mode: false
```

Use `sandbox_mode: "workspace-write"` when you want Codex to edit files in the
configured workspace.

### 5. Run in Console Mode

```powershell
python run.py
```

On macOS or Linux:

```bash
python3 run.py
```

Send `/start` to the Telegram bot.

## Commands

- `/start` - Welcome and quick status
- `/commands` - Command list
- `/status` - CLI availability, config, and session info
- `/model` - Select one of the configured models
- `/newsession` - Start a safe session
- `/nickname <name>` - Name the active session
- `/pause` - Save active session metadata
- `/listsessions` - List saved sessions
- `/loadsession <name or id>` - Resume saved session metadata
- `/cancel` - Stop the current run

Any non-command text is sent to the configured local agent.

## Tests

```bash
python -m unittest discover -s tests
```

The current tests cover safe Codex defaults, dangerous-mode gating, command
construction, and config validation.

## Provider Notes

### Codex

Codex is the default provider. ClawCat runs:

```text
codex exec --sandbox <mode> --output-last-message <file> "<prompt>"
```

For safety, ClawCat starts a fresh non-interactive Codex run for each Telegram
task. The current `codex exec resume` path does not expose the same sandbox
flags, so ClawCat does not use it for remote execution.

### Claude Legacy Mode

Existing private installs can still use:

```yaml
agent:
  provider: "claude"
  executable: "C:\\Users\\YOUR_USER\\.local\\bin\\claude.exe"
  model: "sonnet"
```

New public deployments should prefer Codex.

## Running as a Windows Service

Windows service mode is optional. Run as Administrator:

```powershell
python install_service.py
```

Service commands:

```powershell
net start ClawCat
net stop ClawCat
python install_service.py --remove
```

Set `CLAWCAT_LOG_DIR` to choose where service logs are written. The default is
`C:\ClawCatLogs`.

On macOS and Linux, use a process manager such as `launchd`, `systemd`, or
`tmux` around `python3 run.py`; the Windows service installer intentionally
does nothing on non-Windows platforms.

## Public Release Checklist

- Keep `config.yaml` out of git.
- Use a dedicated workspace.
- Start with `read-only` sandboxing.
- Add repository-specific operating notes before enabling `workspace-write`.
- Do not enable full-access mode on a machine with broad personal credentials.
