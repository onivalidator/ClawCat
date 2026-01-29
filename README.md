# ClawCat

Telegram Remote Control for Claude Code CLI.

Control Claude Code on your Windows machine from anywhere via Telegram.

## Features

- Send instructions to Claude Code remotely via Telegram
- Check Claude status and availability
- Cancel running tasks
- Run as Windows service for always-on operation
- Single-user security model

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
cd C:\Users\kevin\ClaudeWorkspace\ClawCat
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

claude:
  executable: "C:\\Users\\kevin\\.local\\bin\\claude.exe"
  working_dir: "C:\\Users\\kevin"
  timeout_seconds: 300
  model: "sonnet"
```

### 5. Test in Console Mode

```powershell
python run.py
```

Send `/start` to your bot in Telegram to verify it works.

## Usage

### Bot Commands

- `/start` - Welcome message and help
- `/status` - Check Claude CLI availability
- `/cancel` - Cancel a running task

### Sending Instructions

Just send any text message to the bot. It will be passed to Claude Code as an instruction.

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

Logs are written to: `C:\Users\kevin\ClaudeLogs\clawcat-service.log`

## Security

- **Single user only**: Only your Telegram user ID can use the bot
- **Local execution**: Bot runs on your machine, no cloud component
- **No permission bypass**: Claude runs with normal user permissions
- **Protect config.yaml**: Contains your bot token (keep it private)

## Troubleshooting

### Bot not responding

1. Check if the bot is running (`python run.py`)
2. Verify your bot token is correct
3. Check that your user ID matches

### Claude commands failing

1. Run `/status` to check Claude availability
2. Verify the Claude CLI path in config.yaml
3. Check Claude CLI works directly: `claude --version`

### Service won't start

1. Check logs: `C:\Users\kevin\ClaudeLogs\clawcat-service.log`
2. Verify config.yaml exists in the ClawCat directory
3. Make sure Python and dependencies are installed
