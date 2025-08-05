# noinspection SqlNoDataSource
"""
ESP32 Device Manager
===================

Manages ESP32 device connections, firmware, file transfers, and communication.
Handles multiple devices, automatic detection, and deployment operations.
"""

import sys
import time
import serial
import serial.tools.list_ports
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

from ..utils.serial_monitor import SerialMonitor

logger = logging.getLogger(__name__)

class DeviceState(Enum):
    """ESP32 device states."""
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    BUSY = "busy"
    FLASHING = "flashing"
    RUNNING = "running"
    ERROR = "error"

@dataclass
class DeviceInfo:
    """Information about an ESP32 device."""
    port: str
    name: str = "ESP32"
    chip_type: str = "ESP32"
    mac_address: str = ""
    flash_size: str = "4MB"
    firmware_version: str = ""
    state: DeviceState = DeviceState.UNKNOWN
    last_seen: float = field(default_factory=time.time)
    baud_rate: int = 115200
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'port': self.port,
            'name': self.name,
            'chip_type': self.chip_type,
            'mac_address': self.mac_address,
            'flash_size': self.flash_size,
            'firmware_version': self.firmware_version,
            'state': self.state.value,
            'last_seen': self.last_seen,
            'baud_rate': self.baud_rate,
            'description': self.description
        }

@dataclass
class FileTransferResult:
    """Result of file transfer operation."""
    success: bool
    files_transferred: int
    bytes_transferred: int
    transfer_time: float
    errors: List[str] = field(default_factory=list)

class SerialConnection:
    """Manages serial connection to ESP32."""

    def __init__(self, port: str, baud_rate: int = 115200, timeout: float = 5.0):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.connection: Optional[serial.Serial] = None
        self.is_connected = False

    def connect(self) -> bool:
        """Establish serial connection."""
        try:
            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            self.is_connected = True
            logger.debug(f"Connected to {self.port} at {self.baud_rate} baud")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Close serial connection."""
        if self.connection and self.connection.is_open:
            self.connection.close()
        self.is_connected = False
        logger.debug(f"Disconnected from {self.port}")

    def write(self, data: bytes) -> bool:
        """Write data to device."""
        if not self.is_connected or not self.connection:
            return False

        try:
            self.connection.write(data)
            self.connection.flush()
            return True
        except Exception as e:
            logger.error(f"Write error: {e}")
            return False

    def read(self, size: int = 1) -> bytes:
        """Read data from device."""
        if not self.is_connected or not self.connection:
            return b''

        try:
            return self.connection.read(size)
        except Exception as e:
            logger.error(f"Read error: {e}")
            return b''

    def readline(self) -> bytes:
        """Read a line from device."""
        if not self.is_connected or not self.connection:
            return b''

        try:
            return self.connection.readline()
        except Exception as e:
            logger.error(f"Readline error: {e}")
            return b''

    def available(self) -> int:
        """Check how many bytes are available."""
        if not self.is_connected or not self.connection:
            return 0

        return self.connection.in_waiting

    def reset_device(self) -> bool:
        """Reset the ESP32 device."""
        try:
            if self.connection:
                # Toggle DTR to reset ESP32
                self.connection.dtr = False
                time.sleep(0.1)
                self.connection.dtr = True
                time.sleep(0.1)
                self.connection.dtr = False
                logger.info(f"Reset device on {self.port}")
                return True
        except Exception as e:
            logger.error(f"Failed to reset device: {e}")
        return False

class MicroPythonREPL:
    """MicroPython REPL interface."""

    def __init__(self, connection: SerialConnection):
        self.connection = connection
        self.prompt = b'>>> '
        self.continuation_prompt = b'... '

    def enter_repl(self) -> bool:
        """Enter REPL mode."""
        try:
            # Send Ctrl+C to interrupt any running program
            self.connection.write(b'\x03')
            time.sleep(0.1)

            # Send Ctrl+B to enter normal REPL mode
            self.connection.write(b'\x02')
            time.sleep(0.5)

            # Clear any pending input
            while self.connection.available():
                self.connection.read(self.connection.available())

            # Send empty line to get prompt
            self.connection.write(b'\r\n')

            # Wait for prompt
            return self.wait_for_prompt()

        except Exception as e:
            logger.error(f"Failed to enter REPL: {e}")
            return False

    def wait_for_prompt(self, timeout: float = 5.0) -> bool:
        """Wait for REPL prompt."""
        start_time = time.time()
        buffer = b''

        while time.time() - start_time < timeout:
            if self.connection.available():
                data = self.connection.read(self.connection.available())
                buffer += data

                if buffer.endswith(self.prompt) or buffer.endswith(self.continuation_prompt):
                    return True

            time.sleep(0.01)

        return False

    def execute_command(self, command: str, timeout: float = 10.0) -> Tuple[bool, str]:
        """Execute a command in REPL."""
        try:
            # Send command
            self.connection.write(command.encode() + b'\r\n')

            # Collect response
            start_time = time.time()
            response = b''

            while time.time() - start_time < timeout:
                if self.connection.available():
                    data = self.connection.read(self.connection.available())
                    response += data

                    if response.endswith(self.prompt):
                        # Remove echo and prompt
                        response_str = response.decode('utf-8', errors='ignore')
                        lines = response_str.split('\r\n')

                        # Remove command echo and prompt
                        if len(lines) > 2:
                            result = '\r\n'.join(lines[1:-1])
                        else:
                            result = ''

                        return True, result

                time.sleep(0.01)

            return False, "Timeout waiting for response"

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return False, str(e)

    def upload_file(self, local_path: Path, remote_path: str) -> bool:
        """Upload file to device."""
        try:
            with open(local_path, 'rb') as f:
                content = f.read()

            # Create file upload command
            encoded_content = content.hex()
            command = f"""
