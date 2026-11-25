import json, uuid
import paho.mqtt.client as mqtt
from config import MQTT_CONFIG

class MQTTCommandPublisher:
    def __init__(self):
        self.connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="aiot-rest-api")
        self.client.on_connect = self._on_connect
        self.client.connect(MQTT_CONFIG["broker_host"], MQTT_CONFIG["broker_port"], MQTT_CONFIG["keepalive"])
        self.client.loop_start()
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = not reason_code.is_failure
        print("MQTT command publisher connected." if self.connected else f"MQTT connection failed: {reason_code}")
    def send_command(self, device_id, command, reason=None, correlation_id=None):
        if not self.connected:
            raise RuntimeError("MQTT broker is not connected.")
        correlation_id = correlation_id or f"CMD-{uuid.uuid4().hex[:10].upper()}"
        payload = {"command": command.upper(), "correlation_id": correlation_id}
        if reason: payload["reason"] = reason
        topic = MQTT_CONFIG["command_topic_template"].format(device_id=device_id)
        info = self.client.publish(topic, json.dumps(payload), qos=MQTT_CONFIG["qos"], retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS: raise RuntimeError(f"MQTT publish failed: {info.rc}")
        return {"topic": topic, "correlation_id": correlation_id, "command": command.upper()}
    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
