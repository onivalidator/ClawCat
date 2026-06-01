"""Session persistence for ClawCat using JSON files."""

import json
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class SessionStore:
    """Persistent storage for sessions using JSON files."""

    def __init__(self, storage_dir: Path):
        """Initialize the session store.

        Args:
            storage_dir: Directory to store session JSON files.
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Session store initialized at: {storage_dir}")

    def _session_file(self, session_id: str) -> Path:
        """Get path to a session's JSON file.

        Args:
            session_id: The local agent session ID.

        Returns:
            Path to the session's JSON file.
        """
        # Sanitize session ID for use as filename.
        safe_id = session_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self.storage_dir / f"{safe_id}.json"

    def save_session(self, session) -> bool:
        """Save a session to disk.

        Args:
            session: Session object to save.

        Returns:
            True if saved successfully, False otherwise.
        """
        agent_session_id = getattr(session, "agent_session_id", None) or getattr(
            session, "claude_session_id", None
        )
        if not agent_session_id:
            logger.warning("Cannot save session without agent_session_id")
            return False

        data = {
            "provider": getattr(session, "provider", "claude"),
            "model": session.model,
            "dangerous_mode": session.dangerous_mode,
            "message_count": session.message_count,
            "agent_session_id": agent_session_id,
            "claude_session_id": agent_session_id,
            "nickname": session.nickname,
            "created_at": session.created_at or time.time(),
            "updated_at": time.time(),
        }

        filepath = self._session_file(agent_session_id)
        temp_path = filepath.with_suffix(".tmp")

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_path.replace(filepath)
            logger.info(f"Session saved: {agent_session_id[:8]}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False

    def load_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data from disk.

        Args:
            session_id: The local agent session ID (full or prefix).

        Returns:
            Session data dict or None if not found.
        """
        # Try exact match first
        filepath = self._session_file(session_id)
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load session {session_id}: {e}")
                return None

        # Try prefix match
        for filepath in self.storage_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    saved_id = data.get("agent_session_id") or data.get("claude_session_id", "")
                    if saved_id.startswith(session_id):
                        return data
            except (json.JSONDecodeError, IOError):
                continue

        return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions.

        Returns:
            List of session metadata dicts, sorted by most recently updated.
        """
        sessions = []

        for filepath in self.storage_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                saved_id = data.get("agent_session_id") or data["claude_session_id"]
                sessions.append({
                    "id": saved_id[:8],
                    "full_id": saved_id,
                    "provider": data.get("provider", "claude"),
                    "nickname": data.get("nickname"),
                    "model": data.get("model"),
                    "messages": data["message_count"],
                    "dangerous_mode": data.get("dangerous_mode", False),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                })

            except (json.JSONDecodeError, KeyError, IOError) as e:
                logger.warning(f"Skipping invalid session file {filepath}: {e}")
                continue

        # Sort by most recently updated
        sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
        return sessions

    def find_session(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Find a session by nickname or ID prefix.

        Args:
            identifier: Nickname or session ID prefix to search for.

        Returns:
            Session metadata dict or None if not found.
        """
        sessions = self.list_sessions()

        for s in sessions:
            # Match by nickname (case-insensitive)
            if s.get("nickname") and s["nickname"].lower() == identifier.lower():
                return s
            # Match by ID prefix
            if s["id"] == identifier or s["full_id"].startswith(identifier):
                return s

        return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a saved session.

        Args:
            session_id: The local agent session ID.

        Returns:
            True if deleted, False if not found.
        """
        filepath = self._session_file(session_id)
        if filepath.exists():
            try:
                filepath.unlink()
                logger.info(f"Session deleted: {session_id[:8]}")
                return True
            except IOError as e:
                logger.error(f"Failed to delete session: {e}")
                return False
        return False
