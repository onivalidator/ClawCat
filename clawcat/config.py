"""Configuration management for ClawCat."""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import yaml


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str
    authorized_user_id: int


@dataclass
class AgentConfig:
    """Codex CLI configuration."""
    executable: str
    working_dir: str
    timeout_seconds: int
    model: str


@dataclass
class Config:
    """Main configuration container."""
    telegram: TelegramConfig
    agent: AgentConfig


class ConfigError(Exception):
    """Configuration error."""
    pass


def find_config_file() -> Path:
    """Find the config.yaml file.

    Search order:
    1. CLAWCAT_CONFIG environment variable
    2. ./config.yaml (current directory)
    3. Script directory/config.yaml
    """
    # Check environment variable
    env_path = os.environ.get("CLAWCAT_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise ConfigError(f"Config file specified in CLAWCAT_CONFIG not found: {env_path}")

    # Check current directory
    cwd_config = Path("config.yaml")
    if cwd_config.exists():
        return cwd_config

    # Check script directory
    script_dir = Path(__file__).parent.parent
    script_config = script_dir / "config.yaml"
    if script_config.exists():
        return script_config

    raise ConfigError(
        "Config file not found. Create config.yaml or set CLAWCAT_CONFIG environment variable."
    )


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load and validate configuration from YAML file.

    Args:
        config_path: Optional path to config file. If None, searches default locations.

    Returns:
        Validated Config object.

    Raises:
        ConfigError: If config is missing or invalid.
    """
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

    # Validate telegram section
    telegram_raw = raw.get("telegram")
    if not telegram_raw:
        raise ConfigError("Missing 'telegram' section in config")

    bot_token = telegram_raw.get("bot_token")
    if not bot_token or not isinstance(bot_token, str):
        raise ConfigError("Missing or invalid 'telegram.bot_token'")

    authorized_user_id = telegram_raw.get("authorized_user_id")
    if not authorized_user_id or not isinstance(authorized_user_id, int):
        raise ConfigError("Missing or invalid 'telegram.authorized_user_id' (must be integer)")

    telegram_config = TelegramConfig(
        bot_token=bot_token,
        authorized_user_id=authorized_user_id
    )

    # Validate codex section
    agent_raw = raw.get("codex", {})

    # Default Codex executable path
    default_executable = r"codex"
    executable = agent_raw.get("executable", default_executable)

    # Default working directory
    default_working_dir = r"C:\ClawCat\Workspace"
    working_dir = agent_raw.get("working_dir", default_working_dir)

    # Default timeout (5 minutes)
    timeout_seconds = agent_raw.get("timeout_seconds", 300)
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise ConfigError("'codex.timeout_seconds' must be a positive integer")

    # Default model
    model = agent_raw.get("model", "gpt-5.1")

    codex_config = AgentConfig(
        executable=executable,
        working_dir=working_dir,
        timeout_seconds=timeout_seconds,
        model=model
    )

    return Config(telegram=telegram_config, codex=codex_config)
