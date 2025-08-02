"""
ESP32 Hardware Simulation Stubs
===============================

This module provides simulation stubs for ESP32 hardware components
to allow local testing and development without physical hardware.
"""

import time
import threading
import random
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Global simulation state
_simulation_state = {
    'pins': {},
    'timers': {},
    'uart_devices': {},
    'i2c_devices': {},
    'spi_devices': {},
    'running': True,
    'start_time': time.time(),
}


@dataclass
class PinState:
    """Represents the state of a GPIO pin."""
    pin_num: int
    mode: int = 0  # 0=input, 1=output
    value: int = 0
    pull: Optional[int] = None
    irq_handler: Optional[Callable] = None
    irq_trigger: int = 0
    last_change: float = field(default_factory=time.time)


class Pin:
    """Simulated GPIO Pin class."""

    # Pin modes
    IN = 0
    OUT = 1
    OPEN_DRAIN = 2

    # Pull resistors
    PULL_UP = 1
    PULL_DOWN = 2

    # IRQ triggers
    IRQ_FALLING = 1
    IRQ_RISING = 2
    IRQ_LOW_LEVEL = 4
    IRQ_HIGH_LEVEL = 8

    def __init__(self, pin_num: int, mode: int = IN, pull: Optional[int] = None, value: Optional[int] = None):
        self.pin_num = pin_num

        # Initialize pin state if not exists
        if pin_num not in _simulation_state['pins']:
            _simulation_state['pins'][pin_num] = PinState(pin_num)

        self.state = _simulation_state['pins'][pin_num]

        # Configure pin
        self.init(mode, pull, value)

        logger.debug(f"Pin {pin_num} initialized: mode={mode}, pull={pull}, value={value}")

    def init(self, mode: int, pull: Optional[int] = None, value: Optional[int] = None):
        """Initialize pin configuration."""
        self.state.mode = mode
        self.state.pull = pull

        if value is not None:
            self.state.value = value
        elif mode == self.IN and pull == self.PULL_UP:
            self.state.value = 1
        elif mode == self.IN and pull == self.PULL_DOWN:
            self.state.value = 0

    def value(self, val: Optional[int] = None) -> int:
        """Get or set pin value."""
        if val is not None:
            if self.state.mode == self.OUT:
                old_value = self.state.value
                self.state.value = val
                self.state.last_change = time.time()

                # Simulate LED or other output
                self._simulate_output_change(old_value, val)

                # Trigger IRQ if configured
                self._check_irq_trigger(old_value, val)
            else:
                logger.warning(f"Attempted to write to input pin {self.pin_num}")

        return self.state.value

    def on(self):
        """Set pin high."""
        self.value(1)

    def off(self):
        """Set pin low."""
        self.value(0)

    def irq(self, handler: Optional[Callable] = None, trigger: int = IRQ_FALLING):
        """Configure interrupt."""
        self.state.irq_handler = handler
        self.state.irq_trigger = trigger

        if handler:
            logger.debug(f"IRQ configured on pin {self.pin_num}, trigger={trigger}")

    def _simulate_output_change(self, old_value: int, new_value: int):
        """Simulate output changes (LED, etc.)."""
        if old_value != new_value:
            if self.pin_num == 2:  # Built-in LED
                state = "ON" if new_value else "OFF"
                print(f"💡 Built-in LED: {state}")
            else:
                print(f"📍 GPIO{self.pin_num}: {new_value}")

    def _check_irq_trigger(self, old_value: int, new_value: int):
        """Check and trigger IRQ if conditions are met."""
        if not self.state.irq_handler:
            return

        trigger = False

        if self.state.irq_trigger & self.IRQ_FALLING and old_value == 1 and new_value == 0:
            trigger = True
        elif self.state.irq_trigger & self.IRQ_RISING and old_value == 0 and new_value == 1:
            trigger = True
        elif self.state.irq_trigger & self.IRQ_LOW_LEVEL and new_value == 0:
            trigger = True
        elif self.state.irq_trigger & self.IRQ_HIGH_LEVEL and new_value == 1:
            trigger = True

        if trigger:
            try:
                self.state.irq_handler(self)
                logger.debug(f"IRQ triggered on pin {self.pin_num}")
            except Exception as e:
                logger.error(f"IRQ handler error on pin {self.pin_num}: {e}")


