# SolarMind weather-driven gateway

A Raspberry Pi with Python 3.10+ and network access, or a Mac, can run the entire demo. No physical inverter, panel or customer equipment is needed. Use the local test backend only. See REGISTERS.md for the five values.

## Mac quick start
Open a terminal in the extracted SolarMind_fixed folder. Use the following commands in that directory. Reuse the local Mosquitto broker on port 1883, or start it in a separate tab with mosquitto -p 1883.

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

Run each in a separate terminal, from the same directory:

    .venv/bin/python backend.py
    .venv/bin/python simulator.py
    .venv/bin/python gateway.py
    mosquitto_sub -h 127.0.0.1 -t 'solarmind/test-01/reading' -v

Open http://127.0.0.1:8010/docs or run curl http://127.0.0.1:8010/weather. Refresh to see new weather. In config.json set site_id, inverter_ip, inverter_port, mqtt_host, mqtt_port, http_url, state_dir, latitude, longitude and timezone. The example location is Hounslow. For separate hosts the simulator bind address must belong to its own machine and the gateway config must point to that machine.

## Weather and energy
The simulator polls the public NOAA Aviation Weather Center METAR endpoint every
15 minutes for the configured ICAO station (EGLL, London Heathrow, by default).
No API key is needed. The dashboard shows the reported air temperature and
observation time. Cloud categories are converted to approximate fractions and
attenuate the simulated daylight curve. Irradiance and PV remain estimates.
Without reported cloud cover or a report less than an hour old, the model uses
the daily profile. Set use_live_weather to false for offline-only operation.
Change weather_station to choose another airport. Coordinates alone do not select
a station. Restart the simulator, backend and viewer after changing the config.

Weather source: https://aviationweather.gov/data/api/

## Sampling and recovery
Expect the first reading after one minute. Every ten seconds the gateway reads a snapshot. Each minute it averages valid samples and logs the count; a window with no successful samples produces no reading. SQLite commits each average before independent HTTP and MQTT workers send it. The HTTP stub deduplicates by site and timestamp. MQTT uses QoS 1, so consumers should deduplicate by the same pair. Stop the HTTP stub for two minutes with Ctrl+C: MQTT should continue. Restart the stub and inspect saved readings:

    sqlite3 data/backend.db 'SELECT site,stamp,payload FROM readings ORDER BY stamp DESC LIMIT 5;'
    sqlite3 data/queue.db 'SELECT id,mqtt,http FROM queue;'

## Raspberry Pi boot setup
Copy this folder to /opt/solarmind. Install Mosquitto and a Python virtual environment there, then install requirements as above. Run these commands on the Pi. In the installed config set state_dir to /var/lib/solarmind for all three services.

    sudo useradd --system --no-create-home solarmind
    sudo install -D -m 644 /opt/solarmind/config.json /etc/solarmind/config.json
    sudo nano /etc/solarmind/config.json
    sudo cp /opt/solarmind/solarmind@.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now mosquitto solarmind@backend solarmind@simulator solarmind@gateway
    journalctl -fu solarmind@gateway

Skip useradd if the service account already exists. Use SOLARMIND_CONFIG to select a different JSON config. On macOS stop each foreground process with Ctrl+C.

## Dashboard and bench circuit
Visit http://127.0.0.1:8010/ on the host running the backend. The dashboard shows the five inverter values, minute history, weather input, queue counts, configuration and the simulated Arduino circuit. The simulator imports arduino_model.py automatically. Optional config key arduino_mode accepts 0 for automatic backup (default), 1 for daylight demonstration, or 2 for continuous blinking. Restart the simulator after changing it.

## Demo acceptance checks
1. Match the site, timestamp and five values of one MQTT message to its dashboard history row. Check PV + grid approximately equals load + battery.
2. Pause the HTTP stub for two minutes. Check that pending HTTP rows accumulate while MQTT continues. Restart HTTP and confirm those same timestamps appear in the backend and the queue drains.
3. In an isolated demo, repeat with the broker stopped and the HTTP backend running. Restart the broker and confirm queued MQTT deliveries clear.
4. On the Pi after a planned reboot, run `systemctl is-active mosquitto solarmind@simulator solarmind@gateway solarmind@backend`. Confirm a new reading arrives within two minutes.
5. For a physical GivEnergy trial, agree on the exact model, LAN adapter and transport with CCE first. The simulator implements the register meanings over standard Modbus TCP.

