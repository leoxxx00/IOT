"""Lecture 4: Connect the Python AIoT device to MQTT."""

import json
import time
import paho.mqtt.client as mqtt

from config import DEVICE_CONFIG, MQTT_CONFIG
from sensors import VirtualSensors
from state import evaluate_state
from telemetry import build_telemetry

class AIoTDeviceMQTT:
    def __init__(self):
        self.sensors = VirtualSensors()
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=DEVICE_CONFIG["device_id"],
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"MQTT connection failed: {reason_code}")
        else:
            print(
                f"Connected to MQTT broker at "
                f"{MQTT_CONFIG['broker_host']}:{MQTT_CONFIG['broker_port']}"
            )

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"Disconnected from MQTT broker: {reason_code}")

    def connect(self):
        self.client.connect(
            MQTT_CONFIG["broker_host"],
            MQTT_CONFIG["broker_port"],
            MQTT_CONFIG["keepalive"],
        )
        self.client.loop_start()

    def publish_telemetry(self, telemetry):
        payload = json.dumps(telemetry)
        info = self.client.publish(
            MQTT_CONFIG["telemetry_topic"],
            payload=payload,
            qos=MQTT_CONFIG["qos"],
            retain=MQTT_CONFIG["retain"],
        )

        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Published -> {MQTT_CONFIG['telemetry_topic']}")
        else:
            print(f"Publish failed: {info.rc}")

    def run(self, cycles=10):
        self.connect()
        try:
            time.sleep(1)
            for cycle in range(1, cycles + 1):
                readings = self.sensors.read_all()
                state, message = evaluate_state(readings)
                telemetry = build_telemetry(
                    DEVICE_CONFIG, readings, state, message
                )

                print(f"\nCycle {cycle}")
                print(json.dumps(telemetry, indent=2))
                self.publish_telemetry(telemetry)

                if cycle < cycles:
                    time.sleep(DEVICE_CONFIG["sampling_interval"])
        except KeyboardInterrupt:
            print("\nDevice stopped by user.")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    AIoTDeviceMQTT().run(cycles=10)
