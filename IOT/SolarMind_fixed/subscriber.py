"""Display minute averages from the configured SolarMind broker."""
import json
import logging

import paho.mqtt.client as mqtt

from common import config


def connected(client, topic, flags, reason_code, properties):
    if reason_code.is_failure:
        logging.error("MQTT connection refused: %s", reason_code)
        return
    client.subscribe(topic, qos=1)
    print(f"Subscribing to {topic}", flush=True)


def received(client, topic, message):
    try:
        reading = json.loads(message.payload)
    except (UnicodeDecodeError, ValueError):
        logging.warning("Invalid JSON on %s", message.topic)
        return
    print(message.topic, json.dumps(reading), flush=True)


if __name__ == "__main__":
    topic = f"solarmind/{config['site_id']}/reading"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=topic)
    client.on_connect = connected
    client.on_message = received
    client.connect_async(config["mqtt_host"], config["mqtt_port"])
    try:
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        client.disconnect()
