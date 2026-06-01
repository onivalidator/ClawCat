"""Configuration and runner safety tests."""

import tempfile
import unittest
from pathlib import Path

from clawcat.agent_runner import AgentRunner, Session
from clawcat.config import ConfigError, load_config


class ConfigAndRunnerTests(unittest.TestCase):
    def write_config(self, text: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_codex_defaults_are_safe(self):
        path = self.write_config(
            """
telegram:
  bot_token: "token"
  authorized_user_id: 123
agent:
  working_dir: "."
"""
        )

        cfg = load_config(path)

        self.assertEqual(cfg.agent.provider, "codex")
        self.assertEqual(cfg.agent.executable, "codex")
        self.assertEqual(cfg.agent.sandbox_mode, "read-only")
        self.assertFalse(cfg.agent.allow_dangerous_mode)

    def test_full_access_requires_explicit_dangerous_opt_in(self):
        path = self.write_config(
            """
telegram:
  bot_token: "token"
  authorized_user_id: 123
agent:
  sandbox_mode: "danger-full-access"
"""
        )

        with self.assertRaises(ConfigError):
            load_config(path)

    def test_codex_command_uses_sandbox_without_dangerous_flag(self):
        path = self.write_config(
            """
telegram:
  bot_token: "token"
  authorized_user_id: 123
agent:
  working_dir: "."
  sandbox_mode: "workspace-write"
  skip_git_repo_check: true
"""
        )
        cfg = load_config(path)
        runner = AgentRunner(cfg.agent)

        cmd = runner._build_codex_command(
            "hello",
            Session(provider="codex", model=None),
            Path("/tmp/clawcat-output.txt"),
        )

        self.assertIn("--sandbox", cmd)
        self.assertIn("workspace-write", cmd)
        self.assertIn("--skip-git-repo-check", cmd)
        self.assertIn("--json", cmd)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", cmd)

    def test_dangerous_mode_is_hidden_when_config_disallows_it(self):
        path = self.write_config(
            """
telegram:
  bot_token: "token"
  authorized_user_id: 123
agent:
  working_dir: "."
"""
        )
        cfg = load_config(path)
        runner = AgentRunner(cfg.agent)

        session = runner.create_session(dangerous_mode=True, open_monitor=False)

        self.assertFalse(session.dangerous_mode)


if __name__ == "__main__":
    unittest.main()
