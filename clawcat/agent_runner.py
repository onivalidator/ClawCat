"""Codex CLI subprocess wrapper."""

import asyncio
import json
import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any

from .config import AgentConfig
from .session_store import SessionStore


logger = logging.getLogger(__name__)

# Available models - Codex CLI aliases (recommended, auto-map to latest versions)
# Reference: https://platform.openai.com/en/docs/codex-code
AVAILABLE_MODELS = ["gpt-5.1-codex", "gpt-5.1", "gpt-5"]

# Full model identifiers (for reference)
MODEL_IDENTIFIERS = {
    "gpt-5.1-codex": "gpt-5.1-codex",      # GPT-5.1 Codex - State-of-the-art, complex reasoning
    "gpt-5.1": "gpt-5.1",  # GPT-5.1 - Daily coding tasks
    "gpt-5": "gpt-5",    # GPT-5 - Fast and efficient
}

# Model descriptions for user display
MODEL_DESCRIPTIONS = {
    "gpt-5.1-codex": "GPT-5.1 Codex - State-of-the-art software engineering (recommended)",
    "gpt-5.1": "GPT-5.1 - Fast daily coding tasks",
    "gpt-5": "GPT-5 - Fastest, high-frequency tasks",
}

# Default model - GPT-5.1 Codex for best quality
DEFAULT_MODEL = "gpt-5.1-codex"


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
    session_id: Optional[str] = None


