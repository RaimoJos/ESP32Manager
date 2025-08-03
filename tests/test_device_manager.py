from pathlib import Path

from esp32_manager.core.device_manager import ESP32DeviceManager, DeviceInfo, DeviceState


def test_connect_device(monkeypatch, tmp_path):
    manager = ESP32DeviceManager(tmp_path)
    info = DeviceInfo(port='COM1')
    manager.devices['COM1'] = info

    class DummySerialConnection:
        def __init__(self, port, baud_rate=115200, timeout=5.0):
            self.port = port
            self.baud_rate = baud_rate
            self.timeout = timeout
            self.is_connected = False
            self.connection = object()

        def connect(self):
            self.is_connected = True
            return True

        def disconnect(self):
            self.is_connected = False

    monkeypatch.setattr('esp32_manager.core.device_manager.SerialConnection', DummySerialConnection)

    assert manager.connect_device('COM1')
    assert manager.devices['COM1'].state == DeviceState.CONNECTED
    assert manager.get_connection('COM1').is_connected