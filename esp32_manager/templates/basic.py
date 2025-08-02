from typing import Dict
from . import BaseTemplate


class BasicTemplate(BaseTemplate):
    """Basic ESP32 project template with minimal functionality."""

    description = "Basic ESP32 project with LED control and basic I/O"
    author = "ESP32Manager"
    version = "1.0.0"
    features = [
        "Built-in LED control",
        "GPIO pin management",
        "Basic timer functionality",
        "Serial communication",
        "Error handling"
    ]
    dependencies = []

    def generate_files(self) -> Dict[str, str]:
        """Generate all project files."""
        files = self.get_common_files()

        # Add template-specific files
        files.update({
            'src/main.py': self._generate_main(),
            'src/config.py': self._generate_config(),
            'src/utils.py': self._generate_utils(),
            'tests/test_main.py': self._generate_tests(),
            'docs/API.md': self._generate_api_docs(),
            'assets/pinout.txt': self._generate_pinout(),
        })

        return files

    def _get_usage_instructions(self) -> str:
        """Get basic template usage instructions."""
        return """1. The built-in LED will blink every second
2. Press the boot button to toggle LED state
3. Check serial output for status messages
4. Modify `src/config.py` to customize behavior"""

    def _generate_main(self) -> str:
        """Generate main.py file."""
        return '''"""
ESP32 Basic Project - Main Application
Created with ESP32Manager Basic Template
"""

import time
import machine
from config import Config
from utils import logger, handle_error

# Initialize hardware
led = machine.Pin(Config.LED_PIN, machine.Pin.OUT)
button = machine.Pin(Config.BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

# State variables
led_state = False
last_button_state = True
last_toggle_time = 0

def setup():
    """Initialize the application."""
    logger("Starting ESP32 Basic Project...")
    logger(f"LED Pin: {Config.LED_PIN}")
    logger(f"Button Pin: {Config.BUTTON_PIN}")
    logger(f"Blink Interval: {Config.BLINK_INTERVAL}ms")

    # Turn off LED initially
    led.off()
    logger("Setup complete!")

def toggle_led():
    """Toggle LED state."""
    global led_state
    led_state = not led_state

    if led_state:
        led.on()
        logger("LED: ON")
    else:
        led.off()
        logger("LED: OFF")

def check_button():
    """Check button state and handle presses."""
    global last_button_state, last_toggle_time

    current_button_state = button.value()
    current_time = time.ticks_ms()

    # Button pressed (with debounce)
    if not current_button_state and last_button_state:
        if time.ticks_diff(current_time, last_toggle_time) > Config.DEBOUNCE_TIME:
            toggle_led()
            last_toggle_time = current_time
            logger("Button pressed - LED toggled")

    last_button_state = current_button_state

def main_loop():
    """Main application loop."""
    logger("Entering main loop...")
    last_blink_time = time.ticks_ms()

    try:
        while True:
            current_time = time.ticks_ms()

            # Check button
            check_button()

            # Auto-blink LED if enabled
            if Config.AUTO_BLINK:
                if time.ticks_diff(current_time, last_blink_time) >= Config.BLINK_INTERVAL:
                    toggle_led()
                    last_blink_time = current_time

            # Small delay to prevent excessive CPU usage
            time.sleep_ms(Config.LOOP_DELAY)

    except KeyboardInterrupt:
        logger("Program interrupted by user")
    except Exception as e:
        handle_error("Main loop error", e)
    finally:
        # Cleanup
        led.off()
        logger("Program terminated")

def main():
    """Application entry point."""
    try:
        setup()
        main_loop()
    except Exception as e:
        handle_error("Fatal error", e)

if __name__ == "__main__":
    main()
'''

    def _generate_config(self) -> str:
        """Generate config.py file."""
        return '''"""
ESP32 Basic Project Configuration
Modify these settings to customize behavior
"""

class Config:
    """Project configuration constants."""

    # Hardware Configuration
    LED_PIN = 2          # Built-in LED pin (GPIO2 on most ESP32 boards)
    BUTTON_PIN = 0       # Boot button (GPIO0 on most ESP32 boards)

    # Timing Configuration
    BLINK_INTERVAL = 1000    # LED blink interval in milliseconds
    DEBOUNCE_TIME = 200      # Button debounce time in milliseconds
    LOOP_DELAY = 50          # Main loop delay in milliseconds

    # Feature Flags
    AUTO_BLINK = True        # Enable automatic LED blinking
    VERBOSE_LOGGING = True   # Enable detailed logging

    # Serial Configuration
    BAUD_RATE = 115200      # Serial communication baud rate

    # Project Information
    PROJECT_NAME = "ESP32 Basic Project"
    VERSION = "1.0.0"
    AUTHOR = "ESP32Manager"

# Validate configuration
def validate_config():
    """Validate configuration settings."""
    errors = []

    if not (0 <= Config.LED_PIN <= 39):
        errors.append(f"Invalid LED_PIN: {Config.LED_PIN}")

    if not (0 <= Config.BUTTON_PIN <= 39):
        errors.append(f"Invalid BUTTON_PIN: {Config.BUTTON_PIN}")

    if Config.BLINK_INTERVAL < 100:
        errors.append(f"BLINK_INTERVAL too small: {Config.BLINK_INTERVAL}")

    if Config.DEBOUNCE_TIME < 50:
        errors.append(f"DEBOUNCE_TIME too small: {Config.DEBOUNCE_TIME}")

    if errors:
        raise ValueError("Configuration errors: " + ", ".join(errors))

    return True

# Run validation on import
if __name__ != "__main__":
    validate_config()
'''

    def _generate_utils(self) -> str:
        """Generate utils.py file."""
        return '''"""
ESP32 Basic Project Utilities
Common utility functions and helpers
"""

import time
import sys
import gc
from config import Config

def logger(message, level="INFO"):
    """Simple logging function."""
    if Config.VERBOSE_LOGGING or level in ["ERROR", "CRITICAL"]:
        timestamp = time.ticks_ms()
        print(f"[{timestamp:08d}] {level}: {message}")

def handle_error(context, error):
    """Handle and log errors."""
    error_msg = f"{context}: {str(error)}"
    logger(error_msg, "ERROR")

    # Optional: Save error to file or take corrective action
    if hasattr(error, '__traceback__'):
        logger("Error details available in traceback", "DEBUG")

def get_system_info():
    """Get system information."""
    import machine

    info = {
        'platform': sys.platform,
        'version': sys.version,
        'implementation': sys.implementation,
        'freq': machine.freq(),
        'unique_id': machine.unique_id(),
        'free_memory': gc.mem_free(),
        'allocated_memory': gc.mem_alloc(),
    }

    return info

def print_system_info():
    """Print system information."""
    logger("=== System Information ===")
    info = get_system_info()

    for key, value in info.items():
        if key == 'unique_id':
            # Convert bytes to hex string
            value = ''.join([f'{b:02x}' for b in value])
        elif key in ['free_memory', 'allocated_memory']:
            # Format memory in KB
            value = f"{value / 1024:.1f} KB"
        elif key == 'freq':
            # Format frequency in MHz
            value = f"{value / 1000000:.0f} MHz"

        logger(f"{key}: {value}")

    logger("=" * 30)

def memory_cleanup():
    """Perform memory cleanup."""
    before = gc.mem_free()
    gc.collect()
    after = gc.mem_free()

    if Config.VERBOSE_LOGGING:
        freed = after - before
        logger(f"Memory cleanup: freed {freed} bytes")

def safe_sleep(duration_ms):
    """Safe sleep function that handles interrupts."""
    try:
        time.sleep_ms(duration_ms)
    except KeyboardInterrupt:
        logger("Sleep interrupted by user", "WARNING")
        raise

def format_uptime(start_time):
    """Format uptime from start time."""
    uptime_ms = time.ticks_diff(time.ticks_ms(), start_time)

    seconds = uptime_ms // 1000
    minutes = seconds // 60
    hours = minutes // 60

    if hours > 0:
        return f"{hours}h {minutes % 60}m {seconds % 60}s"
    elif minutes > 0:
        return f"{minutes}m {seconds % 60}s"
    else:
        return f"{seconds}s"

class SimpleTimer:
    """Simple timer class for periodic tasks."""

    def __init__(self, interval_ms):
        self.interval = interval_ms
        self.last_time = time.ticks_ms()

    def is_time(self):
        """Check if timer interval has elapsed."""
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_time) >= self.interval:
            self.last_time = current_time
            return True
        return False

    def reset(self):
        """Reset timer."""
        self.last_time = time.ticks_ms()

class MovingAverage:
    """Simple moving average calculator."""

    def __init__(self, window_size=10):
        self.window_size = window_size
        self.values = []

    def add_value(self, value):
        """Add a value to the moving average."""
        self.values.append(value)
        if len(self.values) > self.window_size:
            self.values.pop(0)

    def get_average(self):
        """Get current moving average."""
        if not self.values:
            return 0
        return sum(self.values) / len(self.values)

    def reset(self):
        """Reset the moving average."""
        self.values.clear()
'''

    def _generate_tests(self) -> str:
        """Generate test file."""
        return '''"""
Tests for ESP32 Basic Project
Run these tests to verify functionality
"""

import unittest
import time
from unittest.mock import Mock, patch

# Mock machine module for testing
import sys
sys.modules['machine'] = Mock()

# Import modules to test
from src.config import Config, validate_config
from src.utils import logger, SimpleTimer, MovingAverage

class TestConfig(unittest.TestCase):
    """Test configuration validation."""

    def test_config_validation(self):
        """Test that config validation passes."""
        self.assertTrue(validate_config())

    def test_config_values(self):
        """Test config values are reasonable."""
        self.assertGreaterEqual(Config.LED_PIN, 0)
        self.assertLessEqual(Config.LED_PIN, 39)
        self.assertGreater(Config.BLINK_INTERVAL, 0)
        self.assertGreater(Config.DEBOUNCE_TIME, 0)

class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def test_logger(self):
        """Test logger function."""
        # Should not raise any exceptions
        logger("Test message")
        logger("Test error", "ERROR")

    def test_simple_timer(self):
        """Test SimpleTimer class."""
        timer = SimpleTimer(100)  # 100ms interval

        # Should not be time immediately
        self.assertFalse(timer.is_time())

        # Mock time passage
        with patch('time.ticks_ms') as mock_time:
            mock_time.side_effect = [0, 0, 150]  # 150ms later
            timer.last_time = 0
            self.assertTrue(timer.is_time())

    def test_moving_average(self):
        """Test MovingAverage class."""
        avg = MovingAverage(window_size=3)

        # Test empty average
        self.assertEqual(avg.get_average(), 0)

        # Test with values
        avg.add_value(10)
        avg.add_value(20)
        avg.add_value(30)
        self.assertEqual(avg.get_average(), 20)

        # Test window overflow
        avg.add_value(40)  # Should remove 10
        self.assertEqual(avg.get_average(), 30)  # (20+30+40)/3

class TestIntegration(unittest.TestCase):
    """Integration tests."""

    @patch('machine.Pin')
    def test_hardware_init(self, mock_pin):
        """Test hardware initialization."""
        # Mock the Pin class
        mock_pin.return_value = Mock()

        # Import and test main module
        try:
            from src import main
            # If import succeeds, basic structure is correct
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed to import main module: {e}")

def run_tests():
    """Run all tests."""
    print("Running ESP32 Basic Project Tests...")
    print("=" * 40)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\\n" + "=" * 40)
    tests_run = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)

    print(f"Tests run: {tests_run}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")

    if failures == 0 and errors == 0:
        print("All tests PASSED! ✓")
        return True
    else:
        print("Some tests FAILED! ✗")
        return False

if __name__ == "__main__":
    run_tests()
'''

    def _generate_api_docs(self) -> str:
        """Generate API documentation."""
        return f'''# {self.project_name} API Documentation

## Overview
This document describes the API and structure of the Basic ESP32 project.

## Modules

### main.py
Main application entry point and control logic.

#### Functions
- `setup()` - Initialize hardware and configuration
- `toggle_led()` - Toggle LED state
- `check_button()` - Check button state with debouncing
- `main_loop()` - Main application loop
- `main()` - Application entry point

### config.py
Project configuration and settings.

#### Classes
- `Config` - Configuration constants and settings

#### Functions
- `validate_config()` - Validate configuration parameters

### utils.py
Utility functions and helper classes.

#### Functions
- `logger(message, level)` - Logging function
- `handle_error(context, error)` - Error handling
- `get_system_info()` - Get system information
- `print_system_info()` - Print system information
- `memory_cleanup()` - Perform garbage collection
- `safe_sleep(duration_ms)` - Safe sleep with interrupt handling
- `format_uptime(start_time)` - Format uptime string

#### Classes
- `SimpleTimer(interval_ms)` - Simple timer for periodic tasks
- `MovingAverage(window_size)` - Moving average calculator

## Hardware Configuration

### Default Pins
- LED: GPIO2 (built-in LED)
- Button: GPIO0 (boot button)

### Customization
Modify `config.py` to change pin assignments and behavior.

## Usage Examples

### Basic Usage
```python
from config import Config
from utils import logger, SimpleTimer

# Create a timer
timer = SimpleTimer(1000)  # 1 second

# Use in loop
while True:
    if timer.is_time():
        logger("Timer fired!")
```

### Custom Pin Configuration
```python
# In config.py
class Config:
    LED_PIN = 5      # Change to GPIO5
    BUTTON_PIN = 4   # Change to GPIO4
```

## Error Handling
The project includes comprehensive error handling:
- Configuration validation
- Hardware initialization errors
- Runtime exceptions
- Memory management

## Testing
Run tests with:
```bash
python -m unittest tests.test_main
```
'''

    def _generate_pinout(self) -> str:
        """Generate pinout reference."""
        return '''ESP32 Basic Project - Pin Reference

Default Pin Configuration:
========================
GPIO2  - Built-in LED (Output)
GPIO0  - Boot Button (Input with Pull-up)

Available GPIO Pins:
==================
GPIO0  - Boot button, also available for input
GPIO1  - TX (Serial) - avoid if using serial
GPIO2  - Built-in LED, also available for I/O
GPIO3  - RX (Serial) - avoid if using serial
GPIO4  - General purpose I/O
GPIO5  - General purpose I/O
GPIO12 - General purpose I/O (note: bootstrap pin)
GPIO13 - General purpose I/O
GPIO14 - General purpose I/O
GPIO15 - General purpose I/O (note: bootstrap pin)
GPIO16 - General purpose I/O
GPIO17 - General purpose I/O
GPIO18 - General purpose I/O
GPIO19 - General purpose I/O
GPIO21 - General purpose I/O (I2C SDA default)
GPIO22 - General purpose I/O (I2C SCL default)
GPIO23 - General purpose I/O
GPIO25 - DAC1, general purpose I/O
GPIO26 - DAC2, general purpose I/O
GPIO27 - General purpose I/O
GPIO32 - ADC1, general purpose I/O
GPIO33 - ADC1, general purpose I/O
GPIO34 - ADC1, input only
GPIO35 - ADC1, input only
GPIO36 - ADC1, input only (VP)
GPIO39 - ADC1, input only (VN)

Notes:
=====
- GPIO6-11 are connected to flash memory (do not use)
- GPIO34-39 are input only
- GPIO0, 2, 12, 15 have bootstrap functions
- Some pins may not be available on all boards

Recommended for beginners:
========================
- GPIO4, 5, 16, 17, 18, 19, 21, 22, 23 are safe choices
- Use GPIO32, 33 for analog input (ADC)
- Use GPIO25, 26 for analog output (DAC)
'''