@dataclass
class Session:
    """Represents a Codex CLI session."""
    model: str
    dangerous_mode: bool = False
    message_count: int = 0
    # Real session ID from Codex CLI (captured from first response)
    agent_session_id: Optional[str] = None
    # User-defined nickname for the session
    nickname: Optional[str] = None
    # Timestamp when session was created
    created_at: Optional[float] = field(default_factory=time.time)

    @property
    def id(self) -> str:
        """Get a display-friendly session ID.

        Returns the Codex session ID (truncated) if available,
        otherwise returns 'pending' to indicate no session yet.
        """
        if self.agent_session_id:
            return self.agent_session_id[:8]
        return "pending"

    @property
    def display_name(self) -> str:
        """Get a user-friendly display name for the session.

        Returns nickname if set, otherwise truncated session ID.
        """
        if self.nickname:
            return self.nickname
        return self.id


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

        # Session management
        self._active_session: Optional[Session] = None
        self._current_model = config.model

        # Session persistence
        storage_dir = Path(config.working_dir) / "ClawCat_sessions"
        self._session_store = SessionStore(storage_dir)

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
        """Get Codex CLI version.

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
            logger.warning(f"Could not get Codex CLI version: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Codex CLI is available.

        Returns:
            True if codex executable exists and can be run.
        """
        return self.get_version() is not None

    def create_session(self, dangerous_mode: bool = False, open_monitor: bool = True) -> Session:
        """Create a new session.

        Args:
            dangerous_mode: If True, skip permission prompts.
            open_monitor: If True and configured, open a monitor window.

        Returns:
            New Session object.
        """
        session = Session(
            model=self._current_model,
            dangerous_mode=dangerous_mode
        )
        self._active_session = session
        logger.info(f"Created new session (model={session.model}, dangerous={dangerous_mode})")

        # Open monitor window if configured
        if open_monitor and self.config.open_monitor_window:
            self._open_monitor_window(session)

        return session

    def _get_activity_log_path(self) -> Path:
        """Get path to the activity log file."""
        return Path(self.config.working_dir) / "ClawCat_sessions" / "activity.log"

    def _open_monitor_window(self, session: Session) -> None:
        """Open a monitor window for the session.

        Args:
            session: The session to monitor.
        """
        try:
            monitor_script = Path(__file__).parent / "session_monitor.py"
            log_file = self._get_activity_log_path()
            log_file.parent.mkdir(parents=True, exist_ok=True)

            session_name = session.nickname or "New Session"
            session_id = session.agent_session_id or "pending"

            # Write initial log entry
            self._log_activity(f"Session started: {session_name} (model={session.model})")

            # Launch monitor as detached process (Windows-specific flags)
            CREATE_NEW_CONSOLE = 0x00000010
            DETACHED_PROCESS = 0x00000008

            subprocess.Popen(
                [sys.executable, str(monitor_script), session_id, session_name, str(log_file)],
                creationflags=CREATE_NEW_CONSOLE | DETACHED_PROCESS,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(f"Monitor window launched for session: {session_name}")

        except Exception as e:
            logger.warning(f"Could not open monitor window: {e}")

    def _log_activity(self, message: str) -> None:
        """Log activity to the session activity log file.

        Args:
            message: Message to log.
        """
        try:
            log_file = self._get_activity_log_path()
            log_file.parent.mkdir(parents=True, exist_ok=True)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logger.warning(f"Could not write to activity log: {e}")

    def get_session_info(self) -> str:
        """Get information about the current session state."""
        session = self.active_session
        if session:
            session_id_display = session.agent_session_id[:8] if session.agent_session_id else "pending"
            model_desc = MODEL_DESCRIPTIONS.get(session.model, session.model)
            model_id = MODEL_IDENTIFIERS.get(session.model, session.model)
            nickname_line = f"Nickname: {session.nickname}\n" if session.nickname else ""
            return (
                f"Session ID: {session_id_display}\n"
                f"{nickname_line}"
                f"Model: {model_desc}\n"
                f"Model ID: {model_id}\n"
                f"Messages: {session.message_count}\n"
                f"Dangerous mode: {'ON' if session.dangerous_mode else 'OFF'}"
            )
        return f"No active session. Use /newsession to start one.\nDefault model: {MODEL_DESCRIPTIONS.get(self._current_model, self._current_model)}"

    def pause_session(self) -> Optional[Session]:
        """Pause and save the current session to disk.

        Returns:
            The paused session, or None if no session to pause.
        """
        session = self._active_session
        if session and session.agent_session_id:
            if self._session_store.save_session(session):
                paused = session
                self._active_session = None
                logger.info(f"Session paused: {session.display_name}")
                return paused
        return None

    def resume_session(self, session_id: str) -> Optional[Session]:
        """Resume a saved session from disk.

        Args:
            session_id: Full session ID to resume.

        Returns:
            The resumed Session, or None if not found.
        """
        data = self._session_store.load_session_data(session_id)
        if not data:
            return None

        session = Session(
            model=data["model"],
            dangerous_mode=data.get("dangerous_mode", False),
            message_count=data.get("message_count", 0),
            agent_session_id=data["agent_session_id"],
            nickname=data.get("nickname"),
            created_at=data.get("created_at"),
        )
        self._active_session = session
        logger.info(f"Session resumed: {session.display_name}")
        return session

    def list_saved_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions.

        Returns:
            List of session metadata dicts.
        """
        return self._session_store.list_sessions()

    def find_saved_session(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Find a saved session by nickname or ID.

        Args:
            identifier: Nickname or session ID prefix.

        Returns:
            Session metadata dict, or None if not found.
        """
        return self._session_store.find_session(identifier)

    def _run_subprocess_sync(self, cmd: list, working_dir: str, timeout: int, visible: bool = False, session: Optional[Session] = None) -> tuple:
        """Run subprocess synchronously (for use in thread).

        Args:
            cmd: Command to run.
            working_dir: Working directory.
            timeout: Timeout in seconds.
            visible: If True, run in a visible console window.
            session: Optional session for display info in visible mode.

        Returns:
            Tuple of (stdout, stderr, returncode, timed_out).
        """
        try:
            if visible and sys.platform == 'win32':
                # Visible terminal mode: run Codex CLI in a visible console window
                # Use PowerShell with Tee-Object to show output AND capture to file
                return self._run_visible_terminal(cmd, working_dir, timeout, session)
            else:
                # Hidden mode: run silently in background
                self._current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )

                try:
                    stdout, stderr = self._current_process.communicate(timeout=timeout)
                    return (stdout, stderr, self._current_process.returncode, False)
                except subprocess.TimeoutExpired:
                    self._current_process.kill()
                    stdout, stderr = self._current_process.communicate()
                    return (stdout, stderr, self._current_process.returncode, True)

        except Exception as e:
            raise e

    def _run_visible_terminal(self, cmd: list, working_dir: str, timeout: int, session: Optional[Session] = None) -> tuple:
        """Run Codex CLI in a visible terminal window on the user's desktop.

        Uses Task Scheduler to launch in the interactive session (required for services).

        Args:
            cmd: Command to run.
            working_dir: Working directory.
            timeout: Timeout in seconds.
            session: Optional session for display info.

        Returns:
            Tuple of (stdout, stderr, returncode, timed_out).
        """
        # Create temp files for stdout, stderr, and the script
        temp_dir = Path(tempfile.gettempdir()) / "clawcat"
        temp_dir.mkdir(exist_ok=True)

        timestamp = time.time_ns()
        stdout_file = temp_dir / f"stdout_{timestamp}.txt"
        stderr_file = temp_dir / f"stderr_{timestamp}.txt"
        exitcode_file = temp_dir / f"exitcode_{timestamp}.txt"
        script_file = temp_dir / f"clawcat_run_{timestamp}.ps1"
        done_file = temp_dir / f"done_{timestamp}.txt"

        # Build the argument list for Codex CLI
        # First arg is the executable, rest are arguments
        codex_exe = cmd[0]
        codex_args = cmd[1:]

        # Escape arguments for PowerShell
        args_escaped = []
        for arg in codex_args:
            # Escape for PowerShell command line
            escaped = arg.replace('"', '`"').replace("'", "''")
            args_escaped.append(f'"{escaped}"')

        args_string = " ".join(args_escaped)

        # Get session display info
        session_display = session.display_name if session else "New Session"
        session_id_short = session.id if session else "pending"

        # Create PowerShell script file
        ps_script = f'''
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

# Set window title
$host.UI.RawUI.WindowTitle = "ClawCat Session: {session_display} [{session_id_short}]"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ClawCat - Codex CLI Session" -ForegroundColor Cyan
Write-Host "  Session: {session_display}" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Working directory: {working_dir}" -ForegroundColor Gray
Write-Host "Model: {cmd[5] if len(cmd) > 5 else 'gpt-5.1-codex'}" -ForegroundColor Gray
Write-Host ""
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Starting Codex CLI..." -ForegroundColor Yellow
Write-Host ""

try {{
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = "{codex_exe}"
    $pinfo.Arguments = '{args_string}'
    $pinfo.WorkingDirectory = "{working_dir}"
    $pinfo.RedirectStandardOutput = $true
    $pinfo.RedirectStandardError = $true
    $pinfo.UseShellExecute = $false
    $pinfo.CreateNoWindow = $false

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $pinfo
    $process.Start() | Out-Null

    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    $stdout | Out-File -FilePath "{stdout_file}" -Encoding utf8
    $stderr | Out-File -FilePath "{stderr_file}" -Encoding utf8
    $process.ExitCode | Out-File -FilePath "{exitcode_file}" -Encoding utf8

    # Try to extract session ID from JSON output to update window title
    try {{
        $json = $stdout | ConvertFrom-Json
        if ($json.session_id) {{
            $shortId = $json.session_id.Substring(0, 8)
            $host.UI.RawUI.WindowTitle = "ClawCat Session: {session_display} [$shortId]"
        }}
    }} catch {{ }}

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Codex CLI Output:" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    # Try to display just the result if JSON, otherwise show raw
    try {{
        $json = $stdout | ConvertFrom-Json
        if ($json.result) {{
            Write-Host $json.result -ForegroundColor White
            Write-Host ""
            Write-Host "Cost: `$$($json.total_cost_usd) | Duration: $($json.duration_ms)ms" -ForegroundColor DarkGray
        }} else {{
            Write-Host $stdout
        }}
    }} catch {{
        Write-Host $stdout
    }}

    if ($stderr) {{
        Write-Host ""
        Write-Host "Errors:" -ForegroundColor Red
        Write-Host $stderr -ForegroundColor Red
    }}
}} catch {{
    Write-Host "Error: $_" -ForegroundColor Red
    "1" | Out-File -FilePath "{exitcode_file}" -Encoding utf8
    $_.ToString() | Out-File -FilePath "{stderr_file}" -Encoding utf8
}}

"done" | Out-File -FilePath "{done_file}" -Encoding utf8

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Command complete." -ForegroundColor Green
Write-Host "This window will stay open for monitoring." -ForegroundColor Gray
Write-Host "Close manually when no longer needed." -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Keep window open indefinitely - user can close manually
# Or could add: Read-Host "Press Enter to close..."
while ($true) {{
    Start-Sleep -Seconds 60
}}
'''

        # Write the script to a file
        script_file.write_text(ps_script, encoding='utf-8')

        try:
            # Use schtasks to run in the interactive session
            # This creates a temporary scheduled task that runs immediately
            task_name = f"ClawCat_Run_{timestamp}"

            # Create the scheduled task
            schtasks_create = [
                "schtasks", "/create",
                "/tn", task_name,
                "/tr", f'powershell.exe -ExecutionPolicy Bypass -File "{script_file}"',
                "/sc", "once",
                "/st", "00:00",
                "/f",  # Force overwrite
                "/rl", "highest",  # Run with highest privileges
            ]

            result = subprocess.run(schtasks_create, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to create scheduled task: {result.stderr}")
                raise Exception(f"Failed to create scheduled task: {result.stderr}")

            # Run the task immediately
            schtasks_run = ["schtasks", "/run", "/tn", task_name]
            result = subprocess.run(schtasks_run, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to run scheduled task: {result.stderr}")
                raise Exception(f"Failed to run scheduled task: {result.stderr}")

            logger.info(f">>> Visible terminal launched via Task Scheduler: {task_name}")

            # Wait for the done file to appear (indicates script completed)
            timed_out = False
            start_time = time.time()
            while not done_file.exists():
                if time.time() - start_time > timeout:
                    logger.warning(f">>> Visible terminal timed out after {timeout}s")
                    timed_out = True
                    break
                time.sleep(0.5)

            # Give a moment for files to be fully written
            time.sleep(0.5)

            # Read output files
            stdout = b""
            stderr = b""
            returncode = 1

            if stdout_file.exists():
                stdout = stdout_file.read_bytes()
                try:
                    stdout_file.unlink()
                except:
                    pass

            if stderr_file.exists():
                stderr = stderr_file.read_bytes()
                try:
                    stderr_file.unlink()
                except:
                    pass

            if exitcode_file.exists():
                try:
                    exitcode_text = exitcode_file.read_text(encoding='utf-8').strip()
                    # Handle BOM if present
                    exitcode_text = exitcode_text.lstrip('\ufeff').strip()
                    returncode = int(exitcode_text) if exitcode_text else 1
                except (ValueError, Exception) as e:
                    logger.warning(f"Could not parse exit code: {e}")
                    returncode = 1
                try:
                    exitcode_file.unlink()
                except:
                    pass

            # Clean up
            if done_file.exists():
                try:
                    done_file.unlink()
                except:
                    pass

            if script_file.exists():
                try:
                    script_file.unlink()
                except:
                    pass

            # Delete the scheduled task
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                capture_output=True
            )

            return (stdout, stderr, returncode, timed_out)

        except Exception as e:
            logger.exception("Error in visible terminal mode")
            # Clean up on error
            for f in [script_file, stdout_file, stderr_file, exitcode_file, done_file]:
                if f.exists():
                    try:
                        f.unlink()
                    except:
                        pass
            raise e

    async def run(self, instruction: str, session: Optional[Session] = None) -> RunResult:
        """Execute an instruction using Codex CLI.

        Args:
            instruction: The instruction to send to Codex.
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

            # Add resume flag ONLY if we have a real Codex session ID
            if session.agent_session_id:
                cmd.extend(["--resume", session.agent_session_id])

            # Add the instruction
            cmd.append(instruction)

            # Log the full command (redacted)
            cmd_display = " ".join(cmd[:6]) + f" ... [{len(instruction)} chars]"
            logger.info(f">>> EXECUTING CLAUDE CLI: {cmd_display}")
            logger.info(f">>> Working directory: {self.config.working_dir}")
            logger.info(f">>> Model: {session.model}, Dangerous: {session.dangerous_mode}")
            if session.agent_session_id:
                logger.info(f">>> Resuming session: {session.agent_session_id}")

            # Log to activity file for monitor window
            instruction_preview = instruction[:100] + "..." if len(instruction) > 100 else instruction
            self._log_activity(f"Instruction: {instruction_preview}")

            # Run subprocess in thread to avoid asyncio subprocess issues on Windows Service
            stdout, stderr, returncode, timed_out = await asyncio.to_thread(
                self._run_subprocess_sync,
                cmd,
                self.config.working_dir,
                self.config.timeout_seconds,
                self.config.visible_terminal,
                session
            )

            if timed_out:
                logger.warning(f">>> Process timed out after {self.config.timeout_seconds}s")
                return RunResult(
                    status=RunStatus.TIMEOUT,
                    output="",
                    error=f"Command timed out after {self.config.timeout_seconds} seconds.",
                    session_id=session.agent_session_id
                )

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            logger.info(f">>> Process completed with return code: {returncode}")
            logger.info(f">>> stdout length: {len(stdout_text)}, stderr length: {len(stderr_text)}")

            # Update session message count
            session.message_count += 1

            # Check if process was cancelled
            if returncode == -15 or returncode == 1:
                if "cancelled" in stderr_text.lower():
                    return RunResult(
                        status=RunStatus.CANCELLED,
                        output="",
                        error="Task was cancelled.",
                        session_id=session.agent_session_id
                    )

            # Try to parse JSON output and capture session ID
            result = self._parse_output(stdout_text, stderr_text, returncode, session)

            # Log result to activity file
            status_str = result.status.value.upper()
            output_preview = result.output[:200] + "..." if len(result.output) > 200 else result.output
            cost_str = f"${result.cost_usd:.4f}" if result.cost_usd else "N/A"
            self._log_activity(f"Result [{status_str}]: {output_preview}")
            self._log_activity(f"Cost: {cost_str}, Messages: {session.message_count}")

            return result

        except FileNotFoundError:
            logger.error(f"Codex CLI not found at: {self.config.executable}")
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

    def _parse_output(self, stdout: str, stderr: str, returncode: int, session: Session) -> RunResult:
        """Parse Codex CLI output.

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
            # Strip UTF-8 BOM if present (PowerShell Out-File adds this)
            stdout_clean = stdout.lstrip('\ufeff').strip()
            data = json.loads(stdout_clean)

            # Extract result from JSON response
            # Field names per Codex CLI --output-format json:
            # - result: the response text
            # - session_id: unique session identifier
            # - total_cost_usd: total cost in USD
            # - duration_ms: duration in milliseconds
            result_text = data.get("result", "")
            cost = data.get("total_cost_usd")  # Note: field is total_cost_usd
            duration_ms = data.get("duration_ms")
            duration = duration_ms / 1000.0 if duration_ms else None  # Convert to seconds

            # Capture the real session ID from Codex CLI
            agent_session_id = data.get("session_id")
            if agent_session_id and not session.agent_session_id:
                session.agent_session_id = agent_session_id
                logger.info(f">>> Captured Codex session ID: {agent_session_id}")

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
                    session_id=session.agent_session_id
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                output=result_text,
                cost_usd=cost,
                duration_seconds=duration,
                session_id=session.agent_session_id
            )

        except json.JSONDecodeError:
            # Not JSON, use raw output
            logger.warning(f">>> Could not parse as JSON, using raw output")
            if returncode != 0:
                return RunResult(
                    status=RunStatus.ERROR,
                    output=stdout,
                    error=stderr or f"Process exited with code {returncode}",
                    session_id=session.agent_session_id
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                output=stdout.strip(),
                session_id=session.agent_session_id
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
