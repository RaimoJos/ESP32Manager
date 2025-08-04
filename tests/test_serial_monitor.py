import time
from pathlib import Path

from esp32_manager.utils.serial_monitor import SerialMonitor

class DummyConnection:
    """Sample serial connection stub for testing."""

    def __init__(self, lines: list[bytes]):
        self.lines = lines

    def readline(self) -> bytes:  # pragma: no cover - exercised via thread
        if self.lines:
            return self.lines.pop(0)
        time.sleep(0.05)
        return b''

def _wait_for(condition, timeout: float  = 1.0):
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return True
        time.sleep(0.05)
    return False

def test_serial_monitor_reads_lines_and_calls_callback(tmp_path: Path):
    lines = [b"hello\n", b"world\n"]
    collected: list[str] = []
    monitor = SerialMonitor(DummyConnection(lines.copy()), callback=collected.append)

    monitor.start()
    _wait_for(lambda: len(collected) >= 2)
    monitor.stop()

    assert any("hello" in line for line in collected)
    assert any('world' in line for line in collected)

def test_serial_monitor_writes_to_log(tmp_path: Path):
    lines = [b"log line\n"]
    collected: list[str] = []
    log_file = tmp_path / "logs" / "serial.log"

    monitor = SerialMonitor(
        DummyConnection(lines.copy()), callback=collected.append, log_file=log_file
    )

    monitor.start()
    _wait_for(lambda: collected)
    monitor.stop()

    assert log_file.exists()
    assert "log line" in log_file.read_text()
    assert monitor._log_handle is None