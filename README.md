# ClawCat

Telegram Remote Control for Codex CLI.

Control Codex on your Windows machine from anywhere via Telegram.

## Features

- Send instructions to Codex remotely via Telegram
- Check Codex status and availability
- Cancel running tasks
- Run as Windows service for always-on operation
- Single-user security model
- Model selection (GPT-5.1 Codex, GPT-5.1, GPT-5)
- Session management with conversation continuity
- Dangerous mode for unrestricted execution

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:ABCdefGHI...`)

### 2. Get Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot)
2. It will reply with your user ID (a number like `123456789`)

### 3. Install Dependencies

```powershell
cd C:\ClawCat\Workspace
pip install -r requirements.txt
```

### 4. Create Configuration

```powershell
copy config.example.yaml config.yaml
```

Edit `config.yaml` with your bot token and user ID:

```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  authorized_user_id: YOUR_USER_ID

agent:
  executable: "codex"
  working_dir: "C:\\ClawCat\\Workspace"
  timeout_seconds: 300
  model: "gpt-5.1-codex"  # gpt-5.1-codex (default), gpt-5.1, or gpt-5
```

### 5. Test in Console Mode

```powershell
python run.py
```

Send `/start` to your bot in Telegram to verify it works.

## Usage

### Bot Commands

- `/start` - Welcome message and help
- `/status` - Check Codex CLI availability and session info
- `/model` - Select AI model (GPT-5.1 Codex, GPT-5.1, GPT-5)
- `/newsession` - Start a new session (normal or dangerous mode)
- `/cancel` - Cancel a running task

### Available Models

| Model | Description |
|-------|-------------|
| `gpt-5.1-codex` | **GPT-5.1 Codex** (gpt-5.1-codex) - State-of-the-art software engineering (default) |
| `gpt-5.1` | **GPT-5.1** (gpt-5.1) - Fast daily coding tasks |
| `gpt-5` | **GPT-5** (gpt-5) - Fastest, high-frequency tasks |

### Sending Instructions

Just send any text message to the bot. It will be passed to Codex as an instruction.

Examples:
- "What is 2+2?"
- "List the files in my Documents folder"
- "Create a simple Python script that prints hello world"

## Running as a Windows Service

For always-on operation, install ClawCat as a Windows service:

### Install Service

Run as Administrator:

```powershell
python install_service.py
```

### Service Commands

```powershell
# Start the service
net start ClawCat

# Stop the service
net stop ClawCat

# Remove the service
python install_service.py --remove
```

### Service Logs

Logs are written to: `C:\ClawCat\Logs\clawcat-service.log`

## Security

- **Single user only**: Only your Telegram user ID can use the bot
- **Local execution**: Bot runs on your machine, no cloud component
- **No permission bypass**: Codex runs with normal user permissions
- **Protect config.yaml**: Contains your bot token (keep it private)

## Troubleshooting

### Bot not responding

1. Check if the bot is running (`python run.py`)
2. Verify your bot token is correct
3. Check that your user ID matches

### Codex commands failing

1. Run `/status` to check Codex availability
2. Verify the Codex CLI path in config.yaml
3. Check Codex CLI works directly: `codex --version`

### Service won't start

1. Check logs: `C:\ClawCat\Logs\clawcat-service.log`
2. Verify config.yaml exists in the ClawCat directory
3. Make sure Python and dependencies are installed
