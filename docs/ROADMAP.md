# Roadmap

ClawCat's direction is a safer remote controller for local Codex workflows. The
goal is not to host an agent in the cloud; it is to let a maintainer trigger
bounded local Codex tasks from Telegram while preserving a reviewable local
development loop.

## Current Position

- Codex is the default provider.
- The app stores no OpenAI API key.
- Codex runs through the authenticated local CLI.
- Remote runs default to read-only sandboxing.
- macOS/Linux console mode and Windows service mode are both supported.
- Unit tests cover the core safety defaults.

## Why It Fits Maintenance Work

Maintainers often need to triage issues, run a small investigation, or queue a
bounded coding-agent task away from the workstation. ClawCat creates a narrow
control plane for that workflow without exposing SSH or a general shell bot.

## Near-Term Work

- Add structured audit logs for each Telegram-triggered run.
- Add optional per-repository command policies.
- Add a dry-run mode that summarizes intended filesystem writes.
- Add richer Codex event parsing for thread IDs and usage summaries.
- Add packaging instructions for `launchd` and `systemd`.

## Non-Goals

- Multi-user bot hosting
- Arbitrary shell command execution
- Cloud-hosted agent orchestration
- Storing OpenAI API keys in ClawCat config
