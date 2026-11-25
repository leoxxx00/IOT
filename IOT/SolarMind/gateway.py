import logging
import socket
import sqlite3
import threading
import time
from statistics import mean
from urllib.request import Request, urlopen
import paho.mqtt.publish as mqtt
from common import config, data, decode, fields, frame, json, packet, struct, utc


def poll():
    with socket.create_connection((config["inverter_ip"], config["inverter_port"]), timeout=3) as sock:
        sock.sendall(packet(1, 17, struct.pack(">BHH", 4, 0, 60)))
        tid, unit, body = frame(sock)
        if (tid, unit, body[:2]) != (1, 17, bytes([4, 120])) or len(body) != 122:
            raise ValueError("Unexpected Modbus reply")
        return decode(struct.unpack(">60H", body[2:]))


def deliver(channel):
    with sqlite3.connect(data/"queue.db", timeout=15) as db:
        while True:
            row = db.execute(f"SELECT id,payload FROM queue WHERE {channel}=0 ORDER BY id LIMIT 1").fetchone()
            if row is None:
                time.sleep(1)
                continue
            key, payload = row
            try:
                if channel == "mqtt":
                    topic = "solarmind/" + json.loads(payload)["site_id"] + "/reading"
                    mqtt.single(topic, payload, qos=1, hostname=config["mqtt_host"], port=config["mqtt_port"])
                else:
                    req = Request(config["http_url"], payload.encode(), {"Content-Type": "application/json"})
                    with urlopen(req, timeout=5) as response:
                        if not 200 <= response.status < 300:
                            raise ValueError(response.status)
                with db:
                    db.execute(f"UPDATE queue SET {channel}=1 WHERE id=?", (key,))
                    db.execute("DELETE FROM queue WHERE id=? AND mqtt=1 AND http=1", (key,))
            except Exception:
                logging.exception("%s delivery failed for %s", channel, key)
                time.sleep(5)


def main():
    logging.basicConfig(level=logging.INFO)
    with sqlite3.connect(data/"queue.db", timeout=15) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS queue(id INTEGER PRIMARY KEY, payload TEXT, mqtt INTEGER DEFAULT 0, http INTEGER DEFAULT 0)")
        for channel in ("mqtt", "http"):
            threading.Thread(target=deliver, args=(channel,), daemon=True).start()
        samples = []
        tick = time.monotonic()
        deadline = tick + 60
        while True:
            try:
                samples.append(poll())
            except (OSError, EOFError, ValueError):
                logging.exception("Modbus poll failed")
            tick += 10
            time.sleep(max(0, tick-time.monotonic()))
            if tick >= deadline:
                if samples:
                    reading = {k: round(mean(s[k] for s in samples), 2) for k in fields}
                    reading.update(site_id=config["site_id"], timestamp=utc())
                    payload = json.dumps(reading)
                    with db:
                        db.execute("INSERT INTO queue(payload) VALUES (?)", (payload,))
                    logging.info("%s samples: %s", len(samples), payload)
                samples.clear()
                deadline += 60


if __name__ == "__main__":
    main()
