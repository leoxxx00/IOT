"""Stateful virtual sensors used by the AIoT device."""

import random
from dataclasses import dataclass

@dataclass
class SensorModel:
    name: str
    value: float
    min_value: float
    max_value: float
    drift: float
    noise: float

    def read(self):
        self.value += random.uniform(-self.drift, self.drift)
        self.value = max(self.min_value, min(self.max_value, self.value))
        observed = self.value + random.uniform(-self.noise, self.noise)
        return round(observed, 2)

class VirtualSensors:
    def __init__(self):
        self.temperature = SensorModel("temperature", 72.0, 65.0, 95.0, 0.35, 0.20)
        self.vibration = SensorModel("vibration", 2.0, 1.0, 5.0, 0.08, 0.05)
        self.pressure = SensorModel("pressure", 6.2, 4.0, 7.5, 0.08, 0.04)
        self.energy = SensorModel("energy", 1.4, 0.8, 2.5, 0.04, 0.03)

    def read_all(self):
        return {
            "temperature": self.temperature.read(),
            "vibration": self.vibration.read(),
            "pressure": self.pressure.read(),
            "energy": self.energy.read(),
        }
