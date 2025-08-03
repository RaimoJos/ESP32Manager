"""Serial monitor utility for ESP32 devices.

This module provides :class:`SerialMonitor`, a small helper that reads
from a serial connection in a background thread.  Each line of output is
timestamped and can optionally be written to a log file.  Callbacks can
be registered to receive the processed text.

The monitor exposes :py:meth:`start` and :py:meth:`stop` methods for
controlling the background thread.  It is designed to work with the
``SerialConnection`` class used by :mod:`esp32_manager`, but it will also
operate with any object that implements ``readline``.
"""

from __future__ import annotations

from datetime import datetime
import threading
import time
from pathlib import Path
from typing import Callable, Optional, TextIO, TYPE_CHECKING
import logging

if TYPE_CHECKING:  # pragma: no cover - used only for type hints
    from ..core.device_manager import SerialConnection


logger = logging.getLogger(__name__)


class SerialMonitor:
    """Continuously read from a serial connection.

    Parameters
    ----------
    connection:
        An established :class:`~esp32_manager.core.device_manager.SerialConnection`
        or any object providing a ``readline`` method.
    callback:
        Optional function called with each line of text (timestamp included).
        If not provided the lines are written to ``stdout`` via
        :func:`print`.
    log_file:
        Optional path to a log file.  If provided, all timestamped lines
        are appended to the file.
    """

    def __init__(
        self,
        connection: "SerialConnection",
        callback: Optional[Callable[[str], None]] = None,
        log_file: Optional[Path] = None,
    ) -> None:
        self.connection = connection
        self.callback = callback or (lambda line: print(line))
        self.log_file_path = Path(log_file) if log_file else None

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._log_handle: Optional[TextIO] = None

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start monitoring the serial connection."""

        if self._thread and self._thread.is_alive():
            return

        if self.log_file_path:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = self.log_file_path.open("a", encoding="utf-8")

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def stop(self) -> None:
        """Stop monitoring and clean up resources."""

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

        if self._log_handle:
            try:
                self._log_handle.close()
            except Exception:  # pragma: no cover - close best effort
                logger.debug("Failed to close log file", exc_info=True)
            finally:
                self._log_handle = None

    # ------------------------------------------------------------------
    def _read_loop(self) -> None:
        """Background thread that reads and processes serial data."""

        while not self._stop_event.is_set():
            try:
                line = self.connection.readline()  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - hardware errors
                logger.error(f"Serial read failed: {exc}")
                time.sleep(0.1)
                continue

            if not line:
                # Small sleep to prevent busy waiting when no data
                time.sleep(0.05)
                continue

            try:
                text = line.decode("utf-8", errors="ignore").rstrip()
            except Exception:  # pragma: no cover - decoding errors
                logger.debug("Failed to decode serial data", exc_info=True)
                continue

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            formatted = f"[{timestamp}] {text}"

            try:
                self.callback(formatted + "\n")
            except Exception:  # pragma: no cover - callback safety
                logger.debug("Serial monitor callback failed", exc_info=True)

            if self._log_handle:
                try:
                    self._log_handle.write(formatted + "\n")
                    self._log_handle.flush()
                except Exception:  # pragma: no cover - disk errors
                    logger.debug("Failed to write serial log", exc_info=True)


__all__ = ["SerialMonitor"]