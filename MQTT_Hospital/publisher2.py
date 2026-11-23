"""Publish synthetic hospital room temperature every 30 seconds."""

from random import uniform

from config import ROOM_ID, ROOM_TOPIC, run_publisher

INTERVAL_SECONDS = 30


def sample():
    return {"temperature_c": round(uniform(20.0, 24.0), 1)}


if __name__ == "__main__":
    run_publisher("room", ROOM_TOPIC, ROOM_ID, INTERVAL_SECONDS, sample)
