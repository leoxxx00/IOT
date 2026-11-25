# AIoT REST API — Lecture 7

## Architecture
Application → REST API → MongoDB / MQTT → AIoT Device

Telemetry:
AIoT Device → MQTT → Ingestion Service → MongoDB → REST API → Application

Commands:
Application → REST API → MQTT → AIoT Device

## Setup
Install:
`pip install -r requirements.txt`

Start the MQTT broker and MongoDB from Lecture 6, then run:
`python mqtt_to_mongodb.py`
`python device_two_way.py`

Start the API:
`uvicorn api:app --reload`

Open:
`http://127.0.0.1:8000/docs`

Recommended demo:
1. GET /health
2. GET /devices/MCH-007/telemetry/latest
3. GET /devices/MCH-007/telemetry?limit=10
4. GET /devices/MCH-007/events/warnings
5. GET /devices/MCH-007/status
6. POST /devices/MCH-007/commands with {"command":"STOP","reason":"Maintenance test"}
7. Send START and watch the device state change.

Production systems should add authentication, authorization, TLS, rate limiting, secrets management, audit logging and stronger health/readiness controls.
