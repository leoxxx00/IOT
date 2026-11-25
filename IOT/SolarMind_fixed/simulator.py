from arduino_model import ArduinoMonitor
import logging
import math
import socketserver
import threading
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from common import config, data, frame, json, packet, struct, utc

registers = None
weather = None


# Representative sky fractions for the METAR cloud amount categories.
SKY_FRACTION = {"CLR": 0, "SKC": 0, "NSC": 0, "NCD": 0,
                "FEW": 0.19, "SCT": 0.44, "BKN": 0.75, "OVC": 1, "VV": 1}


def read_station(reports, station):
    report = max((r for r in reports if r.get("icaoId") == station),
                 key=lambda r: int(r["obsTime"]))
    stamp = int(report["obsTime"])
    temperature = float(report["temp"])
    if not math.isfinite(temperature) or not 0 <= time.time() - stamp < 3600:
        raise ValueError("Missing or stale station observation")
    covers = [layer.get("cover") for layer in report.get("clouds") or []]
    covers.append(report.get("cover"))
    known = [SKY_FRACTION[c] for c in covers if c in SKY_FRACTION]
    return dict(provider="NOAA Aviation Weather Center", station=station,
                observed_epoch=stamp, fetched_utc=utc(), temperature_c=temperature,
                cloud_fraction=max(known) if known else None)


def update_weather():
    global weather
    station = config.get("weather_station", "EGLL").upper()
    query = urlencode(dict(ids=station, format="json"))
    request = Request("https://aviationweather.gov/api/data/metar?" + query,
                      headers={"User-Agent": "SolarMind-Edge-Prototype/1.0"})
    while True:
        try:
            with urlopen(request, timeout=10) as response:
                observation = read_station(json.load(response), station)
            tmp = data / "weather.tmp"
            tmp.write_text(json.dumps(observation))
            tmp.replace(data / "weather.json")
            weather = observation
        except Exception:
            logging.exception("Weather refresh failed for %s", station)
        time.sleep(900)


def model():
    global registers
    monitor = ArduinoMonitor(config.get("arduino_mode", 0))
    last_report = 0
    soc = 55.0
    previous = time.monotonic()
    while True:
        now = datetime.now(ZoneInfo(config["timezone"]))
        hour = now.hour + now.minute / 60 + now.second / 3600
        sunlight = math.sin(math.pi * (hour - 7) / 10) if 7 < hour < 17 else 0.0
        sample = weather
        irradiance = 750 * sunlight
        if sample and 0 <= time.time() - sample["observed_epoch"] < 3600:
            clouds = sample["cloud_fraction"]
            if clouds is not None:
                irradiance *= 1 - 0.75 * clouds
        pv = min(5000, round(5 * irradiance * 0.85))
        load = round(350 + 1200*math.exp(-((hour-18)/2)**2)
                     + 650*math.exp(-((hour-8)/1.3)**2) + 50*math.sin(hour*8))
        tick = time.monotonic()
        hours = max(tick-previous, 0.001)/3600
        circuit = monitor.sample(irradiance, tick)
        if tick - last_report >= 1:
            circuit["Sample UTC"] = utc()
            tmp = data / "arduino.tmp"
            tmp.write_text(json.dumps(circuit))
            tmp.replace(data / "arduino.json")
            last_report = tick
        previous = tick
        battery = round(min(2000, (95-soc)*100/hours,
                            max(-2000, (10-soc)*100/hours, pv-load)))
        soc = max(10, min(95, soc + battery*hours/100))
        grid = load+battery-pv
        raw = [0]*60
        raw[18], raw[20] = pv//2, pv-pv//2
        raw[30], raw[42], raw[52], raw[59] = -grid & 65535, load, -battery & 65535, round(soc)
        registers = raw
        time.sleep(0.05)


class Reader(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            while True:
                tid, unit, body = frame(self.request)
                if unit != 17 or body[0] != 4:
                    reply = bytes([body[0] | 128, 1])
                elif len(body) != 5:
                    reply = bytes([132, 3])
                elif registers is None:
                    reply = bytes([132, 6])  # First model snapshot is pending.
                else:
                    start, count = struct.unpack(">HH", body[1:])
                    if not count or start+count > 60:
                        reply = bytes([132, 2])
                    else:
                        reply = bytes([4, count*2]) + struct.pack(f">{count}H", *registers[start:start+count])
                self.request.sendall(packet(tid, unit, reply))
        except (OSError, EOFError, ValueError):
            return


class ModbusServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if config.get("use_live_weather", False):
        threading.Thread(target=update_weather, daemon=True).start()
    threading.Thread(target=model, daemon=True).start()
    with ModbusServer((config["inverter_ip"], config["inverter_port"]), Reader) as server:
        server.serve_forever()
