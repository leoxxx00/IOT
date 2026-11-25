"""Telemetry builder for the AIoT device."""

from datetime import datetime

def build_telemetry(device_config, readings, state, message):
    return {
        "device_id": device_config["device_id"],
        "device_type": device_config["device_type"],
        "location": device_config["location"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "state": state.value,
        "message": message,
        "readings": readings,
    }
