from typing import Dict
from . import BaseTemplate

class IoTTemplate(BaseTemplate):
    """IoT project template with Wi-Fi, .MQTT, sensors, and web server."""

    description = "Complete IoT solution with WiFi connectivity, MQTT communication, sensor readings, and web interface"
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
        "Real-time dashboard"
    ]
    dependencies = [
        "umqtt.simple",
        "upip",
        "ujson"
    ]

    def generate_files(self) ->  Dict[str, str]:
        """Generate all IoT project files."""
        files = self.get_common_files()

        # Add IoT-specific files
        files.update({
            'src/main.py': self._generate_main(),
            'src/config.py': self._generate_config(),
            'src/wifi_manager.py': self._generate_wifi_manager(),
            'src/mqtt_client.py': self._generate_mqtt_client(),
            'src/sensor_manager.py': self._generate_sensor_manager(),
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
        return """1. Configure WiFi credentials in config.py
2. Set up MQTT broker details
3. Configure sensors in sensor_manager.py
4. Access web interface at http://<esp32-ip>
5. Monitor MQTT topics sensor data
6. Use REST API for remote control
        """

    def _generate_main(self) -> str:
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

             # Check connections periodically
             if current_time - last_status_check >= Config.STATUS_CHECK_INTERVAL:
                 try:
                     # Check WiFi connection
                     if wifi and not wifi.is_connected():
                         logger("WiFi disconnected, attempting reconnection...", "WARNING")
                         if wifi.connect():
                             logger("WiFi reconnected")
                         else:
                             logger("WiFi reconnection failed", "ERROR")

                     # Check MQTT connection
                     if mqtt and not mqtt.is_connected():
                         logger("MQTT disconnected, attempting reconnection...", "WARNING")
                         if mqtt.connect():
                             logger("MQTT reconnected")
                         else:
                             logger("MQTT reconnection failed", "ERROR")

                     last_status_check = current_time

                 except Exception as e:
                     handle_error("Status check failed", e)

             # Handle web server requests
             if web_server:
                 try:
                     web_server.handle_requests()
                 except Exception as e:
                     handle_error("Web server error", e)

             # Handle MQTT messages
             if mqtt and mqtt.is_connected():
                 try:
                     mqtt.check_messages()
                 except Exception as e:
                     handle_error("MQTT message handling failed", e)

             # Garbage collection
             if current_time - last_gc_collect >= Config.GC_INTERVAL:
                 gc.collect()
                 last_gc_collect = current_time

             # Small delay to prevent excessive CPU usage
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
     """Application entry point."""
     try:
         setup()
         main_loop()
     except Exception as e:
         handle_error("Fatal error", e)
         machine.reset()

 if __name__ == "__main__":
     main()
 '''

    def _generate_config(self) -> str:
        """Generate IoT config.py file."""
        return '''"""
ESP32 IoT Project - Configuration
================================
Central configuration file for all project settings
"""

import time
import machine

class Config:
    """Configuration constants and settings."""

    # Project information
    PROJECT_NAME = "ESP32 IoT Project"
    VERSION = "1.0.0"
    START_TIME = time.time()

    # Hardware pins
    STATUS_LED_PIN = 2
    ONBOARD_LED_PIN = 2

    # Sensor pins (customize based on your setup)
    DHT22_PIN = 4
    DS18B20_PIN = 5
    LDR_PIN = 34  # ADC pin
    PIR_PIN = 18
    BUZZER_PIN = 19

    # I2C pins for sensors
    I2C_SDA_PIN = 21
    I2C_SCL_PIN = 22

    # SPI pins for SD card
    SD_MISO_PIN = 19
    SD_MOSI_PIN = 23
    SD_SCK_PIN = 18
    SD_CS_PIN = 5

    # WiFi settings
    WIFI_SSID = "YOUR_WIFI_SSID"
    WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
    WIFI_TIMEOUT = 15  # seconds
    WIFI_MAX_RETRIES = 3

    # MQTT settings
    ENABLE_MQTT = True
    MQTT_BROKER = "broker.hivemq.com"  # Public broker for testing
    MQTT_PORT = 1883
    MQTT_USER = ""
    MQTT_PASSWORD = ""
    MQTT_CLIENT_ID = f"esp32_{machine.unique_id().hex()}"
    MQTT_TOPIC_PREFIX = f"iot/{MQTT_CLIENT_ID}"
    MQTT_KEEPALIVE = 60
    MQTT_TIMEOUT = 10

    # Web server settings
    ENABLE_WEB_SERVER = True
    WEB_SERVER_PORT = 80
    WEB_SERVER_TIMEOUT = 5

    # Data logging settings
    ENABLE_DATA_LOGGING = True
    LOG_FILE_PATH = "/sd/sensor_data.csv"
    LOG_MAX_SIZE = 1024 * 1024  # 1MB
    LOG_ROTATION = True

    # Timing intervals (seconds)
    SENSOR_READ_INTERVAL = 5
    MQTT_PUBLISH_INTERVAL = 10
    STATUS_CHECK_INTERVAL = 30
    GC_INTERVAL = 60

    # Main loop settings
    MAIN_LOOP_DELAY = 100  # milliseconds

    # Sensor settings
    DHT22_ENABLED = True
    DS18B20_ENABLED = True
    LDR_ENABLED = True
    PIR_ENABLED = True
    BME280_ENABLED = False  # Set to True if BME280 is connected

    # Thresholds and limits
    TEMPERATURE_MIN = -40
    TEMPERATURE_MAX = 80
    HUMIDITY_MIN = 0
    HUMIDITY_MAX = 100
    LIGHT_THRESHOLD = 500

    # OTA settings
    ENABLE_OTA = False
    OTA_URL = "http://your-server.com/firmware.bin"

    # Debug settings
    DEBUG_MODE = True
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

    # Network settings
    AP_MODE_FALLBACK = True
    AP_SSID = f"ESP32-{machine.unique_id().hex()[-6:]}"
    AP_PASSWORD = "12345678"

    @classmethod
    def validate(cls):
        """Validate configuration settings."""
        errors = []

        if not cls.WIFI_SSID or cls.WIFI_SSID == "YOUR_WIFI_SSID":
            errors.append("WiFi SSID not configured")

        if not cls.WIFI_PASSWORD or cls.WIFI_PASSWORD == "YOUR_WIFI_PASSWORD":
            errors.append("WiFi password not configured")

        if cls.ENABLE_MQTT and not cls.MQTT_BROKER:
            errors.append("MQTT broker not configured")

        if cls.SENSOR_READ_INTERVAL <= 0:
            errors.append("Sensor read interval must be positive")

        return errors

    @classmethod
    def get_sensor_config(cls):
        """Get sensor configuration dictionary."""
        return {
            'dht22': {
                'enabled': cls.DHT22_ENABLED,
                'pin': cls.DHT22_PIN
            },
            'ds18b20': {
                'enabled': cls.DS18B20_ENABLED,
                'pin': cls.DS18B20_PIN
            },
            'ldr': {
                'enabled': cls.LDR_ENABLED,
                'pin': cls.LDR_PIN
            },
            'pir': {
                'enabled': cls.PIR_ENABLED,
                'pin': cls.PIR_PIN
            },
            'bme280': {
                'enabled': cls.BME280_ENABLED,
                'sda': cls.I2C_SDA_PIN,
                'scl': cls.I2C_SCL_PIN
            }
        }
'''

    def _generate_wifi_manager(self) -> str:
        """Generate IoT wifi_manager.py file."""
        return '''"""
ESP32 IoT Project - WiFi Manager
===============================
Handles WiFi connection, reconnection, and access point fallback
"""

import network
import time
import machine
from config import Config
from utils import logger

class WiFiManager:
    """Manages WiFi connections and access point mode."""

    def __init__(self):
        self.sta = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)
        self.connected = False
        self.ip_address = None
        self.ap_mode = False

    def connect(self, ssid=None, password=None, timeout=None):
        """Connect to WiFi network."""
        ssid = ssid or Config.WIFI_SSID
        password = password or Config.WIFI_PASSWORD
        timeout = timeout or Config.WIFI_TIMEOUT

        if not ssid or ssid == "YOUR_WIFI_SSID":
            logger("WiFi SSID not configured", "ERROR")
            return self._start_ap_mode()

        logger(f"Connecting to WiFi: {ssid}")

        # Activate station mode
        self.sta.active(True)

        # Check if already connected to the right network
        if self.sta.isconnected():
            if self.sta.config('essid') == ssid:
                self.connected = True
                self.ip_address = self.sta.ifconfig()[0]
                logger(f"Already connected to {ssid} ({self.ip_address})")
                return True
            else:
                self.sta.disconnect()
                time.sleep(1)

        # Connect to network
        self.sta.connect(ssid, password)

        # Wait for connection
        start_time = time.time()
        while not self.sta.isconnected():
            if time.time() - start_time > timeout:
                logger(f"WiFi connection timeout after {timeout}s", "ERROR")
                return self._start_ap_mode() if Config.AP_MODE_FALLBACK else False

            time.sleep(0.5)

        # Connection successful
        self.connected = True
        self.ip_address = self.sta.ifconfig()[0]
        logger(f"WiFi connected successfully!")
        logger(f"IP address: {self.ip_address}")
        logger(f"Subnet mask: {self.sta.ifconfig()[1]}")
        logger(f"Gateway: {self.sta.ifconfig()[2]}")
        logger(f"DNS: {self.sta.ifconfig()[3]}")

        return True

    def _start_ap_mode(self):
        """Start access point mode as fallback."""
        if not Config.AP_MODE_FALLBACK:
            return False

        logger("Starting Access Point mode...")

        # Deactivate station mode
        self.sta.active(False)

        # Configure and activate AP
        self.ap.config(essid=Config.AP_SSID, password=Config.AP_PASSWORD)
        self.ap.active(True)

        # Wait for AP to be ready
        while not self.ap.active():
            time.sleep(0.1)

        self.connected = True
        self.ap_mode = True
        self.ip_address = self.ap.ifconfig()[0]

        logger(f"Access Point started: {Config.AP_SSID}")
        logger(f"AP IP address: {self.ip_address}")
        logger("Connect to this AP and navigate to http://192.168.4.1")

        return True

    def disconnect(self):
        """Disconnect from WiFi."""
        logger("Disconnecting from WiFi...")

        if self.ap_mode:
            self.ap.active(False)
            self.ap_mode = False
        else:
            self.sta.disconnect()

        self.connected = False
        self.ip_address = None

    def is_connected(self):
        """Check if WiFi is connected."""
        if self.ap_mode:
            return self.ap.active()
        else:
            return self.sta.isconnected()

    def get_ip(self):
        """Get current IP address."""
        if self.ap_mode:
            return self.ap.ifconfig()[0]
        elif self.sta.isconnected():
            return self.sta.ifconfig()[0]
        else:
            return None

    def get_rssi(self):
        """Get WiFi signal strength."""
        if self.ap_mode:
            return 0
        elif self.sta.isconnected():
            return self.sta.status('rssi')
        else:
            return -100

    def scan_networks(self):
        """Scan for available WiFi networks."""
        logger("Scanning for WiFi networks...")

        if not self.sta.active():
            self.sta.active(True)
            time.sleep(1)

        networks = self.sta.scan()
        network_list = []

        for net in networks:
            network_info = {
                'ssid': net[0].decode('utf-8'),
                'bssid': ':'.join(f'{b:02x}' for b in net[1]),
                'channel': net[2],
                'rssi': net[3],
                'authmode': net[4],
                'hidden': net[5]
            }
            network_list.append(network_info)

        # Sort by signal strength
        network_list.sort(key=lambda x: x['rssi'], reverse=True)

        logger(f"Found {len(network_list)} networks")
        return network_list

    def get_connection_info(self):
        """Get detailed connection information."""
        if not self.is_connected():
            return None

        if self.ap_mode:
            config = self.ap.ifconfig()
            return {
                'mode': 'AP',
                'ssid': Config.AP_SSID,
                'ip': config[0],
                'subnet': config[1],
                'gateway': config[2],
                'dns': config[3],
                'rssi': 0
            }
        else:
            config = self.sta.ifconfig()
            return {
                'mode': 'STA',
                'ssid': self.sta.config('essid'),
                'ip': config[0],
                'subnet': config[1],
                'gateway': config[2],
                'dns': config[3],
                'rssi': self.get_rssi()
            }

    def reconnect(self):
        """Attempt to reconnect to WiFi."""
        if self.ap_mode:
            return True  # AP mode doesn't need reconnection

        if self.is_connected():
            return True

        logger("Attempting WiFi reconnection...")
        self.disconnect()
        time.sleep(2)
        return self.connect()
'''

    def _generate_mqtt_client(self) -> str:
        """Generate IoT mqtt_client.py file."""
        return '''"""
ESP32 IoT Project - MQTT Client
==============================
Handles MQTT communication with automatic reconnection
"""

import time
import ujson
from umqtt.simple import MQTTClient as SimpleMQTTClient
from config import Config
from utils import logger, handle_error

class MQTTClient:
    """MQTT client with auto-reconnection and message handling."""

    def __init__(self, device_ip=None):
        self.client = None
        self.connected = False
        self.device_ip = device_ip
        self.last_ping = time.time()
        self.message_callbacks = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

    def connect(self):
        """Connect to MQTT broker."""
        try:
            logger(f"Connecting to MQTT broker: {Config.MQTT_BROKER}")
            
            self.client = SimpleMQTTClient(
                client_id=Config.MQTT_CLIENT_ID,
                server=Config.MQTT_BROKER,
                port=Config.MQTT_PORT,
                user=Config.MQTT_USER,
                password=Config.MQTT_PASSWORD,
                keepalive=Config.MQTT_KEEPALIVE
            )

            # Set callback for incoming messages
            self.client.set_callback(self._message_callback)
            
            # Connect to broker
            self.client.connect()
            self.connected = True
            self.reconnect_attempts = 0

            logger("MQTT connected successfully")

            # Subscribe to control topics
            self._subscribe_to_control_topics()

            # Publish online status
            self._publish_status("online")

            return True

        except Exception as e:
            handle_error("MQTT connection failed", e)
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.connected and self.client:
            try:
                # Publish offline status
                self._publish_status("offline")

                self.client.disconnect()
                logger("MQTT disconnected")
            except Exception as e:
                handle_error("MQTT disconnect error", e)

        self.connected = False
        self.client = None

    def is_connected(self):
        """Check if MQTT is connected."""
        return self.connected

    def publish(self, topic, message, retain=False):
        """Publish message to MQTT topic."""
        if not self.connected or not self.client:
            return False

        try:
            # Convert message to string if needed
            if isinstance(message, dict):
                message = ujson.dumps(message)
            elif not isinstance(message, str):
                message = str(message)

            self.client.publish(topic, message, retain)
            logger(f"Published to {topic}: {message[:50]}...", "DEBUG")
            return True

        except Exception as e:
            handle_error(f"MQTT publish failed for topic {topic}", e)
            self.connected = False
            return False

    def subscribe(self, topic, callback=None):
        """Subscribe to MQTT topic."""
        if not self.connected or not self.client:
            return False

        try:
            self.client.subscribe(topic)

            if callback:
                self.message_callbacks[topic] = callback

            logger(f"Subscribed to topic: {topic}")
            return True

        except Exception as e:
            handle_error(f"MQTT subscribe failed for topic {topic}", e)
            return False

    def unsubscribe(self, topic):
        """Unsubscribe from MQTT topic."""
        if not self.connected or not self.client:
            return False

        try:
            self.client.unsubscribe(topic)

            if topic in self.message_callbacks:
                del self.message_callbacks[topic]

            logger(f"Unsubscribed from topic: {topic}")
            return True

        except Exception as e:
            handle_error(f"MQTT unsubscribe failed for topic {topic}", e)
            return False

    def check_messages(self):
        """Check for incoming MQTT messages."""
        if not self.connected or not self.client:
            return

        try:
            self.client.check_msg()

            # Send ping if needed
            current_time = time.time()
            if current_time - self.last_ping > Config.MQTT_KEEPALIVE / 2:
                self.client.ping()
                self.last_ping = current_time

        except Exception as e:
            handle_error("MQTT message check failed", e)
            self.connected = False

    def _message_callback(self, topic, msg):
        """Handle incoming MQTT messages."""
        try:
            topic_str = topic.decode('utf-8')
            msg_str = msg.decode('utf-8')

            logger(f"MQTT message received - Topic: {topic_str}, Message: {msg_str}", "DEBUG")

            # Check for specific topic callbacks
            if topic_str in self.message_callbacks:
                self.message_callbacks[topic_str](topic_str, msg_str)
            else:
                # Handle control messages
                self._handle_control_message(topic_str, msg_str)
                
        except Exception as e:
            handle_error("MQTT message callback error", e)

    def _handle_control_message(self, topic, message):
        """Handle control messages."""
        try:
            base_topic = f"{Config.MQTT_TOPIC_PREFIX}/control"

            if topic == f"{base_topic}/restart":
                logger("Restart command received via MQTT")
                import machine
                machine.reset()

            elif topic == f"{base_topic}/status":
                self._publish_device_status()

            elif topic == f"{base_topic}/led":
                self._handle_led_control(message)

            elif topic.startswith(f"{base_topic}/config"):
                self._handle_config_update(topic, message)

        except Exception as e:
            handle_error("Control message handling failed", e)

    def _handle_led_control(self, message):
        """Handle LED control commands."""
        try:
            import machine
                led = machine.Pin(Config.STATUS_LED_PIN, machine.Pin.OUT)

            if message.lower() in ['on', '1', 'true']:
                led.on()
                logger("LED turned ON via MQTT")
            elif message.lower() in ['off', '0', 'false']:
                led.off()
                logger("LED turned OFF via MQTT")

        except Exception as e:
            handle_error("LED control failed", e)

    def _handle_config_update(self, topic, message):
        """Handle configuration updates."""
        try:
            config_param = topic.split('/')[-1]
            logger(f"Config update: {config_param} = {message}")

            # Here you could update configuration dynamically
            # This is a placeholder for more advanced config management

        except Exception as e:
            handle_error("Config update failed", e)

    def _subscribe_to_control_topics(self):
        """Subscribe to control topics."""
        control_topics = [
            f"{Config.MQTT_TOPIC_PREFIX}/control/restart",
            f"{Config.MQTT_TOPIC_PREFIX}/control/status",
            f"{Config.MQTT_TOPIC_PREFIX}/control/led",
            f"{Config.MQTT_TOPIC_PREFIX}/control/config/+"
        ]

        for topic in control_topics:
            self.subscribe(topic)

    def _publish_status(self, status):
        """Publish device status."""
        status_topic = f"{Config.MQTT_TOPIC_PREFIX}/status"
        self.publish(status_topic, status, retain=True)

    def _publish_device_status(self):
        """Publish detailed device status."""
        try:
            import gc
            import machine

            status_data = {
                "device_id": Config.MQTT_CLIENT_ID,
                "uptime": time.time() - Config.START_TIME,
                "free_memory": gc.mem_free(),
                "cpu_freq": machine.freq(),
                "ip_address": self.device_ip,
                "timestamp": time.time()
            }

            status_topic = f"{Config.MQTT_TOPIC_PREFIX}/device_status"
            self.publish(status_topic, ujson.dumps(status_data))

        except Exception as e:
            handle_error("Device status publish failed", e)

    def reconnect(self):
        """Attempt to reconnect to MQTT broker."""
        if self.connected:
            return True

        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger(f"Max MQTT reconnect attempts ({self.max_reconnect_attempts}) reached", "ERROR")
            return False

        self.reconnect_attempts += 1
        logger(f"MQTT reconnect attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")

        # Wait before reconnecting
        time.sleep(min(self.reconnect_attempts * 2, 30))

        return self.connect()
'''

    def _generate_sensor_manager(self) -> str:
        """Generate IoT sensor_manager.py file."""
        return '''"""
ESP32 IoT Project - Sensor Manager
=================================
Manages all sensors and data collection
"""

import time
import machine
from machine import Pin, ADC, I2C
from config import Config
from utils import logger, handle_error

try:
    import dht
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    logger("DHT library not available", "WARNING")

try:
    import onewire
    import ds18x20
    DS18B20_AVAILABLE = True
except ImportError:
    DS18B20_AVAILABLE = False
    logger("DS18B20 library not available", "WARNING")

class SensorManager:
    """Manages all sensors and data collection."""

    def __init__(self):
        self.sensors = {}
        self.last_readings = {}
        self.sensor_errors = {}

        # Initialize sensors based on configuration
        self._init_sensors()

    def _init_sensors(self):
        """Initialize all enabled sensors."""
        sensor_config = Config.get_sensor_config()

        # Initialize DHT22 sensor
        if sensor_config['dht22']['enabled'] and DHT_AVAILABLE:
            try:
                pin = Pin(sensor_config['dht22']['pin'])
                self.sensors['dht22'] = dht.DHT22(pin)
                logger(f"DHT22 sensor initialized on pin {sensor_config['dht22']['pin']}")
            except Exception as e:
                handle_error("DHT22 initialization failed", e)

        # Initialize DS18B20 temperature sensor
        if sensor_config['ds18b20']['enabled'] and DS18B20_AVAILABLE:
            try:
                pin = Pin(sensor_config['ds18b20']['pin'])
                ow = onewire.OneWire(pin)
                self.sensors['ds18b20'] = ds18x20.DS18X20(ow)
                logger(f"DS18B20 sensor initialized on pin {sensor_config['ds18b20']['pin']}")
            except Exception as e:
                handle_error("DS18B20 initialization failed", e)

        # Initialize LDR (Light Dependent Resistor)
        if sensor_config['ldr']['enabled']:
            try:
                self.sensors['ldr'] = ADC(Pin(sensor_config['ldr']['pin']))
                self.sensors['ldr'].atten(ADC.ATTN_11DB)  # Full range: 3.3V
                logger(f"LDR sensor initialized on pin {sensor_config['ldr']['pin']}")
            except Exception as e:
                handle_error("LDR initialization failed", e)

        # Initialize PIR motion sensor
        if sensor_config['pir']['enabled']:
            try:
                self.sensors['pir'] = Pin(sensor_config['pir']['pin'], Pin.IN)
                logger(f"PIR sensor initialized on pin {sensor_config['pir']['pin']}")
            except Exception as e:
                handle_error("PIR initialization failed", e)

        # Initialize BME280 if enabled
        if sensor_config['bme280']['enabled']:
            try:
                i2c = I2C(scl=Pin(sensor_config['bme280']['scl']), 
                            sda=Pin(sensor_config['bme280']['sda']))
                # Note: BME280 library would need to be imported separately
                # This is a placeholder for BME280 initialization
                logger("BME280 sensor would be initialized here (library needed)")
            except Exception as e:
                handle_error("BME280 initialization failed", e)

    def read_all(self):
        """Read data from all available sensors."""
        readings = {}
        current_time = time.time()

        # Read DHT22 (temperature and humidity)
        if 'dht22' in self.sensors:
            try:
                self.sensors['dht22'].measure()
                temperature = self.sensors['dht22'].temperature()
                humidity = self.sensors['dht22'].humidity()

                # Validate readings
                if (Config.TEMPERATURE_MIN <= temperature <= Config.TEMPERATURE_MAX and
                    Config.HUMIDITY_MIN <= humidity <= Config.HUMIDITY_MAX):
                    readings['temperature'] = round(temperature, 2)
                    readings['humidity'] = round(humidity, 2)
                    self.sensor_errors['dht22'] = 0
                else:
                    logger(f"DHT22 readings out of range: T={temperature}, H={humidity}", "WARNING")

            except Exception as e:
                self._handle_sensor_error('dht22', e)

        # Read DS18B20 temperature
        if 'ds18b20' in self.sensors:
            try:
                ds = self.sensors['ds18b20']
                roms = ds.scan()
                if roms:
                    ds.convert_temp()
                    time.sleep_ms(750)  # Wait for conversion
                    for rom in roms:
                        temp = ds.read_temp(rom)
                        if Config.TEMPERATURE_MIN <= temp <= Config.TEMPERATURE_MAX:
                            readings['ds18b20_temp'] = round(temp, 2)
                            self.sensor_errors['ds18b20'] = 0
                            break

            except Exception as e:
                self._handle_sensor_error('ds18b20', e)

        # Read LDR (light level)
        if 'ldr' in self.sensors:
            try:
                raw_value = self.sensors['ldr'].read()
                # Convert to percentage (0-100%)
                light_level = round((raw_value / 4095) * 100, 1)
                readings['light_level'] = light_level
                readings['light_raw'] = raw_value
                self.sensor_errors['ldr'] = 0

            except Exception as e:
                self._handle_sensor_error('ldr', e)

        # Read PIR motion sensor
        if 'pir' in self.sensors:
            try:
                motion = self.sensors['pir'].value()
                readings['motion'] = bool(motion)
                self.sensor_errors['pir'] = 0

            except Exception as e:
                self._handle_sensor_error('pir', e)

        # Add timestamp and system info
        readings['timestamp'] = current_time
        readings['uptime'] = current_time - Config.START_TIME

        # Store last readings
        self.last_readings = readings.copy()

        return readings

    def read_sensor(self, sensor_name):
        """Read data from a specific sensor."""
        if sensor_name not in self.sensors:
            return None

        try:
            if sensor_name == 'dht22':
                self.sensors['dht22'].measure()
                return {
                    'temperature': self.sensors['dht22'].temperature(),
                    'humidity': self.sensors['dht22'].humidity()
                }

            elif sensor_name == 'ds18b20':
                ds = self.sensors['ds18b20']
                roms = ds.scan()
                if roms:
                    ds.convert_temp()
                    time.sleep_ms(750)
                    return {'temperature': ds.read_temp(roms[0])}

            elif sensor_name == 'ldr':
                raw_value = self.sensors['ldr'].read()
                return {
                    'light_level': round((raw_value / 4095) * 100, 1),
                    'raw_value': raw_value
                }

            elif sensor_name == 'pir':
                return {'motion': bool(self.sensors['pir'].value())}

        except Exception as e:
            self._handle_sensor_error(sensor_name, e)
            return None

    def get_sensor_status(self):
        """Get status of all sensors."""
        status = {}

        for sensor_name in self.sensors:
            error_count = self.sensor_errors.get(sensor_name, 0)
            status[sensor_name] = {
                'available': True,
                'error_count': error_count,
                'status': 'OK' if error_count < 5 else 'ERROR'
            }

        return status

    def get_last_readings(self):
        """Get the last sensor readings."""
        return self.last_readings.copy()

    def calibrate_sensors(self):
        """Calibrate sensors if needed."""
        logger("Sensor calibration started...")

        # Placeholder for sensor calibration routines
        # This could include:
        # - Temperature offset calibration
        # - Light sensor calibration
        # - Motion sensor sensitivity adjustment

        logger("Sensor calibration completed")

    def _handle_sensor_error(self, sensor_name, error):
        """Handle sensor reading errors."""
        if sensor_name not in self.sensor_errors:
            self.sensor_errors[sensor_name] = 0

        self.sensor_errors[sensor_name] += 1

        if self.sensor_errors[sensor_name] <= 3:
            logger(f"Sensor {sensor_name} error #{self.sensor_errors[sensor_name]}: {error}", "WARNING")
        elif self.sensor_errors[sensor_name] == 4:
            logger(f"Sensor {sensor_name} has too many errors, suppressing further warnings", "ERROR")

    def reset_error_counts(self):
        """Reset error counts for all sensors."""
        self.sensor_errors.clear()
        logger("Sensor error counts reset")

    def get_available_sensors(self):
        """Get list of available sensors."""
        return list(self.sensors.keys())

    def is_sensor_available(self, sensor_name):
        """Check if a specific sensor is available."""
        return sensor_name in self.sensors
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