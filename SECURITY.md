# Security Policy

ClawCat turns Telegram messages into local coding-agent tasks. Treat any
deployment as sensitive automation.

## Supported Versions

Security fixes target the current `master` branch until the project adopts
versioned releases.

## Threat Model

Primary risks:

- Compromise of the Telegram bot token
- Unauthorized Telegram user access
- Prompted local agents modifying sensitive files
- Full-access execution on a machine with broad credentials
- Accidental leakage of workspace/session data in logs

Built-in controls:

- One configured Telegram user ID
- No OpenAI API key stored by ClawCat
- Codex CLI uses local auth and config
- Read-only sandbox by default
- Full-access mode hidden unless explicitly enabled
- `config.yaml` ignored by git

## Safe Deployment Checklist

- Use a dedicated Telegram bot token.
- Keep `config.yaml` private and readable only by the service user.
- Point `agent.working_dir` at a dedicated repository or workspace.
- Start with `sandbox_mode: "read-only"`.
- Move to `workspace-write` only when the repository has a clean git history.
- Do not enable `allow_dangerous_mode` on a personal machine.
- Rotate the Telegram bot token immediately if the config is exposed.

## Reporting a Vulnerability

Open a private security advisory on GitHub if available. If not, contact the
maintainer through the GitHub profile before posting public details.