class ADC:
    """Simulated Analog-to-Digital Converter."""

    ATTN_0DB = 0
    ATTN_2_5DB = 1
    ATTN_6DB = 2
    ATTN_11DB = 3

    WIDTH_9BIT = 0
    WIDTH_10BIT = 1
    WIDTH_11BIT = 2
    WIDTH_12BIT = 3

    def __init__(self, pin: Pin, atten: int = ATTN_11DB):
        self.pin = pin
        self.atten = atten
        self._noise_level = 50  # Simulate ADC noise
        logger.debug(f"ADC initialized on pin {pin.pin_num}")

    def read(self) -> int:
        """Read ADC value (simulated)."""
        # Simulate realistic ADC readings
        base_value = random.randint(0, 4095)  # 12-bit ADC
        noise = random.randint(-self._noise_level, self._noise_level)
        value = max(0, min(4095, base_value + noise))

        logger.debug(f"ADC read from pin {self.pin.pin_num}: {value}")
        return value

    def read_u16(self) -> int:
        """Read ADC value as 16-bit."""
        return self.read() << 4  # Scale 12-bit to 16-bit


class PWM:
    """Simulated Pulse Width Modulation."""

    def __init__(self, pin: Pin, freq: int = 1000, duty: int = 512):
        self.pin = pin
        self._freq = freq
        self._duty = duty
        self._running = False
        logger.debug(f"PWM initialized on pin {pin.pin_num}: freq={freq}Hz, duty={duty}")

    def freq(self, frequency: Optional[int] = None) -> int:
        """Get or set PWM frequency."""
        if frequency is not None:
            self._freq = frequency
            logger.debug(f"PWM freq set to {frequency}Hz on pin {self.pin.pin_num}")
        return self._freq

    def duty(self, duty_cycle: Optional[int] = None) -> int:
        """Get or set PWM duty cycle."""
        if duty_cycle is not None:
            self._duty = duty_cycle
            # Simulate PWM output
            percentage = (duty_cycle / 1023) * 100
            print(f"🔄 PWM GPIO{self.pin.pin_num}: {percentage:.1f}% duty")
            logger.debug(f"PWM duty set to {duty_cycle} on pin {self.pin.pin_num}")
        return self._duty

    def duty_u16(self, duty_cycle: Optional[int] = None) -> int:
        """Get or set PWM duty cycle as 16-bit."""
        if duty_cycle is not None:
            self._duty = duty_cycle >> 6  # Convert 16-bit to 10-bit
            percentage = (duty_cycle / 65535) * 100
            print(f"🔄 PWM GPIO{self.pin.pin_num}: {percentage:.1f}% duty")
        return self._duty << 6


class Timer:
    """Simulated Timer."""

    ONE_SHOT = 0
    PERIODIC = 1

    def __init__(self, timer_id: int):
        self.timer_id = timer_id
        self._callback = None
        self._period = 0
        self._mode = self.ONE_SHOT
        self._running = False
        self._thread = None

        _simulation_state['timers'][timer_id] = self
        logger.debug(f"Timer {timer_id} created")

    def init(self, mode: int = ONE_SHOT, period: int = 1000, callback: Optional[Callable] = None):
        """Initialize timer."""
        self._mode = mode
        self._period = period
        self._callback = callback
        logger.debug(f"Timer {self.timer_id} initialized: mode={mode}, period={period}ms")

    def callback(self, handler: Callable):
        """Set timer callback."""
        self._callback = handler

    def start(self):
        """Start timer."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._thread.start()
        logger.debug(f"Timer {self.timer_id} started")

    def stop(self):
        """Stop timer."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        logger.debug(f"Timer {self.timer_id} stopped")

    def _timer_loop(self):
        """Timer execution loop."""
        while self._running:
            time.sleep(self._period / 1000.0)

            if self._callback and self._running:
                try:
                    self._callback(self)
                except Exception as e:
                    logger.error(f"Timer {self.timer_id} callback error: {e}")

            if self._mode == self.ONE_SHOT:
                break

        self._running = False


