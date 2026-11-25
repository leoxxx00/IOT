"""Simple MQTT subscriber for the Lecture 4 live demonstration."""

import paho.mqtt.client as mqtt
from config import MQTT_CONFIG

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"Connection failed: {reason_code}")
        return
    topic = MQTT_CONFIG["telemetry_topic"]
    client.subscribe(topic, qos=MQTT_CONFIG["qos"])
    print(f"Connected. Subscribed to: {topic}")
    print("Waiting for device telemetry...\n")

def on_message(client, userdata, message):
    print(f"Topic: {message.topic}")
    print(f"Payload: {message.payload.decode('utf-8')}")
    print("-" * 80)

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="MCH-007-demo-subscriber",
)
client.on_connect = on_connect
client.on_message = on_message

client.connect(
    MQTT_CONFIG["broker_host"],
    MQTT_CONFIG["broker_port"],
    MQTT_CONFIG["keepalive"],
)

print("MQTT subscriber started.")
client.loop_forever()
