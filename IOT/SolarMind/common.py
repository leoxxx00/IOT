import json
import os
from pathlib import Path
import struct
from datetime import datetime, timezone

config = json.loads(Path(os.getenv("SOLARMIND_CONFIG", "config.json")).read_text())
data = Path(config["state_dir"])
data.mkdir(parents=True, exist_ok=True)
fields = ("pv_power_w", "load_power_w", "grid_power_w", "battery_power_w", "battery_soc_pct")
header = struct.Struct(">HHHB")


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def receive(sock, size):
    buf = bytearray()
    while len(buf) < size:
        part = sock.recv(size - len(buf))
        if not part:
            raise EOFError("Incomplete Modbus frame")
        buf.extend(part)
    return bytes(buf)


def frame(sock):
    tid, protocol, length, unit = header.unpack(receive(sock, 7))
    if protocol or not 2 <= length <= 254:
        raise ValueError("Invalid Modbus header")
    return tid, unit, receive(sock, length - 1)


def packet(tid, unit, body):
    return header.pack(tid, 0, len(body) + 1, unit) + body


def signed(value):
    return value - 65536 if value >= 32768 else value


def decode(reg):
    return dict(zip(fields, (reg[18]+reg[20], reg[42], -signed(reg[30]),
                             -signed(reg[52]), reg[59])))
