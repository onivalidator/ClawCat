#!/usr/bin/env python3
"""Console entry point for ClawCat."""

import logging
import sys
from pathlib import Path

from clawcat.config import load_config, ConfigError
from clawcat.bot import ClawCatBot


def setup_logging():
    """Configure logging for console mode."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    print("ClawCat - Telegram Remote Control for Claude Code")
    print("=" * 50)

    try:
        # Load configuration
        config_path = None
        if len(sys.argv) > 1:
            config_path = Path(sys.argv[1])
            print(f"Using config file: {config_path}")

        config = load_config(config_path)
        print("Configuration loaded successfully")
        print(f"  Working directory: {config.claude.working_dir}")
        print(f"  Model: {config.claude.model}")
        print(f"  Timeout: {config.claude.timeout_seconds}s")
        print()

        # Create bot
        bot = ClawCatBot(config)

        # Check Claude availability
        if bot.runner.is_available():
            print("Claude CLI: Available")
        else:
            print("WARNING: Claude CLI not available!")
            print(f"  Expected at: {config.claude.executable}")

        print()
        print("Starting bot... Press Ctrl+C to stop.")
        print()

        # Run the bot
        bot.run()

    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\nConfiguration error: {e}")
        print("\nMake sure you have a config.yaml file with:")
        print("  telegram:")
        print("    bot_token: YOUR_BOT_TOKEN")
        print("    authorized_user_id: YOUR_TELEGRAM_ID")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        logger.exception("Fatal error")
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
