"""Configuration management for ClawCat."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


class ConfigError(Exception):
    """Configuration error."""


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""

    bot_token: str
    authorized_user_id: int


@dataclass
class AgentConfig:
    """Local coding-agent CLI configuration."""

    provider: str
    executable: str
    working_dir: str
    timeout_seconds: int
    model: Optional[str] = None
    models: list[str] = field(default_factory=list)
    sandbox_mode: str = "read-only"
    allow_dangerous_mode: bool = False
    open_monitor_window: bool = False
    visible_terminal: bool = False
    skip_git_repo_check: bool = False


# Backwards-compatible alias for older imports/config language.
ClaudeConfig = AgentConfig


@dataclass
class Config:
    """Main configuration container."""

    telegram: TelegramConfig
    agent: AgentConfig

    @property
    def claude(self) -> AgentConfig:
        """Legacy accessor for older code paths."""
        return self.agent


def find_config_file() -> Path:
    """Find the config.yaml file.

    Search order:
    1. CLAWCAT_CONFIG environment variable
    2. ./config.yaml (current directory)
    3. Script directory/config.yaml
    """
    env_path = os.environ.get("CLAWCAT_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise ConfigError(f"Config file specified in CLAWCAT_CONFIG not found: {env_path}")

    cwd_config = Path("config.yaml")
    if cwd_config.exists():
        return cwd_config

    script_dir = Path(__file__).parent.parent
    script_config = script_dir / "config.yaml"
    if script_config.exists():
        return script_config

    raise ConfigError(
        "Config file not found. Create config.yaml or set CLAWCAT_CONFIG environment variable."
    )


def _require_bool(raw: dict, key: str, default: bool, section: str) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"'{section}.{key}' must be a boolean")
    return value


def _load_agent_config(raw: dict) -> AgentConfig:
    """Load agent config, accepting both new `agent` and legacy `claude` sections."""
    agent_raw = raw.get("agent")
    legacy_claude_raw = raw.get("claude")

    if agent_raw and legacy_claude_raw:
        raise ConfigError("Use either 'agent' or legacy 'claude' config, not both")

    if agent_raw is None:
        agent_raw = legacy_claude_raw or {}
        default_provider = "claude" if legacy_claude_raw is not None else "codex"
    else:
        default_provider = "codex"

    if not isinstance(agent_raw, dict):
        raise ConfigError("'agent' section must be a YAML dictionary")

    provider = str(agent_raw.get("provider", default_provider)).lower().strip()
    if provider not in {"codex", "claude"}:
        raise ConfigError("'agent.provider' must be either 'codex' or 'claude'")

    if provider == "codex":
        default_executable = "codex"
        default_model = None
        default_models = ["default", "gpt-5.1-codex", "gpt-5.1", "gpt-5"]
    else:
        default_executable = "claude"
        default_model = "opus"
        default_models = ["opus", "sonnet", "haiku"]

    executable = str(agent_raw.get("executable", default_executable))
    working_dir = str(agent_raw.get("working_dir", str(Path.home())))

    timeout_seconds = agent_raw.get("timeout_seconds", 300)
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise ConfigError("'agent.timeout_seconds' must be a positive integer")

    raw_model = agent_raw.get("model", default_model)
    model = str(raw_model).strip() if raw_model not in (None, "") else None

    models = agent_raw.get("models", default_models)
    if not isinstance(models, list) or not all(isinstance(item, str) for item in models):
        raise ConfigError("'agent.models' must be a list of strings")
    if model and model not in models:
        models = [model] + models

    sandbox_mode = str(agent_raw.get("sandbox_mode", "read-only")).strip()
    if sandbox_mode not in {"read-only", "workspace-write", "danger-full-access"}:
        raise ConfigError(
            "'agent.sandbox_mode' must be read-only, workspace-write, or danger-full-access"
        )

    section_name = "agent"
    allow_dangerous_mode = _require_bool(agent_raw, "allow_dangerous_mode", False, section_name)
    open_monitor_window = _require_bool(agent_raw, "open_monitor_window", False, section_name)
    visible_terminal = _require_bool(agent_raw, "visible_terminal", False, section_name)
    skip_git_repo_check = _require_bool(agent_raw, "skip_git_repo_check", False, section_name)

    if sandbox_mode == "danger-full-access" and not allow_dangerous_mode:
        raise ConfigError(
            "'agent.sandbox_mode: danger-full-access' requires 'allow_dangerous_mode: true'"
        )

    return AgentConfig(
        provider=provider,
        executable=executable,
        working_dir=working_dir,
        timeout_seconds=timeout_seconds,
        model=model,
        models=models,
        sandbox_mode=sandbox_mode,
        allow_dangerous_mode=allow_dangerous_mode,
        open_monitor_window=open_monitor_window,
        visible_terminal=visible_terminal,
        skip_git_repo_check=skip_git_repo_check,
    )


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load and validate configuration from YAML file."""
    if config_path is None:
        config_path = find_config_file()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {e}")
    except IOError as e:
        raise ConfigError(f"Cannot read config file: {e}")

    if not isinstance(raw, dict):
        raise ConfigError("Config file must be a YAML dictionary")

    telegram_raw = raw.get("telegram")
    if not telegram_raw or not isinstance(telegram_raw, dict):
        raise ConfigError("Missing or invalid 'telegram' section in config")

    bot_token = telegram_raw.get("bot_token")
    if not bot_token or not isinstance(bot_token, str):
        raise ConfigError("Missing or invalid 'telegram.bot_token'")

    authorized_user_id = telegram_raw.get("authorized_user_id")
    if not authorized_user_id or not isinstance(authorized_user_id, int):
        raise ConfigError("Missing or invalid 'telegram.authorized_user_id' (must be integer)")

    return Config(
        telegram=TelegramConfig(
            bot_token=bot_token,
            authorized_user_id=authorized_user_id,
        ),
        agent=_load_agent_config(raw),
    )
