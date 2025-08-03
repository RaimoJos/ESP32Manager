"""Git integration plugin for ESP32Manager."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .base_plugin import  BasePlugin

class GitIntegrationPlugin(BasePlugin):
    """Simple plugin providing basic Git repository management."""

    name = 'git_integration'

    def load(self) -> None:
        """Verify that Git is available."""
        try:
            subprocess.run(["git", "--version"], check=True, capture_output=True)
        except Exception as exc:
            raise RuntimeError('Git executable not found') from exc

    # Helper methods ----
    @staticmethod
    def _run_git(path: Path, *args: str, **kwargs: Any) -> subprocess.CompletedProcess:
        """Execute a git command im *path* and return the completed process."""
        return subprocess.run(
            ["git", *args],
            cwd=str(path),
            check=True,
            capture_output=True,
            text=True,
            **kwargs,
        )

    # Public API ------------------------------------------------------------------------------
    def execute(self, command: str, *args: str, **kwargs: Any) -> Any:
        """Dispatch *command* to the appropriate method."""
        method = getattr(self, command, None)
        if not callable(method):
            raise ValueError(f"Unknown Git command: {command}")
        return method(**kwargs)

    # Individual commands ----------------------------------
    def __init_repo(self, path: Path) -> str:
        """Initialize a new Gir repository at *path*."""
        self._run_git(path, "init")
        return path.as_posix()

    def commit_all(self, path: Path, message: str) -> None:
        """Commit all changes in the repository with *message*."""
        # Configure identity Locally to avoid global config requirements
        self._run_git(path, "config", "user.email", "esp32@example.com")
        self._run_git(path, "config", "user.name", "ESP32Manager")
        self._run_git(path, "add", "-A")
        self._run_git(path, "commit", "-m", message)

    def get_status(self, path: Path) -> str:
        """Return the short git status for the repository at *path*."""
        result = self._run_git(path, "status", "--short")
        return result.stdout.strip()