from arduino_model import ArduinoMonitor
import logging
import math
import socketserver
import threading
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo
from common import config, data, frame, json, packet, struct, utc

registers = [0] * 60
weather = None


def update_weather():
    global weather
    query = urlencode(dict(latitude=config["latitude"], longitude=config["longitude"],
                           current="temperature_2m,shortwave_radiation", timezone="GMT",
                           timeformat="unixtime"))
    while True:
        try:
            with urlopen("https://api.open-meteo.com/v1/forecast?" + query, timeout=10) as response:
                current = json.load(response)["current"]
            radiation = float(current["shortwave_radiation"])
            temp = float(current["temperature_2m"])
            stamp = int(current["time"])
            if not all(map(math.isfinite, (radiation, temp))) or radiation < 0:
                raise ValueError("Invalid weather values")
            weather = (stamp, radiation)
            tmp = data / "weather.tmp"
            tmp.write_text(json.dumps(dict(provider="Open-Meteo", observed_epoch=stamp,
                                           fetched_utc=utc(), temperature_c=temp,
                                           irradiance_w_m2=radiation)))
            tmp.replace(data / "weather.json")
        except Exception:
            logging.exception("Weather refresh failed")
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
        sunlight = max(0, math.sin(math.pi * (hour - 7) / 10))
        sample = weather
        irradiance = sample[1] if sample and 0 <= time.time()-sample[0] < 3600 else 750*sunlight
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
                else:
                    start, count = struct.unpack(">HH", body[1:])
                    if not count or start+count > 60:
                        reply = bytes([132, 2])
                    else:
                        reply = bytes([4, count*2]) + struct.pack(f">{count}H", *registers[start:start+count])
                self.request.sendall(packet(tid, unit, reply))
        except (OSError, EOFError, ValueError):
            return


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=update_weather, daemon=True).start()
    threading.Thread(target=model, daemon=True).start()
    with socketserver.ThreadingTCPServer((config["inverter_ip"], config["inverter_port"]), Reader) as server:
        server.serve_forever()