## Isolated local integration test

Run the following in the project folder after installing the requirements.
Install Mosquitto and its command-line clients first (macOS: brew install
mosquitto; Raspberry Pi OS: sudo apt install mosquitto mosquitto-clients).
Ensure mosquitto and mosquitto_sub are on your PATH.

    .venv/bin/python test_local.py

The test starts its own loopback broker and simulator on temporary ports,
subscribes before starting the gateway, and intentionally keeps HTTP offline
for the first minute. It checks the MQTT payload and pending SQLite row,
starts FastAPI, and checks that the recovered HTTP reading matches and the queue
drains. Allow about 70–90 seconds. A connection-refused log for HTTP is
expected during the outage. Child services and temporary data are cleaned up.

## MQTT subscriber and LAN dashboard

Run these commands in separate terminals from the same project folder, alongside
the simulator, broker, gateway, and backend. Each process uses the same config.

    .venv/bin/python subscriber.py
    .venv/bin/python viewer.py

The gateway is the MQTT publisher. Mosquitto forwards its minute average on
solarmind/test-01/reading to subscriber.py and any subscribed Home Assistant
client. Independently, the gateway POSTs that minute average to FastAPI on the
gateway machine at http://127.0.0.1:8010/readings. The LAN viewer reads the
same SQLite database as the backend. It can show HTTP-delivered history even
when the subscriber was closed.

Open http://127.0.0.1:8011/ on the gateway host. On another device connected to
the same private LAN, open http://HOST_IP:8011/ using the gateway machine's
LAN IPv4 address. On the Pi run hostname -I; on a Mac using Wi-Fi on en0 run
ipconfig getifaddr en0. Allow incoming TCP 8011 on the host's private network
if prompted. Leave broker and ingestion settings at their loopback defaults.
The optional viewer serves simulated data without login to reachable devices.

| Method | LAN viewer path | Result |
| --- | --- | --- |
| GET | / | Dashboard |
| GET | /sites/test-01/latest | Latest averaged reading; 404 before first delivery |
| GET | /sites/test-01/readings?limit=10 | Newest first; empty list before first delivery |
| GET | /docs | Interactive API documentation |

Replace test-01 with the configured site ID. To run the viewer on Pi boot with
the existing service template, install viewer.py with the other scripts and run
sudo systemctl enable --now solarmind@viewer.

The dashboard offers JSON and CSV downloads of all saved minute averages for the configured site, oldest first. Each download includes readings saved up to that query. Use GET /sites/test-01/export.json or /sites/test-01/export.csv. Restart the backend and any running viewer after upgrading.

### Read the API from a second computer

Start viewer.py on the gateway host and keep it running. Copy lan_client.py
to a computer on the same LAN. From the folder containing the client, run
`python3 lan_client.py http://HOST_IP:8011`, replacing HOST_IP with the
gateway's current LAN address. Python's standard library is sufficient.
The optional --site argument selects a site (default test-01). Each invocation
prints one latest saved JSON reading, including its UTC timestamp.

Open /?api-test on the viewer to send read-only API requests and inspect HTTP
status and response data from the same host. Select an endpoint, enter the site
ID for site readings or exports, and click Send request.

For a continuously refreshed one-row CSV, run the client on the computer where
you want the file. Use a dedicated filename, since each successful refresh
replaces it. Example on the gateway Mac:

    python3 lan_client.py http://127.0.0.1:8010 --watch-csv latest-reading.csv

Use the viewer's LAN URL on another computer. Leave the client running; Ctrl+C
stops it. It fetches immediately and then every 60 seconds. Failed requests
preserve the previous CSV. Download CSV history in the API tester exports all
saved readings separately.
