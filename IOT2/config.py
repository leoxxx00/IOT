"""Configuration for the Lecture 4 AIoT MQTT device demo."""

DEVICE_CONFIG = {
    "device_id": "MCH-007",
    "device_type": "Bottle Filling Machine",
    "location": "Production Line 2",
    "sampling_interval": 2,
}

MQTT_CONFIG = {
    "broker_host": "localhost",
    "broker_port": 1883,
    "keepalive": 60,
    "telemetry_topic": "factory/production-line-2/machine/MCH-007/telemetry",
    "qos": 0,
    "retain": False,
}
