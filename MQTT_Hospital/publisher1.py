"""Publish synthetic heart rate and blood pressure every 60 seconds."""

from random import randint

from config import PATIENT_ID, PATIENT_TOPIC, run_publisher

INTERVAL_SECONDS = 60


def sample():
    """Return an illustrative set of adult resting readings."""
    return {
        "heart_rate_bpm": randint(60, 95),
        "systolic_mmhg": randint(105, 130),
        "diastolic_mmhg": randint(65, 85),
    }


if __name__ == "__main__":
    run_publisher("patient", PATIENT_TOPIC, PATIENT_ID, INTERVAL_SECONDS, sample)