with open('{remote_path}', 'wb') as f:
    f.write(bytes.fromhex('{encoded_content}'))
"""

            success, response = self.execute_command(command, timeout=30.0)

            if success and 'Error' not in response:
                logger.info(f"Uploaded {local_path} -> {remote_path}")
                return True
            else:
                logger.error(f"Upload failed: {response}")
                return False

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False

    def download_file(self, remote_path: str, local_path: Path) -> bool:
        """Download file from device."""
        try:
            command = f"""
try:
    with open('{remote_path}', 'rb') as f:
        content = f.read()
    print('FILE_START')
    print(content.hex())
    print('FILE_END')
except Exception as e:
    print('ERROR:', str(e))
"""

            success, response = self.execute_command(command, timeout=30.0)

            if success and 'FILE_START' in response and 'FILE_END' in response:
                # Extract hex content
                lines = response.split('\n')
                hex_content = ''
                in_file = False

                for line in lines:
                    if 'FILE_START' in line:
                        in_file = True
                    elif 'FILE_END' in line:
                        break
                    elif in_file:
                        hex_content += line.strip()

                # Convert hex to bytes and save
                if hex_content:
                    content = bytes.fromhex(hex_content)
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(local_path, 'wb') as f:
                        f.write(content)

                    logger.info(f"Downloaded {remote_path} -> {local_path}")
                    return True

            logger.error(f"Download failed: {response}")
            return False

        except Exception as e:
            logger.error(f"Download error: {e}")
            return False

    def list_files(self, path: str = '/') -> List[str]:
        """List files on device."""
        command = f"""
import os
try:
    files = os.listdir('{path}')
    for f in files:
        print(f)
except Exception as e:
    print('ERROR:', str(e))
