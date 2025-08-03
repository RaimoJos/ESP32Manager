"""Base plugin infrastructure for ESP32Manager."""
from __future__ import annotations
from typing import Any, Optional

class BasePlugin:
    """Base class for all plugins.

    Plugins should :class:`BasePlugin` and override the
    :meth:`load` and :meth:`execute` methods. The project manager will
    instantiate plugins and call :meth:`load` when the application
    starts. The :meth:`execute` method acts as a generic entry point for
    plugin functionality and can be implemented in whatever fashion the
    plugin requires (for example command dispatch)."""

    name: str = "base"

    def __init__(self, manager: Optional["ProjectManager"] = None) -> None:
        self.manager = manager

    def load(self) -> None:
        """Called after the plugin is instantiated."""
        # Default implementation does nothing
        return None

    def unload(self) -> None:
        """Hook called when plugin is unloaded."""
        return None

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the plugin's main functionality."""

        raise NotImplementedError