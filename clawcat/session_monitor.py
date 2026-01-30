"""Session activity monitor window for ClawCat.

This script displays a tkinter window showing session activity logs.
It's launched as a separate process when a new session starts.
"""

import sys
import tkinter as tk
from tkinter import scrolledtext
from pathlib import Path


class SessionMonitorWindow:
    """A tkinter window showing session activity."""

    def __init__(self, session_id: str, session_name: str, log_file: Path):
        """Initialize the monitor window.

        Args:
            session_id: The Claude session ID.
            session_name: Display name for the session.
            log_file: Path to the activity log file.
        """
        self.session_id = session_id
        self.session_name = session_name
        self.log_file = log_file
        self.last_position = 0

        # Create window
        self.root = tk.Tk()
        self.root.title(f"ClawCat: {session_name}")
        self.root.geometry("900x600")
        self.root.configure(bg="#1a1a2e")

        # Configure grid
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Header frame
        header_frame = tk.Frame(self.root, bg="#16213e", padx=10, pady=8)
        header_frame.grid(row=0, column=0, sticky="ew")

        # Title
        title = tk.Label(
            header_frame,
            text=f"ClawCat Session Monitor",
            font=("Segoe UI", 14, "bold"),
            bg="#16213e",
            fg="#00ff88"
        )
        title.pack(side="left")

        # Session info
        session_info = tk.Label(
            header_frame,
            text=f"  |  {session_name}  |  ID: {session_id[:8] if len(session_id) > 8 else session_id}",
            font=("Consolas", 10),
            bg="#16213e",
            fg="#aaaaaa"
        )
        session_info.pack(side="left")

        # Status indicator
        self.status_label = tk.Label(
            header_frame,
            text="Waiting for activity...",
            font=("Consolas", 9),
            bg="#16213e",
            fg="#888888"
        )
        self.status_label.pack(side="right")

        # Log display
        self.log_display = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#0f0f1a",
            fg="#e0e0e0",
            insertbackground="#00ff88",
            selectbackground="#3d5a80",
            padx=10,
            pady=10,
            borderwidth=0,
            highlightthickness=0
        )
        self.log_display.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Configure text tags for styling
        self.log_display.tag_configure("timestamp", foreground="#888888")
        self.log_display.tag_configure("info", foreground="#00ff88")
        self.log_display.tag_configure("warning", foreground="#ffaa00")
        self.log_display.tag_configure("error", foreground="#ff4444")
        self.log_display.tag_configure("instruction", foreground="#66ccff")

        # Initial message
        self._append_log("Session monitor started. Waiting for Claude CLI activity...\n", "info")

        # Start polling
        self.poll_log()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _append_log(self, text: str, tag: str = None) -> None:
        """Append text to the log display.

        Args:
            text: Text to append.
            tag: Optional tag for styling.
        """
        self.log_display.configure(state="normal")
        if tag:
            self.log_display.insert(tk.END, text, tag)
        else:
            self.log_display.insert(tk.END, text)
        self.log_display.see(tk.END)
        self.log_display.configure(state="disabled")

    def poll_log(self) -> None:
        """Check for new log entries."""
        try:
            if self.log_file.exists():
                with open(self.log_file, "r", encoding="utf-8") as f:
                    f.seek(self.last_position)
                    new_content = f.read()
                    if new_content:
                        self._append_log(new_content)
                        self.status_label.configure(text="Active", fg="#00ff88")
                    self.last_position = f.tell()
        except Exception:
            pass

        # Poll every 500ms
        self.root.after(500, self.poll_log)

    def on_close(self) -> None:
        """Handle window close."""
        self.root.destroy()

    def run(self) -> None:
        """Run the main loop."""
        self.root.mainloop()


def main():
    """Entry point when run as script."""
    if len(sys.argv) < 4:
        print("Usage: session_monitor.py <session_id> <session_name> <log_file>")
        print("This script is normally launched automatically by ClawCat.")
        sys.exit(1)

    session_id = sys.argv[1]
    session_name = sys.argv[2]
    log_file = Path(sys.argv[3])

    window = SessionMonitorWindow(session_id, session_name, log_file)
    window.run()


if __name__ == "__main__":
    main()
