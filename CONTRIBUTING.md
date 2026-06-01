# Contributing

ClawCat is a small remote-control surface for local coding agents. Contributions
should keep that scope tight: single-user Telegram control, local CLI execution,
and conservative security defaults.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests
```

On Windows, use PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests
```

## Development Rules

- Keep Codex as the public default provider.
- Keep remote runs sandboxed by default.
- Do not expose full-access mode unless a config flag explicitly opts in.
- Do not commit `config.yaml`, bot tokens, API keys, session logs, or local
  workspace data.
- Avoid provider-specific code in the Telegram command layer; put provider
  behavior in the runner layer.
- Preserve macOS/Linux console mode when touching Windows service behavior.

## Commit Style

Use human maintainer-style commits with a clear scope and reason. Good examples:

- `Keep Codex runs sandboxed by default`
- `Add macOS-safe service fallback`
- `Document remote agent threat model`

Avoid generated-looking messages, broad "update files" commits, or tool
trailers unless maintainers explicitly request them.

## Pull Requests

PRs should include:

- What changed
- Why the security posture is still safe
- What validation was run
- Any platform-specific behavior touched
