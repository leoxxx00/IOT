"""Subscribe to both sensors and display readings in the terminal."""

import json
from datetime import datetime
from math import isfinite

import paho.mqtt.client as mqtt

from config import PATIENT_TOPIC, ROOM_TOPIC, make_client, utc_timestamp

DEVICES = {
    PATIENT_TOPIC: (
        "Patient monitor",
        {
            "heart_rate_bpm": ("Heart rate", "BPM"),
            "systolic_mmhg": ("Systolic", "mmHg"),
            "diastolic_mmhg": ("Diastolic", "mmHg"),
        },
    ),
    ROOM_TOPIC: ("Room sensor", {"temperature_c": ("Temperature", "°C")}),
}


def format_message(topic, payload):
    label, fields = DEVICES[topic]
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")

    device_id = data["device_id"]
    timestamp = data["timestamp"]
    readings = data["readings"]
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("device_id must be a non-empty string")
    if not isinstance(timestamp, str) or not isinstance(readings, dict):
        raise ValueError("invalid timestamp or readings type")
    if datetime.fromisoformat(timestamp.replace("Z", "+00:00")).utcoffset() is None:
        raise ValueError("timestamp must include a time zone")

    values = []
    for key, (name, unit) in fields.items():
        value = readings[key]
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError(f"{key} must be a finite number")
        values.append(f"{name} {value} {unit}")

    return (
        f"Received {utc_timestamp()} | {label} [{device_id!r}] | "
        f"Sampled {timestamp} | {' | '.join(values)}"
    )


def on_message(client, userdata, message):
    try:
        line = format_message(message.topic, message.payload)
    except (ValueError, KeyError, OverflowError, RecursionError) as error:
        print(f"Ignored malformed message on {message.topic}: {error}", flush=True)
        return
    print(line, flush=True)


def subscribe(client):
    # MQTT clean sessions require subscriptions to be made again after reconnect.
    result, _ = client.subscribe([(topic, 0) for topic in DEVICES])
    if result != mqtt.MQTT_ERR_SUCCESS:
        print(f"Could not request subscriptions ({mqtt.error_string(result)}).", flush=True)


def on_subscribe(client, userdata, mid, reason_codes, properties):
    for topic, reason in zip(DEVICES, reason_codes):
        status = "Subscription rejected" if reason.is_failure else "Subscribed"
        print(f"{status}: {topic}", flush=True)


def main():
    client, _ = make_client("terminal", subscribe)
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    print("Waiting for MQTT connection.", flush=True)
    try:
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        print("\nStopping subscriber.", flush=True)
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
