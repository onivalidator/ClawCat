"""Local coding-agent subprocess wrapper."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import AgentConfig
from .session_store import SessionStore


logger = logging.getLogger(__name__)


MODEL_DESCRIPTIONS = {
    "default": "Default model from local CLI config",
    "gpt-5.1-codex": "GPT-5.1 Codex - coding-agent workflows",
    "gpt-5.1": "GPT-5.1 - general OpenAI reasoning",
    "gpt-5": "GPT-5 - general OpenAI reasoning",
    "opus": "Claude Opus - high quality coding tasks",
    "sonnet": "Claude Sonnet - fast daily coding tasks",
    "haiku": "Claude Haiku - fast lightweight tasks",
}

MODEL_IDENTIFIERS = {
    "default": "CLI default",
    "gpt-5.1-codex": "gpt-5.1-codex",
    "gpt-5.1": "gpt-5.1",
    "gpt-5": "gpt-5",
    "opus": "Claude CLI alias: opus",
    "sonnet": "Claude CLI alias: sonnet",
    "haiku": "Claude CLI alias: haiku",
}


class RunStatus(Enum):
    """Status of an agent run."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class RunResult:
    """Result from a local agent CLI execution."""

    status: RunStatus
    output: str
    error: Optional[str] = None
    cost_usd: Optional[float] = None
    duration_seconds: Optional[float] = None
    session_id: Optional[str] = None


@dataclass
class Session:
    """Represents a local agent session."""

    provider: str
    model: Optional[str]
    dangerous_mode: bool = False
    message_count: int = 0
    agent_session_id: Optional[str] = None
    nickname: Optional[str] = None
    created_at: Optional[float] = field(default_factory=time.time)

    @property
    def id(self) -> str:
        """Get a display-friendly session ID."""
        if self.agent_session_id:
            return self.agent_session_id[:8]
        return "pending"

    @property
    def display_name(self) -> str:
        """Get a user-friendly display name for the session."""
        return self.nickname or self.id

    @property
    def model_display(self) -> str:
        """Get a display-safe model name."""
        return self.model or "default"


