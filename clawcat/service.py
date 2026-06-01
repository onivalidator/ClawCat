"""Windows service wrapper for ClawCat."""

import asyncio
import logging
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
else:
    servicemanager = None
    win32event = None
    win32service = None
    win32serviceutil = None

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from clawcat.config import load_config, ConfigError
from clawcat.bot import ClawCatBot


# Service configuration
SERVICE_NAME = "ClawCat"
SERVICE_DISPLAY_NAME = "ClawCat - Telegram Remote Control"
SERVICE_DESCRIPTION = "Telegram bot for remote control of local coding-agent CLIs"

# Log file location
LOG_DIR = Path(os.environ.get("CLAWCAT_LOG_DIR", r"C:\ClawCatLogs"))
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


if sys.platform == "win32":

    class ClawCatService(win32serviceutil.ServiceFramework):
        """Windows service wrapper for ClawCat bot."""

        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            """Initialize the service."""
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.win32_stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.bot = None
            self.loop = None
            self.async_stop_event = None

        def SvcStop(self):
            """Handle service stop request."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            logging.info("Service stop requested")

            # Signal the asyncio stop event.
            if self.loop and self.async_stop_event:
                self.loop.call_soon_threadsafe(self.async_stop_event.set)

            win32event.SetEvent(self.win32_stop_event)

        def SvcDoRun(self):
            """Main service entry point."""
            setup_logging()
            logging.info("ClawCat service starting...")

            try:
                # Load configuration.
                config = load_config()
                logging.info("Configuration loaded successfully")

                # Create bot.
                self.bot = ClawCatBot(config)
                logging.info("Starting Telegram bot...")

                # Use SelectorEventLoop to avoid signal.set_wakeup_fd in service threads.
                self.loop = asyncio.SelectorEventLoop()
                asyncio.set_event_loop(self.loop)

                self.async_stop_event = asyncio.Event()
                self.loop.run_until_complete(self.bot.run_async(self.async_stop_event))

            except ConfigError as e:
                logging.error(f"Configuration error: {e}")
                servicemanager.LogErrorMsg(f"ClawCat configuration error: {e}")
            except Exception as e:
                logging.exception("Service error")
                servicemanager.LogErrorMsg(f"ClawCat error: {e}")
            finally:
                if self.loop:
                    self.loop.close()

            logging.info("ClawCat service stopped")
else:

    class ClawCatService:
        """Placeholder on non-Windows platforms."""


def main():
    """Entry point for service installation/control."""
    if sys.platform != "win32":
        print("ClawCat Windows service mode is only available on Windows.")
        print("On macOS or Linux, run console mode with: python run.py")
        return

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
