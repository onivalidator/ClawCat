"""Telegram bot handler for ClawCat."""

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from .config import Config
from .claude_runner import ClaudeRunner, RunStatus, AVAILABLE_MODELS, MODEL_DESCRIPTIONS, MODEL_IDENTIFIERS


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

    # Command descriptions - update this when adding/changing commands
    COMMANDS = {
        "start": "Welcome message and quick help",
        "commands": "List all commands with descriptions",
        "status": "Check CLI status and current session info",
        "model": "Select AI model (opus/sonnet/haiku)",
        "newsession": "Start a new Claude session",
        "nickname <name>": "Set a nickname for current session",
        "pause": "Save current session to disk",
        "listsessions": "Show all saved sessions",
        "loadsession <name>": "Resume a saved session by name or ID",
        "cancel": "Cancel the currently running task",
    }

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not await self._check_auth(update):
            return

        version = self.runner.get_version() or "Unknown"

        await update.message.reply_text(
            f"Welcome to ClawCat!\n\n"
            f"Remote interface to Claude Code CLI.\n"
            f"CLI Version: {version}\n\n"
            f"Use /commands to see all available commands.\n\n"
            f"Send any message to execute via Claude CLI."
        )

    async def cmd_commands(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /commands command - list all commands."""
        if not await self._check_auth(update):
            return

        lines = ["Available Commands:", ""]
        for cmd, desc in self.COMMANDS.items():
            lines.append(f"  /{cmd} - {desc}")

        await update.message.reply_text("\n".join(lines))

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not await self._check_auth(update):
            return

        version = self.runner.get_version()
        is_running = self.runner.is_running

        status_parts = []

        if version:
            status_parts.append(f"Claude CLI: {version}")
        else:
            status_parts.append("Claude CLI: NOT AVAILABLE")

        status_parts.append(f"Working directory: {self.config.claude.working_dir}")
        status_parts.append(f"Timeout: {self.config.claude.timeout_seconds}s")
        status_parts.append("")

        # Session info
        session_info = self.runner.get_session_info()
        status_parts.append(session_info)

        if is_running:
            status_parts.append("\n[Task currently running]")

        await update.message.reply_text("\n".join(status_parts))

    async def cmd_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /model command - show model selection."""
        if not await self._check_auth(update):
            return

        current = self.runner.current_model
        session = self.runner.active_session

        # Build inline keyboard with model descriptions
        buttons = []
        for model in AVAILABLE_MODELS:
            desc = MODEL_DESCRIPTIONS.get(model, model)
            if model == current:
                label = f"* {desc}"
            else:
                label = desc
            buttons.append([InlineKeyboardButton(label, callback_data=f"model:{model}")])

        keyboard = InlineKeyboardMarkup(buttons)

        session_note = ""
        if session:
            session_note = f"\n\nNote: Current session uses {session.model}. New model applies to new sessions."

        await update.message.reply_text(
            f"Select model:{session_note}",
            reply_markup=keyboard
        )

    async def cmd_newsession(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /newsession command - start a new session."""
        if not await self._check_auth(update):
            return

        # Build inline keyboard for session options
        buttons = [
            [InlineKeyboardButton("Normal session", callback_data="session:normal")],
            [InlineKeyboardButton("Dangerous mode (skip permissions)", callback_data="session:dangerous")],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        await update.message.reply_text(
            f"Start new session with model: {self.runner.current_model}\n\n"
            f"Choose mode:",
            reply_markup=keyboard
        )

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        if not self._is_authorized(user_id):
            await query.edit_message_text("Unauthorized.")
            return

        data = query.data

        if data.startswith("model:"):
            # Model selection
            model = data.split(":")[1]
            if model in AVAILABLE_MODELS:
                self.runner.current_model = model
                desc = MODEL_DESCRIPTIONS.get(model, model)
                model_id = MODEL_IDENTIFIERS.get(model, model)
                await query.edit_message_text(
                    f"Model set to: {desc}\n"
                    f"Identifier: {model_id}"
                )
            else:
                await query.edit_message_text(f"Unknown model: {model}")

        elif data.startswith("session:"):
            # New session
            mode = data.split(":")[1]
            dangerous = (mode == "dangerous")

            session = self.runner.create_session(dangerous_mode=dangerous)

            mode_str = "DANGEROUS MODE" if dangerous else "normal mode"
            await query.edit_message_text(
                f"New session created!\n\n"
                f"Session ID: {session.id}\n"
                f"Model: {session.model}\n"
                f"Mode: {mode_str}\n\n"
                f"Send a message to start."
            )

    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command."""
        if not await self._check_auth(update):
            return

        cancelled = await self.runner.cancel()

        if cancelled:
            await update.message.reply_text("Task cancelled.")
        else:
            await update.message.reply_text("No task is currently running.")

    async def cmd_nickname(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /nickname command - set a name for the current session."""
        if not await self._check_auth(update):
            return

        session = self.runner.active_session
        if not session:
            await update.message.reply_text(
                "No active session. Start one with /newsession first."
            )
            return

        # Get nickname from command args
        if context.args:
            nickname = " ".join(context.args)
            session.nickname = nickname
            await update.message.reply_text(f"Session nicknamed: {nickname}")
        else:
            current = session.nickname or "(none)"
            await update.message.reply_text(
                f"Current nickname: {current}\n\n"
                f"Usage: /nickname <name>"
            )

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pause command - save current session to disk."""
        if not await self._check_auth(update):
            return

        session = self.runner.pause_session()
        if session:
            name = session.display_name
            await update.message.reply_text(
                f"Session paused and saved: {name}\n"
                f"Model: {session.model}\n"
                f"Messages: {session.message_count}\n\n"
                f"Use /listsessions to see saved sessions."
            )
        else:
            await update.message.reply_text(
                "No active session to pause, or session has no ID yet.\n"
                "Send at least one message to establish a session ID."
            )

    async def cmd_listsessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /listsessions command - show all saved sessions."""
        if not await self._check_auth(update):
            return

        sessions = self.runner.list_saved_sessions()

        if not sessions:
            await update.message.reply_text(
                "No saved sessions.\n"
                "Use /pause to save the current session."
            )
            return

        lines = ["Saved Sessions:", ""]
        for s in sessions[:10]:  # Limit to 10
            name = s.get("nickname") or s["id"]
            model = s["model"]
            msgs = s["messages"]
            dangerous = " [DANGEROUS]" if s.get("dangerous_mode") else ""
            lines.append(f"  {name} ({model}, {msgs} msgs){dangerous}")

        if len(sessions) > 10:
            lines.append(f"\n  ... and {len(sessions) - 10} more")

        lines.append("")
        lines.append("Use /loadsession <name or id> to resume.")

        await update.message.reply_text("\n".join(lines))

    async def cmd_loadsession(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /loadsession command - resume a saved session."""
        if not await self._check_auth(update):
            return

        if not context.args:
            await update.message.reply_text(
                "Usage: /loadsession <session name or id>\n\n"
                "Use /listsessions to see available sessions."
            )
            return

        identifier = " ".join(context.args)

        # Find matching session
        match = self.runner.find_saved_session(identifier)

        if not match:
            await update.message.reply_text(
                f"Session not found: {identifier}\n\n"
                f"Use /listsessions to see available sessions."
            )
            return

        session = self.runner.resume_session(match["full_id"])
        if session:
            name = session.display_name
            await update.message.reply_text(
                f"Session resumed: {name}\n"
                f"Session ID: {session.id}\n"
                f"Model: {session.model}\n"
                f"Messages: {session.message_count}\n"
                f"Dangerous mode: {'ON' if session.dangerous_mode else 'OFF'}"
            )
        else:
            await update.message.reply_text("Failed to load session.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages as Claude instructions."""
        if not await self._check_auth(update):
            return

        instruction = update.message.text

        if not instruction or not instruction.strip():
            await update.message.reply_text("Please send an instruction for Claude.")
            return

        # Send "working" indicator with session info
        session = self.runner.active_session
        if session:
            working_text = f"Working... [Session: {session.id}, Model: {session.model}]"
        else:
            working_text = f"Working... [New session, Model: {self.runner.current_model}]"

        working_msg = await update.message.reply_text(working_text)

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

        # Footer with metadata
        footer_parts = []
        if result.session_id:
            footer_parts.append(f"Session: {result.session_id}")
        if result.cost_usd is not None:
            footer_parts.append(f"Estimated API Cost: ${result.cost_usd:.4f}")
        if result.duration_seconds is not None:
            footer_parts.append(f"Time: {result.duration_seconds:.1f}s")

        if footer_parts:
            parts.append(f"\n[{' | '.join(footer_parts)}]")

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
        self.application.add_handler(CommandHandler("commands", self.cmd_commands))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("model", self.cmd_model))
        self.application.add_handler(CommandHandler("newsession", self.cmd_newsession))
        self.application.add_handler(CommandHandler("cancel", self.cmd_cancel))
        self.application.add_handler(CommandHandler("nickname", self.cmd_nickname))
        self.application.add_handler(CommandHandler("pause", self.cmd_pause))
        self.application.add_handler(CommandHandler("listsessions", self.cmd_listsessions))
        self.application.add_handler(CommandHandler("loadsession", self.cmd_loadsession))
        self.application.add_handler(CallbackQueryHandler(self.callback_handler))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        return self.application

    def run(self) -> None:
        """Run the bot (blocking)."""
        app = self.build_application()
        logger.info("Starting ClawCat bot...")
        app.run_polling(drop_pending_updates=True)
