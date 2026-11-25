DEVICE_CONFIG = {
    "device_id": "MCH-007",
    "device_type": "Bottle Filling Machine",
    "location": "Production Line 2",
    "sampling_interval": 2,
}
MQTT_CONFIG={
    "broker_host":"localhost",
    "broker_port":1883,
    "keepalive":60,
    "telemetry_topic":"factory/production-line-2/machine/MCH-007/telemetry",
    "command_topic": "factory/production-line-2/machine/MCH-007/command",
    "command_topic_template": "factory/production-line-2/machine/{device_id}/command",
    "ack_topic": "factory/production-line-2/machine/{device_id}/ack_topic",
    "qos":0,
}
MONGODB_CONFIG={"uri":"mongodb://localhost:27017","database":"aiot_platform","collection":"telemetry"}
API_CONFIG = {"title": "Enterprise AIoT Device API", "version": "1.0.0"}
