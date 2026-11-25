# Connecting the Python AIoT Device to MQTT — Lecture 4

## Architecture

Python AIoT Device → MQTT Broker → MQTT Subscriber

## Files

- `device_mqtt.py` — AIoT device that publishes telemetry
- `subscriber.py` — live MQTT subscriber
- `config.py` — device and MQTT configuration
- `sensors.py` — stateful virtual sensors
- `state.py` — machine-state logic
- `telemetry.py` — telemetry builder
- `requirements.txt` — Python dependency
- `docker-compose.yml` — optional local Mosquitto broker
- `mosquitto.conf` — local demo broker configuration
- `AIoT_Device_MQTT_Lecture_4.ipynb` — guided notebook

## Setup

1. Start the local broker:

```bash
docker compose up -d
```

2. Install the Python dependency:

```bash
pip install -r requirements.txt
```

3. Terminal 1 — subscriber:

```bash
python subscriber.py
```

4. Terminal 2 — device:

```bash
python device_mqtt.py
```

The subscriber should display telemetry in real time.

## MQTT topic

```text
factory/production-line-2/machine/MCH-007/telemetry
```

## Important

The included Mosquitto configuration allows anonymous access only for this local learning demo.
Do not use it in production. Production MQTT should use authentication, authorization,
TLS and appropriate network controls.

## Paho MQTT

This project uses the Eclipse Paho MQTT Python client and its version-2 callback API.
