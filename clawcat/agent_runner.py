"""Codex CLI subprocess wrapper."""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import AgentConfig


logger = logging.getLogger(__name__)


class RunStatus(Enum):
    """Status of a Codex run."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class RunResult:
    """Result from a Codex CLI execution."""
    status: RunStatus
    output: str
    error: Optional[str] = None
    cost_usd: Optional[float] = None
    duration_seconds: Optional[float] = None


class AgentRunner:
    """Manages Codex CLI subprocess execution."""

    def __init__(self, config: AgentConfig):
        """Initialize the runner with configuration.

        Args:
            config: Codex CLI configuration.
        """
        self.config = config
        self._current_process: Optional[asyncio.subprocess.Process] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Check if a command is currently running."""
        return self._is_running

    def is_available(self) -> bool:
        """Check if Codex CLI is available.

        Returns:
            True if codex executable exists and can be run.
        """
        try:
            result = subprocess.run(
                [self.config.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning(f"Codex CLI not available: {e}")
            return False

    async def run(self, instruction: str) -> RunResult:
        """Execute an instruction using Codex CLI.

        Args:
            instruction: The instruction to send to Codex.

        Returns:
            RunResult containing the output or error.
        """
        if self._is_running:
            return RunResult(
                status=RunStatus.ERROR,
                output="",
                error="Another command is already running. Use /cancel to stop it."
            )

        self._is_running = True

        try:
            # Build command with flags for non-interactive mode
            cmd = [
                self.config.executable,
                "-p",  # Print mode (non-interactive)
                "--output-format", "json",
                "--model", self.config.model,
                instruction
            ]

            logger.info(f"Running Codex CLI: {' '.join(cmd[:4])}...")

            # Start the subprocess
            self._current_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_dir
            )

            try:
                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    self._current_process.communicate(),
                    timeout=self.config.timeout_seconds
                )

                stdout_text = stdout.decode("utf-8", errors="replace")
                stderr_text = stderr.decode("utf-8", errors="replace")

                # Check if process was cancelled
                if self._current_process.returncode == -15 or self._current_process.returncode == 1:
                    if "cancelled" in stderr_text.lower():
                        return RunResult(
                            status=RunStatus.CANCELLED,
                            output="",
                            error="Task was cancelled."
                        )

                # Try to parse JSON output
                return self._parse_output(stdout_text, stderr_text, self._current_process.returncode)

            except asyncio.TimeoutError:
                # Kill the process on timeout
                self._current_process.kill()
                await self._current_process.wait()
                return RunResult(
                    status=RunStatus.TIMEOUT,
                    output="",
                    error=f"Command timed out after {self.config.timeout_seconds} seconds."
                )

        except FileNotFoundError:
            return RunResult(
                status=RunStatus.ERROR,
                output="",
                error=f"Codex CLI not found at: {self.config.executable}"
            )
        except Exception as e:
            logger.exception("Error running Codex CLI")
            return RunResult(
                status=RunStatus.ERROR,
                output="",
                error=f"Error: {str(e)}"
            )
        finally:
            self._current_process = None
            self._is_running = False

    def _parse_output(self, stdout: str, stderr: str, returncode: int) -> RunResult:
        """Parse Codex CLI output.

        Args:
            stdout: Standard output from the process.
            stderr: Standard error from the process.
            returncode: Process return code.

        Returns:
            Parsed RunResult.
        """
        # Try to parse as JSON
        try:
            data = json.loads(stdout)

            # Extract result from JSON response
            result_text = data.get("result", "")
            cost = data.get("cost_usd")
            duration = data.get("duration_seconds")

            if returncode != 0:
                error_msg = data.get("error") or stderr or f"Process exited with code {returncode}"
                return RunResult(
                    status=RunStatus.ERROR,
                    output=result_text,
                    error=error_msg,
                    cost_usd=cost,
                    duration_seconds=duration
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                output=result_text,
                cost_usd=cost,
                duration_seconds=duration
            )

        except json.JSONDecodeError:
            # Not JSON, use raw output
            if returncode != 0:
                return RunResult(
                    status=RunStatus.ERROR,
                    output=stdout,
                    error=stderr or f"Process exited with code {returncode}"
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                output=stdout.strip()
            )

    async def cancel(self) -> bool:
        """Cancel the currently running command.

        Returns:
            True if a command was cancelled, False if nothing was running.
        """
        if self._current_process is not None and self._is_running:
            try:
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
