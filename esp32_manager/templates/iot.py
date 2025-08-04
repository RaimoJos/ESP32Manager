from typing import Dict
from . import BaseTemplate

class IoTTemplate(BaseTemplate):
    """IoT project template with Wi-Fi, MQTT, sensors, and web server."""

    description = (
        "Complete IoT solution with WiFi connectivity, MQTT communication, sensor readings, and web interface"
    )
    author = "ESP32Manager"
    version = "1.0.0"
    features = [
        "WiFi connection management",
        "MQTT client with auto-reconnect",
        "Sensor data collection",
        "Web server with REST API",
        "Configuration management",
        "OTA updates support",
        "Data logging to SD card",
        "Real-time dashboard",
    ]
    dependencies = [
        "umqtt.simple",
        "upip",
        "ujson",
    ]

    def generate_files(self) -> Dict[str, str]:
        """Generate all IoT project files."""
        files = self.get_common_files()
        files.update({
            'src/main.py': self._generate_main(),
            'src/config.py': self._generate_config(),
            'src/wifi_manager.py': self._generate_wifi_manager(),
            'src/mqtt_client.py': self._generate_mqtt_client(),
            'src/sensor_manager.py': self._generate_sensor_manager(),
            'src/web_server.py': self._generate_web_server(),
            'src/data_logger.py': self._generate_data_logger(),
            'src/utils.py': self._generate_utils(),
            'tests/test_iot.py': self._generate_tests(),
            'docs/API.md': self._generate_api_docs(),
            'assets/web/index.html': self._generate_web_interface(),
            'assets/web/styles.css': self._generate_web_styles(),
            'assets/web/scripts.js': self._generate_web_scripts(),
            'assets/config.json': self._generate_default_config(),
        })
        return files

    def _get_usage_instructions(self) -> str:
        """Get IoT template usage instructions."""
        return (
            "1. Configure WiFi credentials in config.py\n"
            "2. Set up MQTT broker details\n"
            "3. Configure sensors in sensor_manager.py\n"
            "4. Access web interface at http://<esp32-ip>\n"
            "5. Monitor MQTT topics for sensor data\n"
            "6. Use REST API for remote control"
        )

    @staticmethod
    def _generate_main() -> str:
        """Generate IoT main.py file."""
        return '''"""
ESP32 IoT Project - Main Application
===================================
Complete IoT solution with WiFi, MQTT, sensors, and web interface
"""

import time
import gc
import machine
from config import Config
from wifi_manager import WiFiManager
from mqtt_client import MQTTClient
from sensor_manager import SensorManager
from web_server import WebServer
from data_logger import DataLogger
from utils import logger, handle_error, system_info

# Global objects
wifi = None
mqtt = None
sensors = None
web_server = None
data_logger = None

# Status LED
status_led = machine.Pin(Config.STATUS_LED_PIN, machine.Pin.OUT)

def setup():
    """Initialize all system components."""
    global wifi, mqtt, sensors, web_server, data_logger

    logger("Starting ESP32 IoT System...")
    logger(f"Project: {Config.PROJECT_NAME} v{Config.VERSION}")

    # Show system info
    info = system_info()
    logger(f"Free memory: {info['free_memory']} bytes")
    logger(f"CPU frequency: {info['freq']} Hz")

    try:
        # Initialize WiFi
        logger("Initializing WiFi...")
        wifi = WiFiManager()

        # Initialize sensors
        logger("Initializing sensors...")
        sensors = SensorManager()

        # Initialize data logger
        if Config.ENABLE_DATA_LOGGING:
            logger("Initializing data logger...")
            data_logger = DataLogger()

        # Connect to WiFi
        if wifi.connect():
            logger("WiFi connected successfully")

            # Initialize MQTT
            if Config.ENABLE_MQTT:
                logger("Initializing MQTT...")
                mqtt = MQTTClient(wifi.get_ip())
                if mqtt.connect():
                    logger("MQTT connected successfully")
                else:
                    logger("MQTT connection failed", "WARNING")

            # Initialize web server
            if Config.ENABLE_WEB_SERVER:
                logger("Starting web server...")
                web_server = WebServer(sensors, mqtt, data_logger)
                web_server.start()
                logger(f"Web server started at http://{wifi.get_ip()}")
        else:
            logger("WiFi connection failed", "ERROR")
            # Continue in offline mode

        # Status indication
        status_led.on()
        logger("Setup completed successfully!")

    except Exception as e:
        handle_error("Setup failed", e)
        status_led.off()
        raise


def main_loop():
    """Main application loop."""
    logger("Entering main loop...")

    last_sensor_read = time.time()
    last_mqtt_publish = time.time()
    last_gc_collect = time.time()
    last_status_check = time.time()

    sensor_data = {}

    try:
        while True:
            current_time = time.time()

            # Read sensors periodically
            if current_time - last_sensor_read >= Config.SENSOR_READ_INTERVAL:
                try:
                    sensor_data = sensors.read_all()
                    logger(f"Sensor data: {sensor_data}", "DEBUG")
                    last_sensor_read = current_time

                    # Log data if enabled
                    if data_logger and Config.ENABLE_DATA_LOGGING:
                        data_logger.log_data(sensor_data)
                except Exception as e:
                    handle_error("Sensor reading failed", e)

            # Publish to MQTT periodically
            if mqtt and mqtt.is_connected() and current_time - last_mqtt_publish >= Config.MQTT_PUBLISH_INTERVAL:
                try:
                    for sensor_name, value in sensor_data.items():
                        topic = f"{Config.MQTT_TOPIC_PREFIX}/{sensor_name}"
                        mqtt.publish(topic, str(value))

                    # Publish system status
                    status_topic = f"{Config.MQTT_TOPIC_PREFIX}/status"
                    status_data = {
                        "uptime": current_time - Config.START_TIME,
                        "free_memory": gc.mem_free(),
                        "wifi_rssi": wifi.get_rssi() if wifi else 0
                    }
                    mqtt.publish(status_topic, str(status_data))
                    last_mqtt_publish = current_time
                except Exception as e:
                    handle_error("MQTT publish failed", e)

            # Connection checks
            if current_time - last_status_check >= Config.STATUS_CHECK_INTERVAL:
                try:
                    if wifi and not wifi.is_connected():
                        logger("WiFi disconnected, attempting reconnection...", "WARNING")
                        wifi.reconnect()
                    if mqtt and not mqtt.is_connected():
                        logger("MQTT disconnected, attempting reconnection...", "WARNING")
                        mqtt.reconnect()
                    last_status_check = current_time
                except Exception as e:
                    handle_error("Status check failed", e)

            # Handle web and MQTT
            if web_server:
                try:
                    web_server.handle_requests()
                except Exception as e:
                    handle_error("Web server error", e)
            if mqtt and mqtt.is_connected():
                try:
                    mqtt.check_messages()
                except Exception as e:
                    handle_error("MQTT message handling failed", e)

            # Garbage collection
            if current_time - last_gc_collect >= Config.GC_INTERVAL:
                gc.collect()
                last_gc_collect = current_time

            time.sleep_ms(Config.MAIN_LOOP_DELAY)

    except KeyboardInterrupt:
        logger("Program interrupted by user")
    except Exception as e:
        handle_error("Main loop error", e)
    finally:
        cleanup()


def cleanup():
    """Clean up resources."""
    logger("Cleaning up...")
    try:
        if web_server:
            web_server.stop()
        if mqtt:
            mqtt.disconnect()
        if wifi:
            wifi.disconnect()
        if data_logger:
            data_logger.close()
        status_led.off()
        logger("Cleanup completed")
    except Exception as e:
        handle_error("Cleanup failed", e)


def main():
    """Entry point."""
    try:
        setup()
        main_loop()
    except Exception as e:
        handle_error("Fatal error", e)
        machine.reset()


if __name__ == "__main__":
    main()
'''


    def _generate_data_logger(self) -> bool:
        """Generate IoT data_logger.py file."""

    def _generate_utils(self) -> bool:
        """Generate IoT utils.py file."""

    def _generate_tests(self) -> bool:
        """Generate IoT test_iot.py file."""

    def _generate_api_docs(self) -> bool:
        """Generate IoT API.md file."""

    def _generate_web_interface(self) -> bool:
        """Generate IoT index.html file."""

    def _generate_web_styles(self) -> bool:
        """Generate IoT styles.css file."""

    def _generate_web_scripts(self) -> bool:
        """Generate IoT scripts.js file."""

    def _generate_default_config(self) -> bool:
        """Generate IoT default config.json file."""