"""

        success, response = self.execute_command(command)

        if success and 'ERROR' not in response:
            files = [line.strip() for line in response.split('\n') if line.strip()]
            return files

        return []

class DeviceDetector:
    """Detects and identifies ESP32 devices."""

    ESP32_VID_PID = [
        (0x10C4, 0xEA60),  # Silicon Labs CP210x
        (0x1A86, 0x7523),  # CH340
        (0x0403, 0x6001),  # FTDI FT232
        (0x1A86, 0x55D4),  # CH9102
    ]

    def detect_devices(self) -> List[DeviceInfo]:
        """Detect ESP32 devices."""
        detected_devices: List[DeviceInfo] = []
        ports = serial.tools.list_ports.comports()

        for serial_port in ports:
            if self._is_esp32_device(serial_port):
                device_info = self._create_device_info(serial_port)
                detected_devices.append(device_info)

        return detected_devices

    def _is_esp32_device(self, port) -> bool:
        """Check if port is likely an ESP32 device."""
        # Check VID/PID
        if hasattr(port, 'vid') and hasattr(port, 'pid'):
            if (port.vid, port.pid) in self.ESP32_VID_PID:
                return True

        # Check description
        description = port.description.lower()
        if any(keyword in description for keyword in ['esp32', 'cp210', 'ch340', 'ft232']):
            return True

        # Check device name (Linux/macOS)
        device_info = port.device.lower()
        if any(keyword in device_info for keyword in ['usb', 'tty', 'com']):
            return True

        return False

    @staticmethod
    def _create_device_info(port) -> DeviceInfo:
        """Create DeviceInfo from serial port."""
        device_info = DeviceInfo(
            port=port.device,
            description=port.description,
            state=DeviceState.DISCONNECTED
        )

        # Try to get more info by connecting
        try:
            connection = SerialConnection(port.device)
            if connection.connect():
                repl = MicroPythonREPL(connection)
                if repl.enter_repl():
                    # Get device info
                    success, response = repl.execute_command("import machine; machine.unique_id()")
                    if success:
                        device_info.mac_address = response.strip()

                    success, response = repl.execute_command("import sys; sys.implementation")
                    if success and 'micropython' in response.lower():
                        device_info.firmware_version = "MicroPython"

                    device_info.state = DeviceState.CONNECTED

                connection.disconnect()
        except Exception as e:
            logger.debug(f"Failed to probe device {port.device}: {e}")

        return device_info

class ESP32DeviceManager:
    """Main device manager class."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.devices: Dict[str, DeviceInfo] = {}
        self.connections: Dict[str, SerialConnection] = {}
        self.serial_monitors: Dict[str, SerialMonitor] = {}
        self.detector = DeviceDetector()
        self._scan_thread: Optional[threading.Thread] = None
        self._scanning = False
        self._observers: List[Callable[[str, DeviceInfo], None]] = []

    def add_observer(self, callback: Callable[[str, DeviceInfo], None]):
        """Add device change observer."""
        self._observers.append(callback)

    def _notify_observers(self, event: str, device_info: DeviceInfo):
        """Notify observers of device changes."""
        for callback in self._observers:
            try:
                callback(event, device_info)
            except Exception as e:
                logger.warning(f"Observer callback failed: {e}")

    def start_scanning(self, interval: float = 5.0):
        """Start continuous device scanning."""
        if self._scanning:
            return

        self._scanning = True
        self._scan_thread = threading.Thread(
            target=self._scan_loop,
            args=(interval,),
            daemon=True
        )
        self._scan_thread.start()
        logger.info("Started device scanning")

    def stop_scanning(self):
        """Stop device scanning."""
        self._scanning = False
        if self._scan_thread:
            self._scan_thread.join(timeout=1)
        logger.info("Stopped device scanning")

    def _scan_loop(self, interval: float):
        """Device scanning loop."""
        while self._scanning:
            try:
                self.scan_devices()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Scan loop error: {e}")
                time.sleep(interval)

    def scan_devices(self) -> List[DeviceInfo]:
        """Scan for devices once."""
        detected_devices = self.detector.detect_devices()
        current_ports = {device.port for device in detected_devices}
        previous_ports = set(self.devices.keys())

        # Check for new devices
        for new_dev in detected_devices:
            if new_dev.port not in self.devices:
                self.devices[new_dev.port] = new_dev
                self._notify_observers('device_connected', new_dev)
                logger.info(f"Device connected: {new_dev.port}")
            else:
                # Update existing device info
                self.devices[new_dev.port] = new_dev

        # Check for disconnected devices
        for port in previous_ports - current_ports:
            device = self.devices[port]
            device.state = DeviceState.DISCONNECTED
            self._notify_observers('device_disconnected', device)
            logger.info(f"Device disconnected: {port}")

            # Clean up connection
            if port in self.connections:
                self.connections[port].disconnect()
                del self.connections[port]

        # Remove disconnected devices after a timeout
        current_time = time.time()
        devices_to_remove = []

        for port, device in self.devices.items():
            if (device.state == DeviceState.DISCONNECTED and
                current_time - device.last_seen > 30):  # 30 second timeout
                devices_to_remove.append(port)

        for port in devices_to_remove:
            del self.devices[port]

        return list(self.devices.values())

    def get_devices(self) -> List[DeviceInfo]:
        """Get list of known devices."""
        return list(self.devices.values())

    def get_device(self, port: str) -> Optional[DeviceInfo]:
        """Get device by port."""
        return self.devices.get(port)

    def connect_device(self, port: str, baud_rate: int = 115200) -> bool:
        """Connect to a device."""
        if port not in self.devices:
            logger.error(f"Device {port} not found")
            return False

        if port in self.connections:
            if self.connections[port].is_connected:
                return True
            else:
                self.connections[port].disconnect()

        connection = SerialConnection(port, baud_rate)
        if connection.connect():
            self.connections[port] = connection
            self.devices[port].state = DeviceState.CONNECTED
            self._notify_observers('device_connected', self.devices[port])
            return True

        return False

    def disconnect_device(self, port: str):
        """Disconnect from a device."""
        if port in self.connections:
            self.connections[port].disconnect()
            del self.connections[port]

        if port in self.devices:
            self.devices[port].state = DeviceState.DISCONNECTED
            self._notify_observers('device_disconnected', self.devices[port])

    def start_monitor(self, port: str,
                      callback: Optional[Callable[[str], None]] = None,
                      log_file: Optional[Path] = None) -> bool:
        """Start monitoring serial output from a device."""
        if not self.connect_device(port):
            logger.error(f"Failed to connect to device {port}")
            return False

        if port in self.serial_monitors:
            return True

        connection = self.connections[port]
        monitor = SerialMonitor(connection, callback=callback, log_file=log_file)
        monitor.start()
        self.serial_monitors[port] = monitor
        return True

    def stop_monitor(self, port: str) -> None:
        """Stop monitoring serial output for a device."""
        monitor = self.serial_monitors.pop(port, None)
        if monitor:
            monitor.stop()

    def get_connection(self, port: str) -> Optional[SerialConnection]:
        """Get connection for a device."""
        return self.connections.get(port)

    def deploy_project(self, project_build_path: Path, port: str,
                      progress_callback: Optional[Callable[[str, float], None]] = None) -> FileTransferResult:
        """Deploy project to device."""
        if not self.connect_device(port):
            return FileTransferResult(
                success=False,
                files_transferred=0,
                bytes_transferred=0,
                transfer_time=0,
                errors=["Failed to connect to device"]
            )

        connection = self.connections[port]
        repl = MicroPythonREPL(connection)

        if not repl.enter_repl():
            return FileTransferResult(
                success=False,
                files_transferred=0,
                bytes_transferred=0,
                transfer_time=0,
                errors=["Failed to enter REPL mode"]
            )

        start_time = time.time()
        files_transferred = 0
        bytes_transferred = 0
        errors = []

        try:
            self.devices[port].state = DeviceState.BUSY

            # Get list of files to transfer
            files_to_transfer = []
            src_dir = project_build_path / "src"

            if src_dir.exists():
                for file_path in src_dir.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(src_dir)
                        files_to_transfer.append((file_path, str(relative_path)))

            # Transfer lib directory if exists
            lib_dir = project_build_path / "lib"
            if lib_dir.exists():
                for file_path in lib_dir.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(lib_dir)
                        remote_path = f"lib/{relative_path}"
                        files_to_transfer.append((file_path, remote_path))

            total_files = len(files_to_transfer)

            if progress_callback:
                progress_callback("Starting file transfer", 0.0)

            # Transfer files
            for i, (local_path, remote_path) in enumerate(files_to_transfer):
                try:
                    if repl.upload_file(local_path, remote_path):
                        files_transferred += 1
                        bytes_transferred += local_path.stat().st_size
                    else:
                        errors.append(f"Failed to upload {remote_path}")

                    if progress_callback:
                        progress = (i + 1) / total_files
                        progress_callback(f"Transferred {remote_path}", progress)

                except Exception as e:
                    error_msg = f"Error transferring {remote_path}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # Reset device to run new code
            if progress_callback:
                progress_callback("Resetting device", 1.0)

            connection.reset_device()

            transfer_time = time.time() - start_time
            success = len(errors) == 0

            self.devices[port].state = DeviceState.RUNNING if success else DeviceState.ERROR

            return FileTransferResult(
                success=success,
                files_transferred=files_transferred,
                bytes_transferred=bytes_transferred,
                transfer_time=transfer_time,
                errors=errors
            )

        except Exception as e:
            errors.append(f"Deployment failed: {e}")
            self.devices[port].state = DeviceState.ERROR

            return FileTransferResult(
                success=False,
                files_transferred=files_transferred,
                bytes_transferred=bytes_transferred,
                transfer_time=time.time() - start_time,
                errors=errors
            )

    def backup_device(self, port: str, backup_path: Path) -> bool:
        """Backup files from device."""
        if not self.connect_device(port):
            logger.error(f"Failed to connect to device {port}")
            return False

        connection = self.connections[port]
        repl = MicroPythonREPL(connection)

        if not repl.enter_repl():
            logger.error("Failed to enter REPL mode")
            return False

        try:
            # List files on device
            files = repl.list_files('/')

            backup_path.mkdir(parents=True, exist_ok=True)

            for filename in files:
                if filename.endswith('.py'):
                    local_file = backup_path / filename
                    if repl.download_file(filename, local_file):
                        logger.info(f"Backed up {filename}")
                    else:
                        logger.warning(f"Failed to backup {filename}")

            return True

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    def flash_firmware(self, port: str, firmware_path: Path,
                      progress_callback: Optional[Callable[[str, float], None]] = None) -> bool:
        """Flash MicroPython firmware to device."""
        try:
            if progress_callback:
                progress_callback("Preparing to flash firmware", 0.0)

            # Disconnect if connected
            if port in self.connections:
                self.disconnect_device(port)

            self.devices[port].state = DeviceState.FLASHING

            # Use esptool to flash firmware
            cmd = [
                sys.executable, "-m", "esptool",
                "--port", port,
                "--baud", "460800",
                "write_flash",
                "--flash_size=detect",
                "0x1000", str(firmware_path)
            ]

            if progress_callback:
                progress_callback("Flashing firmware...", 0.5)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Firmware flashed successfully to {port}")
                self.devices[port].state = DeviceState.CONNECTED

                if progress_callback:
                    progress_callback("Firmware flashed successfully", 1.0)

                return True
            else:
                logger.error(f"Firmware flash failed: {result.stderr}")
                self.devices[port].state = DeviceState.ERROR
                return False

        except Exception as e:
            logger.error(f"Firmware flash error: {e}")
            if port in self.devices:
                self.devices[port].state = DeviceState.ERROR
            return False

    def get_device_info(self, port: str) -> Optional[Dict[str, Any]]:
        """Get detailed device information."""
        if not self.connect_device(port):
            return None

        connection = self.connections[port]
        repl = MicroPythonREPL(connection)

        if not repl.enter_repl():
            return None

        info = {}

        try:
            # Get system info
            commands = {
                'unique_id': "import machine; machine.unique_id().hex()",
                'freq': "import machine; machine.freq()",
                'memory_free': "import gc; gc.mem_free()",
                'memory_alloc': "import gc; gc.mem_alloc()",
                'platform': "import sys; sys.platform",
                'version': "import sys; sys.version",
                'implementation': "import sys; sys.implementation.name + ' ' + '.'.join(map(str, sys.implementation.version))"
            }

            for key, command in commands.items():
                success, response = repl.execute_command(command)
                if success:
                    info[key] = response.strip()

            # Get file system info
            success, response = repl.execute_command("import os; os.statvfs('/')")
            if success:
                info['filesystem'] = response.strip()

            return info

        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            return None


    def send_command(self, port: str, command: str) -> bool:
        """Send command to device."""
        if port not in self.connections:
            return False

        connection = self.connections[port]
        data = command.encode() + b'\r\n'
        return connection.write(data)

    def reset_device(self, port: str) -> bool:
        """Reset device."""
        if port not in self.connections:
            return False

        connection = self.connections[port]
        return connection.reset_device()

    def get_device_status(self) -> Dict[str, Any]:
        """Get overall device manager status."""
        return {
            'total_devices': len(self.devices),
            'connected_devices': len([d for d in self.devices.values()
                                    if d.state == DeviceState.CONNECTED]),
            'scanning': self._scanning,
            'devices': [device.to_dict() for device in self.devices.values()]
        }

    def save_device_config(self, config_file: Path):
        """Save device configuration."""
        config = {
            'devices': [device.to_dict() for device in self.devices.values()],
            'timestamp': time.time()
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Device config saved to {config_file}")

    def load_device_config(self, config_file: Path) -> bool:
        """Load device configuration."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            for device_data in config.get('devices', []):
                device = DeviceInfo(
                    port=device_data['port'],
                    name=device_data.get('name', 'ESP32'),
                    chip_type=device_data.get('chip_type', 'ESP32'),
                    mac_address=device_data.get('mac_address', ''),
                    flash_size=device_data.get('flash_size', '4MB'),
                    firmware_version=device_data.get('firmware_version', ''),
                    state=DeviceState(device_data.get('state', 'disconnected')),
                    baud_rate=device_data.get('baud_rate', 115200),
                    description=device_data.get('description', '')
                )
                self.devices[device.port] = device

            logger.info(f"Loaded {len(self.devices)} devices from config")
            return True

        except Exception as e:
            logger.error(f"Failed to load device config: {e}")
            return False

    def cleanup(self):
        """Clean up resources."""
        self.stop_scanning()
        for port in list(self.serial_monitors.keys()):
            self.stop_monitor(port)

        # Disconnect all devices
        for port in list(self.connections.keys()):
            self.disconnect_device(port)

        logger.info("Device manager cleanup completed")

# Utility functions
def detect_esp32_devices() -> List[str]:
    """Quick function to detect ESP32 device ports."""
    detector = DeviceDetector()
    devices = detector.detect_devices()
    return [device.port for device in devices]

def get_device_info_quick(port: str) -> Optional[Dict[str, str]]:
    """Quick device info without full manager setup."""
    try:
        connection = SerialConnection(port)
        if connection.connect():
            repl = MicroPythonREPL(connection)
            if repl.enter_repl():
                quick_info: Dict[str, str] = {}

                success, response = repl.execute_command("import sys; sys.platform")
                if success:
                    quick_info['platform'] = response.strip()

                success, response = repl.execute_command("import machine; machine.unique_id().hex()")
                if success:
                    info['unique_id'] = response.strip()

                connection.disconnect()
                return quick_info

        connection.disconnect()
    except Exception as e:
        logger.debug(f"Failed to get quick device info: {e}")

    return None

if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description="ESP32 Device Manager")
    parser.add_argument("--scan", action="store_true", help="Scan for devices")
    parser.add_argument("--monitor", help="Monitor device output")
    parser.add_argument("--info", help="Get device info")

    args = parser.parse_args()

    if args.scan:
        print("Scanning for ESP32 devices...")
        devices = detect_esp32_devices()
        if devices:
            print(f"Found {len(devices)} device(s):")
            for device in devices:
                print(f"  - {device}")
        else:
            print("No ESP32 devices found")

    elif args.monitor:
        print(f"Monitoring {args.monitor} (Ctrl+C to stop)")

        def output_callback(text):
            print(text, end='')

        manager = ESP32DeviceManager(Path("."))

        try:
            manager.start_monitor(args.monitor, callback=output_callback)
            while True:
                time.sleep(0.1)

        except KeyboardInterrupt:
            manager.start_monitor(args.monitor)
            print("\nMonitoring stopped")
        finally:
            manager.cleanup()

    elif args.info:
        print(f"Getting device info for {args.info}")
        info = get_device_info_quick(args.info)
        if info:
            for key, value in info.items():
                print(f"{key}: {value}")
        else:
            print("Failed to get device info")