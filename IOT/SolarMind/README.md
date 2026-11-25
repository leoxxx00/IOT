# SolarMind weather-driven gateway

A Raspberry Pi with Python 3.10+ and network access, or a Mac, can run the entire demo. No physical inverter, panel or customer equipment is needed. Use the local test backend only. See REGISTERS.md for the five values.

## Mac quick start
Extract the project into IOT1 and open the directory containing config.json. Use the following commands in that directory. Reuse the local Mosquitto broker on port 1883, or start it in a separate tab with mosquitto -p 1883.

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

Run each in a separate terminal, from the same directory:

    .venv/bin/python backend.py
    .venv/bin/python simulator.py
    .venv/bin/python gateway.py
    mosquitto_sub -h 127.0.0.1 -t 'solarmind/test-01/reading' -v

Open http://127.0.0.1:8010/docs or run curl http://127.0.0.1:8010/weather. Refresh to see new weather. In config.json set site_id, inverter_ip, inverter_port, mqtt_host, mqtt_port, http_url, state_dir, latitude, longitude and timezone. The example location is Hounslow. For separate hosts the simulator bind address must belong to its own machine and the gateway config must point to that machine.

## Weather and energy
The simulator requests current modelled air temperature and shortwave radiation every 15 minutes. Irradiance drives a 5 kWp PV approximation with a 0.85 performance factor. Load has daily morning and evening peaks. A 10 kWh simulated battery charges or discharges within 10–95% SOC. Grid balances PV + grid = load + battery. When weather is missing or at least an hour old the simulator uses a synthetic local-time daylight curve. Restarting the simulator resets its battery to 55%. Weather is shown separately to preserve the seven-field SolarMind JSON contract.

Weather data: Open-Meteo, https://open-meteo.com/en/docs . Free endpoint for non-commercial evaluation; review https://open-meteo.com/en/pricing before commercial deployment.

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
