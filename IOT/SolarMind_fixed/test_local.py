"""Run the full simulator against a private local Mosquitto and FastAPI stub."""
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parent


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(check, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {check.__name__}")


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    for name in ("mosquitto", "mosquitto_sub"):
        if not shutil.which(name):
            raise SystemExit(f"Install {name} and add it to PATH before running this test.")

    with tempfile.TemporaryDirectory() as tmp, ExitStack() as cleanup:
        directory = Path(tmp)
        config = json.loads((PROJECT / "config.json").read_text())
        ports = set()
        while len(ports) < 4:
            ports.add(free_port())
        inverter, broker, http, viewer = sorted(ports)
        config.update(inverter_port=inverter, mqtt_port=broker, state_dir=tmp,
                      inverter_ip="127.0.0.1", mqtt_host="127.0.0.1",
                      http_url=f"http://127.0.0.1:{http}/readings", use_live_weather=False)
        config_path = directory / "config.json"
        config_path.write_text(json.dumps(config))
        env = dict(os.environ, SOLARMIND_CONFIG=str(config_path))

        def start(*args, stdout=None):
            process = subprocess.Popen(args, cwd=PROJECT, env=env, stdout=stdout, text=True)
            cleanup.callback(stop, process)
            return process

        start("mosquitto", "-p", str(broker))
        start(sys.executable, "simulator.py")
        wait_for(lambda: listening(broker) and listening(inverter))
        topic = f"solarmind/{config['site_id']}/reading"
        subscriber = start("mosquitto_sub", "-h", "127.0.0.1", "-p", str(broker),
                           "-q", "1", "-t", topic, "-C", "1", stdout=subprocess.PIPE)
        start(sys.executable, "gateway.py")
        print("Waiting for the first one-minute reading with HTTP offline.", flush=True)
        payload, _ = subscriber.communicate(timeout=80)
        if subscriber.returncode:
            raise RuntimeError("MQTT subscriber failed")
        reading = json.loads(payload)
        assert reading["site_id"] == config["site_id"]
        assert reading["timestamp"].endswith("Z")
        assert 0 <= reading["battery_soc_pct"] <= 100
        assert min(reading["pv_power_w"], reading["load_power_w"]) >= 0
        assert abs(reading["pv_power_w"] + reading["grid_power_w"]
                   - reading["load_power_w"] - reading["battery_power_w"]) < 0.1

        def queue():
            with sqlite3.connect(directory / "queue.db") as db:
                return db.execute("SELECT mqtt,http FROM queue").fetchall()

        wait_for(lambda: queue() == [(1, 0)])
        start(sys.executable, "-m", "uvicorn", "backend:app", "--host", "127.0.0.1",
              "--port", str(http))
        wait_for(lambda: queue() == [], 20)
        with sqlite3.connect(directory / "backend.db") as db:
            stored = db.execute("SELECT payload FROM readings").fetchone()
        assert stored and json.loads(stored[0]) == reading
        start(sys.executable, "-m", "uvicorn", "viewer:app", "--host", "127.0.0.1",
              "--port", str(viewer))
        wait_for(lambda: listening(viewer))
        base = f"http://127.0.0.1:{viewer}"
        with urlopen(base + "/", timeout=3) as response:
            assert b"Site monitor" in response.read()
        with urlopen(base + f"/sites/{config['site_id']}/latest", timeout=3) as response:
            assert json.load(response) == reading
        print("PASS: Dashboard and viewer API returned the saved site reading.")
        print("PASS: MQTT and recovered HTTP payloads match. Queue is empty.")
        print(json.dumps(reading, indent=2))


if __name__ == "__main__":
    main()
