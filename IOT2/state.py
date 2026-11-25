"""Simple machine-state evaluation for the MQTT demo."""

from enum import Enum

class MachineState(str, Enum):
    RUNNING = "RUNNING"
    WARNING = "WARNING"
    FAULT = "FAULT"

THRESHOLDS = {
    "temperature_warning": 80.0,
    "temperature_fault": 88.0,
    "vibration_warning": 3.2,
    "vibration_fault": 4.0,
    "pressure_fault_low": 4.0,
}

def evaluate_state(readings):
    t = readings["temperature"]
    v = readings["vibration"]
    p = readings["pressure"]

    if t >= THRESHOLDS["temperature_fault"] and v >= THRESHOLDS["vibration_fault"]:
        return MachineState.FAULT, "Critical temperature and vibration"
    if t >= THRESHOLDS["temperature_fault"]:
        return MachineState.FAULT, "Critical temperature"
    if p <= THRESHOLDS["pressure_fault_low"]:
        return MachineState.FAULT, "Critical low pressure"
    if t >= THRESHOLDS["temperature_warning"] or v >= THRESHOLDS["vibration_warning"]:
        return MachineState.WARNING, "Operating parameter approaching limit"

    return MachineState.RUNNING, "Normal operation"
