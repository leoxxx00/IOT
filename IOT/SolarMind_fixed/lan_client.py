"""Print the latest SolarMind reading from a viewer on the local network."""
import argparse
import csv
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


COLUMNS = ("site_id", "timestamp", "pv_power_w", "load_power_w", "grid_power_w",
           "battery_power_w", "battery_soc_pct")


def write_latest(path, reading):
    values = [reading[key] for key in COLUMNS]
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8",
                                         dir=path.parent, delete=False) as stream:
            tmp = Path(stream.name)
            writer = csv.writer(stream)
            writer.writerow(COLUMNS)
            writer.writerow(values)
        tmp.replace(path)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="Viewer address, e.g. http://192.168.1.107:8011")
    parser.add_argument("--site", default="test-01")
    parser.add_argument("--watch-csv", type=Path, metavar="FILE",
                        help="Replace FILE with the latest reading every 60 seconds")
    args = parser.parse_args()
    url = f"{args.base_url.rstrip('/')}/sites/{quote(args.site, safe='')}/latest"
    while True:
        try:
            with urlopen(url, timeout=5) as response:
                reading = json.load(response)
            if args.watch_csv is None:
                print(json.dumps(reading, indent=2))
                return
            write_latest(args.watch_csv, reading)
            print(f"{reading['timestamp']} saved to {args.watch_csv}", flush=True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if args.watch_csv is None:
                parser.exit(1, f"Could not read {url}: {exc}\n")
            print(f"CSV update failed: {exc}. Retrying in 60 seconds.", flush=True)
        time.sleep(60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
