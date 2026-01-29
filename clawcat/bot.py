"""Telegram bot handler for ClawCat."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from .config import Config
from .claude_runner import ClaudeRunner, RunStatus


logger = logging.getLogger(__name__)

# Maximum message length for Telegram
MAX_MESSAGE_LENGTH = 4096


class ClawCatBot:
    """Telegram bot for remote Claude Code control."""

    def __init__(self, config: Config):
        """Initialize the bot.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.runner = ClaudeRunner(config.claude)
        self.application: Optional[Application] = None

    def _is_authorized(self, user_id: int) -> bool:
        """Check if a user is authorized to use the bot.

        Args:
            user_id: Telegram user ID.

        Returns:
            True if authorized.
        """
        return user_id == self.config.telegram.authorized_user_id

    async def _check_auth(self, update: Update) -> bool:
        """Check authorization and send error if not authorized.

        Args:
            update: Telegram update.

        Returns:
            True if authorized, False otherwise.
        """
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            logger.warning(f"Unauthorized access attempt from user ID: {user_id}")
            await update.message.reply_text(
                "Unauthorized. This bot is configured for a specific user only."
            )
            return False
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not await self._check_auth(update):
            return

        await update.message.reply_text(
            "Welcome to ClawCat!\n\n"
            "I'm your remote interface to Claude Code.\n\n"
            "Commands:\n"
            "/status - Check if Claude is available\n"
            "/cancel - Cancel running task\n\n"
            "Just send me any message and I'll pass it to Claude Code."
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not await self._check_auth(update):
            return

        is_available = self.runner.is_available()
        is_running = self.runner.is_running

        status_parts = []

        if is_available:
            status_parts.append("Claude CLI: Available")
        else:
            status_parts.append("Claude CLI: NOT AVAILABLE")

        if is_running:
            status_parts.append("Current task: Running")
        else:
            status_parts.append("Current task: None")

        status_parts.append(f"Working directory: {self.config.claude.working_dir}")
        status_parts.append(f"Model: {self.config.claude.model}")
        status_parts.append(f"Timeout: {self.config.claude.timeout_seconds}s")

        await update.message.reply_text("\n".join(status_parts))

    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command."""
        if not await self._check_auth(update):
            return

        cancelled = await self.runner.cancel()

        if cancelled:
            await update.message.reply_text("Task cancelled.")
        else:
            await update.message.reply_text("No task is currently running.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages as Claude instructions."""
        if not await self._check_auth(update):
            return

        instruction = update.message.text

        if not instruction or not instruction.strip():
            await update.message.reply_text("Please send an instruction for Claude.")
            return

        # Send "working" indicator
        working_msg = await update.message.reply_text("Working...")

        try:
            # Run the instruction
            result = await self.runner.run(instruction)

            # Delete the "working" message
            await working_msg.delete()

            # Format and send response
            await self._send_result(update, result)

        except Exception as e:
            logger.exception("Error handling message")
            await working_msg.edit_text(f"Error: {str(e)}")

    async def _send_result(self, update: Update, result) -> None:
        """Send a run result to the user.

        Args:
            update: Telegram update.
            result: RunResult from Claude execution.
        """
        # Build response message
        parts = []

        # Status indicator
        status_emoji = {
            RunStatus.SUCCESS: "",
            RunStatus.ERROR: "[ERROR] ",
            RunStatus.TIMEOUT: "[TIMEOUT] ",
            RunStatus.CANCELLED: "[CANCELLED] ",
        }

        prefix = status_emoji.get(result.status, "")

        # Main content
        if result.output:
            parts.append(f"{prefix}{result.output}")
        elif result.error:
            parts.append(f"{prefix}{result.error}")
        else:
            parts.append(f"{prefix}No output.")

        # Error details (if separate from output)
        if result.error and result.output:
            parts.append(f"\nError: {result.error}")

        # Cost info (if available)
        if result.cost_usd is not None:
            parts.append(f"\n[Cost: ${result.cost_usd:.4f}]")

        message = "\n".join(parts)

        # Split long messages
        await self._send_long_message(update, message)

    async def _send_long_message(self, update: Update, text: str) -> None:
        """Send a message, splitting if necessary.

        Args:
            update: Telegram update.
            text: Message text to send.
        """
        # If message fits in one chunk, send it
        if len(text) <= MAX_MESSAGE_LENGTH:
            await update.message.reply_text(text)
            return

        # Split into chunks
        chunks = []
        current = ""

        for line in text.split("\n"):
            # If adding this line would exceed limit
            if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH - 20:  # Leave room for "[x/y]"
                if current:
                    chunks.append(current)
                current = line
            else:
                if current:
                    current += "\n" + line
                else:
                    current = line

        if current:
            chunks.append(current)

        # Send chunks
        total = len(chunks)
        for i, chunk in enumerate(chunks, 1):
            header = f"[{i}/{total}]\n" if total > 1 else ""
            await update.message.reply_text(header + chunk)

    def build_application(self) -> Application:
        """Build the Telegram application.

        Returns:
            Configured Application instance.
        """
        self.application = (
            Application.builder()
            .token(self.config.telegram.bot_token)
            .build()
        )

        # Add handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("cancel", self.cmd_cancel))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        return self.application

    def run(self) -> None:
        """Run the bot (blocking)."""
        app = self.build_application()
        logger.info("Starting ClawCat bot...")
        app.run_polling(drop_pending_updates=True)