class UART:
    """Simulated UART communication."""

    def __init__(self, uart_id: int, baudrate: int = 115200, tx: Optional[Pin] = None, rx: Optional[Pin] = None):
        self.uart_id = uart_id
        self.baudrate = baudrate
        self.tx_pin = tx
        self.rx_pin = rx
        self._buffer = []

        _simulation_state['uart_devices'][uart_id] = self
        logger.debug(f"UART {uart_id} initialized: baudrate={baudrate}")

    def write(self, data: bytes):
        """Write data to UART."""
        text = data.decode('utf-8', errors='ignore')
        print(f"📡 UART{self.uart_id} TX: {text.strip()}")
        logger.debug(f"UART {self.uart_id} wrote {len(data)} bytes")

    def read(self, num_bytes: Optional[int] = None) -> Optional[bytes]:
        """Read data from UART."""
        if not self._buffer:
            return None

        if num_bytes is None:
            data = bytes(self._buffer)
            self._buffer.clear()
        else:
            data = bytes(self._buffer[:num_bytes])
            self._buffer = self._buffer[num_bytes:]

        logger.debug(f"UART {self.uart_id} read {len(data)} bytes")
        return data

    def readline(self) -> Optional[bytes]:
        """Read a line from UART."""
        try:
            newline_idx = self._buffer.index(ord('\n'))
            line = bytes(self._buffer[:newline_idx + 1])
            self._buffer = self._buffer[newline_idx + 1:]
            return line
        except ValueError:
            return None

    def any(self) -> int:
        """Check if data is available."""
        return len(self._buffer)


class I2C:
    """Simulated I2C communication."""

    def __init__(self, i2c_id: int, scl: Pin, sda: Pin, freq: int = 100000):
        self.i2c_id = i2c_id
        self.scl = scl
        self.sda = sda
        self.freq = freq
        self._devices = {}  # Simulated I2C devices

        _simulation_state['i2c_devices'][i2c_id] = self
        logger.debug(f"I2C {i2c_id} initialized: SCL=GPIO{scl.pin_num}, SDA=GPIO{sda.pin_num}, freq={freq}Hz")

    def scan(self) -> List[int]:
        """Scan for I2C devices."""
        # Return some simulated device addresses
        devices = [0x48, 0x68, 0x76]  # Common sensor addresses
        logger.debug(f"I2C scan found devices: {[hex(addr) for addr in devices]}")
        return devices

    def writeto(self, addr: int, buf: bytes):
        """Write to I2C device."""
        print(f"📤 I2C write to {hex(addr)}: {buf.hex()}")
        logger.debug(f"I2C wrote {len(buf)} bytes to {hex(addr)}")

    def readfrom(self, addr: int, nbytes: int) -> bytes:
        """Read from I2C device."""
        # Return simulated data
        data = bytes([random.randint(0, 255) for _ in range(nbytes)])
        print(f"📥 I2C read from {hex(addr)}: {data.hex()}")
        logger.debug(f"I2C read {nbytes} bytes from {hex(addr)}")
        return data


class SPI:
    """Simulated SPI communication."""

    MSB = 0
    LSB = 1

    def __init__(self, spi_id: int, baudrate: int = 1000000, polarity: int = 0, phase: int = 0,
                 sck: Optional[Pin] = None, mosi: Optional[Pin] = None, miso: Optional[Pin] = None):
        self.spi_id = spi_id
        self.baudrate = baudrate
        self.polarity = polarity
        self.phase = phase
        self.sck = sck
        self.mosi = mosi
        self.miso = miso

        _simulation_state['spi_devices'][spi_id] = self
        logger.debug(f"SPI {spi_id} initialized: baudrate={baudrate}")

    def write(self, buf: bytes):
        """Write to SPI."""
        print(f"📤 SPI{self.spi_id} write: {buf.hex()}")
        logger.debug(f"SPI wrote {len(buf)} bytes")

    def read(self, nbytes: int) -> bytes:
        """Read from SPI."""
        data = bytes([random.randint(0, 255) for _ in range(nbytes)])
        print(f"📥 SPI{self.spi_id} read: {data.hex()}")
        logger.debug(f"SPI read {nbytes} bytes")
        return data

    def write_readinto(self, write_buf: bytes, read_buf: bytearray):
        """Write and read simultaneously."""
        self.write(write_buf)
        data = self.read(len(read_buf))
        read_buf[:] = data


# Machine module simulation
class machine:
    """Simulated machine module."""

    Pin = Pin
    ADC = ADC
    PWM = PWM
    Timer = Timer
    UART = UART
    I2C = I2C
    SPI = SPI

    @staticmethod
    def freq(frequency: Optional[int] = None) -> int:
        """Get or set CPU frequency."""
        if frequency is not None:
            print(f"🔧 CPU frequency set to {frequency} Hz")
            return frequency
        return 240000000  # Default ESP32 frequency

    @staticmethod
    def unique_id() -> bytes:
        """Get unique device ID."""
        return b'\xde\xad\xbe\xef\x12\x34'  # Simulated ID

    @staticmethod
    def reset():
        """Reset the device."""
        print("🔄 Device reset (simulated)")
        logger.info("Device reset requested")

    @staticmethod
    def soft_reset():
        """Soft reset the device."""
        print("🔄 Soft reset (simulated)")
        logger.info("Soft reset requested")


