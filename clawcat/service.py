"""Windows service wrapper for ClawCat."""

import logging
import os
import sys
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from clawcat.config import load_config, ConfigError
from clawcat.bot import ClawCatBot


# Service configuration
SERVICE_NAME = "ClawCat"
SERVICE_DISPLAY_NAME = "ClawCat - Telegram Remote Control"
SERVICE_DESCRIPTION = "Telegram bot for remote control of Claude Code CLI"

# Log file location
LOG_DIR = Path(r"C:\Users\kevin\ClaudeLogs")
LOG_FILE = LOG_DIR / "clawcat-service.log"


def setup_logging():
    """Configure logging for the service."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ]
    )


class ClawCatService(win32serviceutil.ServiceFramework):
    """Windows service wrapper for ClawCat bot."""

    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        """Initialize the service."""
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.bot = None

    def SvcStop(self):
        """Handle service stop request."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

        # Stop the bot if running
        if self.bot and self.bot.application:
            try:
                self.bot.application.stop()
            except Exception as e:
                logging.error(f"Error stopping bot: {e}")

        logging.info("Service stop requested")

    def SvcDoRun(self):
        """Main service entry point."""
        setup_logging()
        logging.info("ClawCat service starting...")

        try:
            # Load configuration
            config = load_config()
            logging.info("Configuration loaded successfully")

            # Create and run bot
            self.bot = ClawCatBot(config)
            logging.info("Starting Telegram bot...")

            # Run the bot (this blocks until stopped)
            self.bot.run()

        except ConfigError as e:
            logging.error(f"Configuration error: {e}")
            servicemanager.LogErrorMsg(f"ClawCat configuration error: {e}")
        except Exception as e:
            logging.exception("Service error")
            servicemanager.LogErrorMsg(f"ClawCat error: {e}")

        logging.info("ClawCat service stopped")


def main():
    """Entry point for service installation/control."""
    if len(sys.argv) == 1:
        # Running as service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ClawCatService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Command line control (install, remove, start, stop, etc.)
        win32serviceutil.HandleCommandLine(ClawCatService)


if __name__ == "__main__":
    main()