class AgentRunner:
    """Manages local coding-agent subprocess execution."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self._current_process: Optional[subprocess.Popen] = None
        self._is_running = False
        self._active_session: Optional[Session] = None
        self._current_model = config.model or "default"
        self.available_models = config.models or [self._current_model]

        storage_dir = Path(config.working_dir) / "ClawCat_sessions"
        self._session_store = SessionStore(storage_dir)

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def provider_label(self) -> str:
        return "Codex" if self.config.provider == "codex" else "Claude"

    @property
    def current_model(self) -> str:
        return self._current_model

    @current_model.setter
    def current_model(self, model: str) -> None:
        if model in self.available_models:
            self._current_model = model
            logger.info("Model changed to: %s", model)

    @property
    def active_session(self) -> Optional[Session]:
        return self._active_session

    def get_version(self) -> Optional[str]:
        """Get the configured CLI version."""
        try:
            result = subprocess.run(
                [self.config.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return (result.stdout or result.stderr).strip()
            return None
        except Exception as e:
            logger.warning("Could not get %s version: %s", self.provider_label, e)
            return None

    def is_available(self) -> bool:
        return self.get_version() is not None

    def create_session(self, dangerous_mode: bool = False, open_monitor: bool = True) -> Session:
        """Create a new local-agent session."""
        if dangerous_mode and not self.config.allow_dangerous_mode:
            logger.warning("Dangerous mode requested but disabled by config")
            dangerous_mode = False

        model = None if self._current_model == "default" else self._current_model
        session = Session(
            provider=self.config.provider,
            model=model,
            dangerous_mode=dangerous_mode,
        )
        self._active_session = session
        logger.info(
            "Created new %s session (model=%s, dangerous=%s)",
            self.provider_label,
            session.model_display,
            session.dangerous_mode,
        )

        if open_monitor and self.config.open_monitor_window:
            self._open_monitor_window(session)

        return session

    def _get_activity_log_path(self) -> Path:
        return Path(self.config.working_dir) / "ClawCat_sessions" / "activity.log"

    def _log_activity(self, message: str) -> None:
        try:
            log_file = self._get_activity_log_path()
            log_file.parent.mkdir(parents=True, exist_ok=True)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logger.warning("Could not write to activity log: %s", e)

    def _open_monitor_window(self, session: Session) -> None:
        try:
            monitor_script = Path(__file__).parent / "session_monitor.py"
            log_file = self._get_activity_log_path()
            log_file.parent.mkdir(parents=True, exist_ok=True)

            session_name = session.nickname or "New Session"
            session_id = session.agent_session_id or "pending"
            self._log_activity(
                f"Session started: {session_name} ({self.provider_label}, model={session.model_display})"
            )

            if sys.platform == "win32":
                creationflags = 0x00000010 | 0x00000008
                subprocess.Popen(
                    [sys.executable, str(monitor_script), session_id, session_name, str(log_file)],
                    creationflags=creationflags,
                    close_fds=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                env = os.environ.copy()
                env["CLAWCAT_MONITOR_SESSION_ID"] = session_id
                env["CLAWCAT_MONITOR_SESSION_NAME"] = session_name
                env["CLAWCAT_MONITOR_LOG_FILE"] = str(log_file)
                subprocess.Popen(
                    [sys.executable, str(monitor_script), session_id, session_name, str(log_file)],
                    start_new_session=True,
                    close_fds=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                )
            logger.info("Monitor window launched for session: %s", session_name)
        except Exception as e:
            logger.warning("Could not open monitor window: %s", e)

    def get_session_info(self) -> str:
        session = self.active_session
        if session:
            model = session.model_display
            model_desc = MODEL_DESCRIPTIONS.get(model, model)
            model_id = MODEL_IDENTIFIERS.get(model, model)
            nickname_line = f"Nickname: {session.nickname}\n" if session.nickname else ""
            return (
                f"Provider: {self.provider_label}\n"
                f"Session ID: {session.id}\n"
                f"{nickname_line}"
                f"Model: {model_desc}\n"
                f"Model ID: {model_id}\n"
                f"Messages: {session.message_count}\n"
                f"Sandbox: {self.config.sandbox_mode}\n"
                f"Dangerous mode: {'ON' if session.dangerous_mode else 'OFF'}"
            )

        return (
            "No active session. Use /newsession to start one.\n"
            f"Provider: {self.provider_label}\n"
            f"Default model: {MODEL_DESCRIPTIONS.get(self._current_model, self._current_model)}\n"
            f"Sandbox: {self.config.sandbox_mode}"
        )

    def pause_session(self) -> Optional[Session]:
        session = self._active_session
        if session and session.agent_session_id:
            if self._session_store.save_session(session):
                paused = session
                self._active_session = None
                logger.info("Session paused: %s", session.display_name)
                return paused
        return None

    def resume_session(self, session_id: str) -> Optional[Session]:
        data = self._session_store.load_session_data(session_id)
        if not data:
            return None

        session = Session(
            provider=data.get("provider", self.config.provider),
            model=data.get("model"),
            dangerous_mode=data.get("dangerous_mode", False),
            message_count=data.get("message_count", 0),
            agent_session_id=data["agent_session_id"],
            nickname=data.get("nickname"),
            created_at=data.get("created_at"),
        )
        self._active_session = session
        logger.info("Session resumed: %s", session.display_name)
        return session

    def list_saved_sessions(self) -> List[Dict[str, Any]]:
        return self._session_store.list_sessions()

    def find_saved_session(self, identifier: str) -> Optional[Dict[str, Any]]:
        return self._session_store.find_session(identifier)

    def _build_codex_command(self, instruction: str, session: Session, output_file: Path) -> list[str]:
        # Keep Codex remote runs fail-closed and explicitly sandboxed. The current
        # `codex exec resume` command does not expose the same sandbox flags, so
        # ClawCat starts a fresh non-interactive Codex run for each Telegram task.
        cmd = [self.config.executable, "exec"]

        if session.model:
            cmd.extend(["--model", session.model])

        if session.dangerous_mode:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            cmd.extend(["--sandbox", self.config.sandbox_mode])

        if self.config.skip_git_repo_check:
            cmd.append("--skip-git-repo-check")

        cmd.extend(["--json", "--output-last-message", str(output_file)])
        cmd.append(instruction)
        return cmd

    def _build_claude_command(self, instruction: str, session: Session) -> list[str]:
        cmd = [
            self.config.executable,
            "-p",
            "--output-format",
            "json",
        ]

        if session.model:
            cmd.extend(["--model", session.model])

        if session.dangerous_mode:
            cmd.append("--dangerously-skip-permissions")

        if session.agent_session_id:
            cmd.extend(["--resume", session.agent_session_id])

        cmd.append(instruction)
        return cmd

    def _build_command(self, instruction: str, session: Session, output_file: Path) -> list[str]:
        if self.config.provider == "codex":
            return self._build_codex_command(instruction, session, output_file)
        return self._build_claude_command(instruction, session)

    def _run_subprocess_sync(
        self,
        cmd: list[str],
        working_dir: str,
        timeout: int,
    ) -> tuple[bytes, bytes, int, bool]:
        try:
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            try:
                stdout, stderr = self._current_process.communicate(timeout=timeout)
                return stdout, stderr, self._current_process.returncode, False
            except subprocess.TimeoutExpired:
                self._current_process.kill()
                stdout, stderr = self._current_process.communicate()
                return stdout, stderr, self._current_process.returncode, True
        except Exception:
            raise

    async def run(self, instruction: str, session: Optional[Session] = None) -> RunResult:
        """Execute an instruction using the configured local agent CLI."""
        if self._is_running:
            return RunResult(
                status=RunStatus.ERROR,
                output="",
                error="Another command is already running. Use /cancel to stop it.",
            )

        if session is None:
            session = self.active_session
            if session is None:
                session = self.create_session()

        self._is_running = True
        output_file: Optional[Path] = None

        try:
            temp_dir = Path(tempfile.gettempdir()) / "clawcat"
            temp_dir.mkdir(exist_ok=True)
            output_file = temp_dir / f"last_message_{time.time_ns()}.txt"
            cmd = self._build_command(instruction, session, output_file)

            instruction_preview = instruction[:100] + "..." if len(instruction) > 100 else instruction
            logger.info(">>> EXECUTING %s CLI: %s ... [%d chars]", self.provider_label, cmd[:8], len(instruction))
            logger.info(">>> Working directory: %s", self.config.working_dir)
            logger.info(
                ">>> Model: %s, sandbox=%s, dangerous=%s",
                session.model_display,
                self.config.sandbox_mode,
                session.dangerous_mode,
            )
            self._log_activity(f"Instruction: {instruction_preview}")

            start = time.time()
            stdout, stderr, returncode, timed_out = await asyncio.to_thread(
                self._run_subprocess_sync,
                cmd,
                self.config.working_dir,
                self.config.timeout_seconds,
            )
            duration = time.time() - start

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            if timed_out:
                logger.warning(">>> Process timed out after %ss", self.config.timeout_seconds)
                return RunResult(
                    status=RunStatus.TIMEOUT,
                    output="",
                    error=f"Command timed out after {self.config.timeout_seconds} seconds.",
                    duration_seconds=duration,
                    session_id=session.agent_session_id,
                )

            session.message_count += 1
            result = self._parse_output(
                stdout_text,
                stderr_text,
                returncode,
                session,
                output_file,
                duration,
            )

            status_str = result.status.value.upper()
            output_preview = result.output[:200] + "..." if len(result.output) > 200 else result.output
            self._log_activity(f"Result [{status_str}]: {output_preview}")
            self._log_activity(f"Messages: {session.message_count}")

            return result

        except FileNotFoundError:
            logger.error("%s CLI not found at: %s", self.provider_label, self.config.executable)
            return RunResult(
                status=RunStatus.ERROR,
                output="",
                error=f"{self.provider_label} CLI not found at: {self.config.executable}",
            )
        except Exception as e:
            logger.exception("Error running %s CLI", self.provider_label)
            return RunResult(status=RunStatus.ERROR, output="", error=f"Error: {str(e)}")
        finally:
            if output_file and output_file.exists():
                try:
                    output_file.unlink()
                except OSError:
                    pass
            self._current_process = None
            self._is_running = False

    def _parse_output(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        session: Session,
        output_file: Optional[Path],
        duration_seconds: float,
    ) -> RunResult:
        if self.config.provider == "codex":
            return self._parse_codex_output(
                stdout,
                stderr,
                returncode,
                session,
                output_file,
                duration_seconds,
            )
        return self._parse_claude_output(stdout, stderr, returncode, session, duration_seconds)

    def _parse_codex_output(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        session: Session,
        output_file: Optional[Path],
        duration_seconds: float,
    ) -> RunResult:
        output = ""
        if output_file and output_file.exists():
            output = output_file.read_text(encoding="utf-8", errors="replace").strip()

        if not output:
            output = stdout.strip()

        session_id = self._extract_codex_session_id(stdout)
        if session_id and not session.agent_session_id:
            session.agent_session_id = session_id
            logger.info(">>> Captured Codex session ID: %s", session_id)

        if returncode != 0:
            return RunResult(
                status=RunStatus.ERROR,
                output=output,
                error=stderr.strip() or f"Process exited with code {returncode}",
                duration_seconds=duration_seconds,
                session_id=session.agent_session_id,
            )

        return RunResult(
            status=RunStatus.SUCCESS,
            output=output,
            duration_seconds=duration_seconds,
            session_id=session.agent_session_id,
        )

    def _extract_codex_session_id(self, stdout: str) -> Optional[str]:
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            for key in ("session_id", "conversation_id", "thread_id"):
                value = event.get(key)
                if isinstance(value, str) and value:
                    return value

            item = event.get("item")
            if isinstance(item, dict):
                for key in ("session_id", "conversation_id", "thread_id"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        return value

        return None

    def _parse_claude_output(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        session: Session,
        duration_seconds: float,
    ) -> RunResult:
        try:
            data = json.loads(stdout.lstrip("\ufeff").strip())
            result_text = data.get("result", "")
            cost = data.get("total_cost_usd")
            duration_ms = data.get("duration_ms")
            duration = duration_ms / 1000.0 if duration_ms else duration_seconds

            cli_session_id = data.get("session_id")
            if cli_session_id and not session.agent_session_id:
                session.agent_session_id = cli_session_id
                logger.info(">>> Captured Claude session ID: %s", cli_session_id)

            is_error = data.get("is_error", False) or returncode != 0
            if is_error:
                return RunResult(
                    status=RunStatus.ERROR,
                    output=result_text,
                    error=data.get("error") or stderr or f"Process exited with code {returncode}",
                    cost_usd=cost,
                    duration_seconds=duration,
                    session_id=session.agent_session_id,
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                output=result_text,
                cost_usd=cost,
                duration_seconds=duration,
                session_id=session.agent_session_id,
            )
        except json.JSONDecodeError:
            if returncode != 0:
                return RunResult(
                    status=RunStatus.ERROR,
                    output=stdout,
                    error=stderr or f"Process exited with code {returncode}",
                    duration_seconds=duration_seconds,
                    session_id=session.agent_session_id,
                )

            return RunResult(
                status=RunStatus.SUCCESS,
                output=stdout.strip(),
                duration_seconds=duration_seconds,
                session_id=session.agent_session_id,
            )

    async def cancel(self) -> bool:
        """Cancel the currently running command."""
        if self._current_process is not None and self._is_running:
            try:
                logger.info(">>> Cancelling process %s", self._current_process.pid)
                self._current_process.terminate()
                await asyncio.sleep(0.5)
                if self._current_process.returncode is None:
                    self._current_process.kill()
                return True
            except Exception as e:
                logger.warning("Error cancelling process: %s", e)
                return False
        return False


# Backwards-compatible names for older imports.
ClaudeRunner = AgentRunner
AVAILABLE_MODELS = ["default", "gpt-5.1-codex", "gpt-5.1", "gpt-5", "opus", "sonnet", "haiku"]