# Additional simulation utilities
def simulate_button_press(pin_num: int, duration: float = 0.1):
    """Simulate a button press on the specified pin."""
    if pin_num in _simulation_state['pins']:
        pin_state = _simulation_state['pins'][pin_num]
        if pin_state.mode == Pin.IN:
            # Simulate button press (pull low)
            old_value = pin_state.value
            pin_state.value = 0
            pin_state.last_change = time.time()

            # Create a Pin object to trigger IRQ
            pin_obj = Pin(pin_num)
            pin_obj._check_irq_trigger(old_value, 0)

            print(f"🔘 Button press simulated on GPIO{pin_num}")

            # Schedule release
            def release_button():
                time.sleep(duration)
                pin_state.value = 1 if pin_state.pull == Pin.PULL_UP else 0
                pin_state.last_change = time.time()
                pin_obj._check_irq_trigger(0, pin_state.value)
                print(f"🔘 Button released on GPIO{pin_num}")

            threading.Thread(target=release_button, daemon=True).start()
        else:
            logger.warning(f"Pin {pin_num} is not configured as input")
    else:
        logger.warning(f"Pin {pin_num} not initialized")


def simulate_sensor_reading(pin_num: int, value: int):
    """Simulate a sensor reading on an analog pin."""
    if pin_num in _simulation_state['pins']:
        pin_state = _simulation_state['pins'][pin_num]
        pin_state.value = value
        print(f"📊 Sensor reading simulated on GPIO{pin_num}: {value}")
    else:
        logger.warning(f"Pin {pin_num} not initialized")


def get_simulation_state() -> Dict[str, Any]:
    """Get current simulation state."""
    return {
        'pins': {num: {
            'mode': state.mode,
            'value': state.value,
            'pull': state.pull,
            'last_change': state.last_change
        } for num, state in _simulation_state['pins'].items()},
        'uptime': time.time() - _simulation_state['start_time'],
        'running': _simulation_state['running']
    }


def print_simulation_status():
    """Print current simulation status."""
    state = get_simulation_state()

    print("\n" + "=" * 50)
    print("🔍 ESP32 SIMULATION STATUS")
    print("=" * 50)
    print(f"⏱️  Uptime: {state['uptime']:.1f} seconds")
    print(f"▶️  Running: {state['running']}")
    print(f"📍 Active pins: {len(state['pins'])}")

    if state['pins']:
        print("\nPin States:")
        for pin_num, pin_state in state['pins'].items():
            mode = "OUT" if pin_state['mode'] == 1 else "IN"
            pull = ""
            if pin_state['pull'] == 1:
                pull = " (PULL_UP)"
            elif pin_state['pull'] == 2:
                pull = " (PULL_DOWN)"

            print(f"  GPIO{pin_num:2d}: {mode} = {pin_state['value']}{pull}")

    print("=" * 50)


def cleanup_simulation():
    """Clean up simulation resources."""
    _simulation_state['running'] = False

    # Stop all timers
    for timer in _simulation_state['timers'].values():
        timer.stop()

    print("🧹 Simulation cleanup completed")
    logger.info("Simulation cleanup completed")


# Interactive simulation controls
class SimulationControls:
    """Interactive controls for simulation."""

    @staticmethod
    def press_button(pin: int = 0, duration: float = 0.1):
        """Simulate button press."""
        simulate_button_press(pin, duration)

    @staticmethod
    def set_sensor(pin: int, value: int):
        """Set sensor value."""
        simulate_sensor_reading(pin, value)

    @staticmethod
    def status():
        """Show simulation status."""
        print_simulation_status()

    @staticmethod
    def help():
        """Show available commands."""
        print("""
🎮 SIMULATION CONTROLS
=====================

Available commands:
- press_button(pin, duration=0.1)  # Simulate button press
- set_sensor(pin, value)           # Set sensor reading
- status()                         # Show simulation status
- help()                          # Show this help

Example usage:
>>> from utils.hardware_stubs import SimulationControls as sim
>>> sim.press_button(0)           # Press boot button
>>> sim.set_sensor(34, 2048)      # Set ADC reading
>>> sim.status()                  # Show status
        """)


# Module initialization
if __name__ == "__main__":
    print("🔧 ESP32 Hardware Simulation Stubs Loaded")
    print("Use SimulationControls for interactive testing")
    SimulationControls.help()