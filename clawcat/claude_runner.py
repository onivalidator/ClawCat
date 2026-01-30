"""Claude CLI subprocess wrapper."""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict

from .config import ClaudeConfig


logger = logging.getLogger(__name__)

# Available models - Claude CLI aliases (recommended, auto-map to latest versions)
# Reference: https://docs.anthropic.com/en/docs/claude-code
AVAILABLE_MODELS = ["opus", "sonnet", "haiku"]

# Full model identifiers (for reference)
MODEL_IDENTIFIERS = {
    "opus": "claude-opus-4-5-20251101",      # Opus 4.5 - State-of-the-art, complex reasoning
    "sonnet": "claude-sonnet-4-5-20250929",  # Sonnet 4.5 - Daily coding tasks
    "haiku": "claude-haiku-4-5-20251001",    # Haiku 4.5 - Fast and efficient
}

# Model descriptions for user display
MODEL_DESCRIPTIONS = {
    "opus": "Opus 4.5 - State-of-the-art software engineering (recommended)",
    "sonnet": "Sonnet 4.5 - Fast daily coding tasks",
    "haiku": "Haiku 4.5 - Fastest, high-frequency tasks",
}

# Default model - Opus 4.5 for best quality
DEFAULT_MODEL = "opus"


class RunStatus(Enum):
    """Status of a Claude run."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class RunResult:
    """Result from a Claude CLI execution."""
    status: RunStatus
    output: str
    error: Optional[str] = None
    cost_usd: Optional[float] = None
    duration_seconds: Optional[float] = None
    session_id: Optional[str] = None


@dataclass
class Session:
    """Represents a Claude CLI session."""
    model: str
    dangerous_mode: bool = False
    message_count: int = 0
    # Real session ID from Claude CLI (captured from first response)
    claude_session_id: Optional[str] = None

    @property
    def id(self) -> str:
        """Get a display-friendly session ID.

        Returns the Claude session ID (truncated) if available,
        otherwise returns 'pending' to indicate no session yet.
        """
        if self.claude_session_id:
            return self.claude_session_id[:8]
        return "pending"


class ClaudeRunner:
    """Manages Claude CLI subprocess execution."""

    def __init__(self, config: ClaudeConfig):
        """Initialize the runner with configuration.

        Args:
            config: Claude CLI configuration.
        """
        self.config = config
        self._current_process: Optional[asyncio.subprocess.Process] = None
        self._is_running = False

        # Session management
        self._active_session: Optional[Session] = None
        self._current_model = config.model

    @property
    def is_running(self) -> bool:
        """Check if a command is currently running."""
        return self._is_running

    @property
    def current_model(self) -> str:
        """Get the current model."""
        return self._current_model

    @current_model.setter
    def current_model(self, model: str) -> None:
        """Set the current model."""
        if model in AVAILABLE_MODELS:
            self._current_model = model
            logger.info(f"Model changed to: {model}")

    @property
    def active_session(self) -> Optional[Session]:
        """Get the active session."""
        return self._active_session

    def get_version(self) -> Optional[str]:
        """Get Claude CLI version.

        Returns:
            Version string or None if not available.
        """
        try:
            result = subprocess.run(
                [self.config.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.warning(f"Could not get Claude CLI version: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Claude CLI is available.

        Returns:
            True if claude executable exists and can be run.
        """
        return self.get_version() is not None

    def create_session(self, dangerous_mode: bool = False) -> Session:
        """Create a new session.

        Args:
            dangerous_mode: If True, skip permission prompts.

        Returns:
            New Session object.
        """
        session = Session(
            model=self._current_model,
            dangerous_mode=dangerous_mode
        )
        self._active_session = session
        logger.info(f"Created new session (model={session.model}, dangerous={dangerous_mode})")
        return session

    def get_session_info(self) -> str:
        """Get information about the current session state."""
        session = self.active_session
        if session:
            session_id_display = session.claude_session_id[:8] if session.claude_session_id else "pending"
            model_desc = MODEL_DESCRIPTIONS.get(session.model, session.model)
            model_id = MODEL_IDENTIFIERS.get(session.model, session.model)
            return (
                f"Session ID: {session_id_display}\n"
                f"Model: {model_desc}\n"
                f"Model ID: {model_id}\n"
                f"Messages: {session.message_count}\n"
                f"Dangerous mode: {'ON' if session.dangerous_mode else 'OFF'}"
            )
        return f"No active session. Use /newsession to start one.\nDefault model: {MODEL_DESCRIPTIONS.get(self._current_model, self._current_model)}"

    async def run(self, instruction: str, session: Optional[Session] = None) -> RunResult:
        """Execute an instruction using Claude CLI.

        Args:
            instruction: The instruction to send to Claude.
            session: Optional session to use. If None, uses active session or creates one.

        Returns:
            RunResult containing the output or error.
        """
        if self._is_running:
            return RunResult(
                status=RunStatus.ERROR,
                output="",
                error="Another command is already running. Use /cancel to stop it."
            )

        # Use provided session, active session, or create new one
        if session is None:
            session = self.active_session
            if session is None:
                session = self.create_session()

        self._is_running = True

        try:
            # Build command with flags for non-interactive mode
            cmd = [
                self.config.executable,
                "-p",  # Print mode (non-interactive)
                "--output-format", "json",
                "--model", session.model,
            ]

            # Add dangerous mode flag if enabled
            if session.dangerous_mode:
                cmd.append("--dangerously-skip-permissions")

            # Add resume flag ONLY if we have a real Claude session ID
            if session.claude_session_id:
                cmd.extend(["--resume", session.claude_session_id])

            # Add the instruction
            cmd.append(instruction)

            # Log the full command (redacted)
            cmd_display = " ".join(cmd[:6]) + f" ... [{len(instruction)} chars]"
            logger.info(f">>> EXECUTING CLAUDE CLI: {cmd_display}")
            logger.info(f">>> Working directory: {self.config.working_dir}")
            logger.info(f">>> Model: {session.model}, Dangerous: {session.dangerous_mode}")
            if session.claude_session_id:
                logger.info(f">>> Resuming session: {session.claude_session_id}")

            # Start the subprocess
            self._current_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_dir
            )

            logger.info(f">>> Process started with PID: {self._current_process.pid}")

            try:
                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    self._current_process.communicate(),
                    timeout=self.config.timeout_seconds
                )

                stdout_text = stdout.decode("utf-8", errors="replace")
                stderr_text = stderr.decode("utf-8", errors="replace")

                logger.info(f">>> Process completed with return code: {self._current_process.returncode}")
                logger.info(f">>> stdout length: {len(stdout_text)}, stderr length: {len(stderr_text)}")

                # Update session message count
                session.message_count += 1

                # Check if process was cancelled
                if self._current_process.returncode == -15 or self._current_process.returncode == 1:
                    if "cancelled" in stderr_text.lower():
                        return RunResult(
                            status=RunStatus.CANCELLED,
                            output="",
                            error="Task was cancelled.",
                            session_id=session.claude_session_id
                        )

                # Try to parse JSON output and capture session ID
                result = self._parse_output(stdout_text, stderr_text, self._current_process.returncode, session)
                return result

            except asyncio.TimeoutError:
                # Kill the process on timeout
                logger.warning(f">>> Process timed out after {self.config.timeout_seconds}s, killing...")
                self._current_process.kill()
                await self._current_process.wait()
                return RunResult(
                    status=RunStatus.TIMEOUT,
                    output="",
                    error=f"Command timed out after {self.config.timeout_seconds} seconds.",
                    session_id=session.claude_session_id
                )

        except FileNotFoundError:
            logger.error(f"Claude CLI not found at: {self.config.executable}")
            return RunResult(
                status=RunStatus.ERROR,
                output="",
                error=f"Claude CLI not found at: {self.config.executable}"
            )
        except Exception as e:
            logger.exception("Error running Claude CLI")
            return RunResult(
                status=RunStatus.ERROR,
                output="",
                error=f"Error: {str(e)}"
            )
        finally:
            self._current_process = None
            self._is_running = False

    def _parse_output(self, stdout: str, stderr: str, returncode: int, session: Session) -> RunResult:
        """Parse Claude CLI output.

        Args:
            stdout: Standard output from the process.
            stderr: Standard error from the process.
            returncode: Process return code.
            session: Session to update with captured session ID.

        Returns:
            Parsed RunResult.
        """
        # Try to parse as JSON
        try:
            data = json.loads(stdout)

            # Extract result from JSON response
            # Field names per Claude CLI --output-format json:
            # - result: the response text
            # - session_id: unique session identifier
            # - total_cost_usd: total cost in USD
            # - duration_ms: duration in milliseconds
            result_text = data.get("result", "")
            cost = data.get("total_cost_usd")  # Note: field is total_cost_usd
            duration_ms = data.get("duration_ms")
            duration = duration_ms / 1000.0 if duration_ms else None  # Convert to seconds

            # Capture the real session ID from Claude CLI
            claude_session_id = data.get("session_id")
            if claude_session_id and not session.claude_session_id:
                session.claude_session_id = claude_session_id
                logger.info(f">>> Captured Claude session ID: {claude_session_id}")

            # Log parsed data
            logger.info(f">>> Parsed JSON response - cost: ${cost}, duration: {duration}s")

            # Check for errors - use is_error field from JSON if available
            is_error = data.get("is_error", False) or returncode != 0
            if is_error:
                error_msg = data.get("error") or stderr or f"Process exited with code {returncode}"
                return RunResult(
                    status=RunStatus.ERROR,
                    output=result_text,
                    error=error_msg,
                    cost_usd=cost,
                    duration_seconds=duration,
                    session_id=session.claude_session_id
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                output=result_text,
                cost_usd=cost,
                duration_seconds=duration,
                session_id=session.claude_session_id
            )

        except json.JSONDecodeError:
            # Not JSON, use raw output
            logger.warning(f">>> Could not parse as JSON, using raw output")
            if returncode != 0:
                return RunResult(
                    status=RunStatus.ERROR,
                    output=stdout,
                    error=stderr or f"Process exited with code {returncode}",
                    session_id=session.claude_session_id
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                output=stdout.strip(),
                session_id=session.claude_session_id
            )

    async def cancel(self) -> bool:
        """Cancel the currently running command.

        Returns:
            True if a command was cancelled, False if nothing was running.
        """
        if self._current_process is not None and self._is_running:
            try:
                logger.info(f">>> Cancelling process {self._current_process.pid}")
                self._current_process.terminate()
                # Give it a moment to terminate gracefully
                await asyncio.sleep(0.5)
                if self._current_process.returncode is None:
                    self._current_process.kill()
                return True
            except Exception as e:
                logger.warning(f"Error cancelling process: {e}")
                return False
        return False
