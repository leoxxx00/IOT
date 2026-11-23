"""Shared MQTT settings and publisher loop."""

import json
import os
from datetime import datetime, timezone
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "hospital-demo/a1-67f62ed60666")
PATIENT_TOPIC = f"{TOPIC_PREFIX}/patient"
ROOM_TOPIC = f"{TOPIC_PREFIX}/room-temperature"

PATIENT_ID = f"{TOPIC_PREFIX}/patient-01"
ROOM_ID = f"{TOPIC_PREFIX}/room-01"


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def make_client(role, on_connected):
    """Create an MQTT 3.1.1 client and reconnect after network failures."""
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"{role}-{uuid4().hex[:12]}",
        protocol=mqtt.MQTTv311,
    )
    connected = Event()
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Broker refused connection ({reason_code}). Retrying.", flush=True)
            return
        print(f"Connected to {BROKER_HOST}:{BROKER_PORT}", flush=True)
        on_connected(client)
        connected.set()

    def on_disconnect(client, userdata, flags, reason_code, properties):
        connected.clear()
        if reason_code.is_failure:
            print(f"Disconnected ({reason_code}). Retrying.", flush=True)

    def on_connect_fail(client, userdata):
        print(f"Cannot reach {BROKER_HOST}:{BROKER_PORT}. Retrying.", flush=True)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_connect_fail = on_connect_fail
    client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=30)
    return client, connected


def run_publisher(role, topic, device_id, interval, sample):
    """Send a fresh sample immediately, then at the configured interval."""
    client, connected = make_client(role, lambda client: None)
    print(f"Publishing to {topic} every {interval} seconds once connected.", flush=True)
    client.loop_start()
    try:
        while True:
            connected.wait()
            deadline = monotonic() + interval
            payload = json.dumps({
                "device_id": device_id,
                "timestamp": utc_timestamp(),
                "readings": sample(),
            })
            # QoS 0 sends live telemetry without replaying missed samples.
            result = client.publish(topic, payload, qos=0, retain=False)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                try:
                    result.wait_for_publish(timeout=5)
                    if result.is_published():
                        print(f"Sent {topic} | {payload}", flush=True)
                    else:
                        print("Send confirmation timed out.", flush=True)
                except (RuntimeError, ValueError) as error:
                    print(f"Send interrupted ({error}).", flush=True)
            else:
                print(f"Sample skipped ({mqtt.error_string(result.rc)}).", flush=True)
            sleep(max(0, deadline - monotonic()))
    except KeyboardInterrupt:
        print("\nStopping publisher.", flush=True)
    finally:
        client.disconnect()
        client.loop_stop()
