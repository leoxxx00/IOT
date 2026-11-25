import sqlite3
import time
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pathlib import Path
from fastapi.responses import FileResponse
from common import config, data, json

app = FastAPI(title="SolarMind local test backend")


class Reading(BaseModel):
    site_id: str
    timestamp: datetime
    pv_power_w: float = Field(ge=0)
    load_power_w: float = Field(ge=0)
    grid_power_w: float
    battery_power_w: float
    battery_soc_pct: float = Field(ge=0, le=100)


@app.post("/readings")
def save(reading: Reading):
    with sqlite3.connect(data/"backend.db") as db:
        db.execute("CREATE TABLE IF NOT EXISTS readings(site TEXT, stamp TEXT, payload TEXT, PRIMARY KEY(site,stamp))")
        db.execute("INSERT OR IGNORE INTO readings VALUES(?,?,?)",
                   (reading.site_id, reading.timestamp.isoformat(), reading.model_dump_json()))
    return {"accepted": True}


@app.get("/weather")
def weather():
    try:
        observation = json.loads((data/"weather.json").read_text())
    except FileNotFoundError:
        return {"source": "daily profile", "weather_available": False}
    fresh = 0 <= time.time()-observation["observed_epoch"] < 3600
    return {**observation, "weather_available": fresh, "source": "Open-Meteo" if fresh else "daily profile"}


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).with_name("dashboard.html"))


@app.get("/dashboard/data")
def dashboard_data():
    readings = []
    pending = None
    path = data / "backend.db"
    if path.exists():
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='readings'").fetchone():
                rows = db.execute("SELECT payload FROM readings WHERE site=? ORDER BY stamp DESC LIMIT 60",
                                  (config["site_id"],))
                readings = [json.loads(row[0]) for row in rows]
    path = data / "queue.db"
    if path.exists():
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='queue'").fetchone():
                total, mqtt, http = db.execute(
                    "SELECT count(*),count(CASE WHEN mqtt=0 THEN 1 END),count(CASE WHEN http=0 THEN 1 END) FROM queue"
                ).fetchone()
                pending = {"Queued readings": total, "Awaiting MQTT": mqtt, "Awaiting HTTP": http}
    return {"readings": readings, "weather": weather(), "queue": pending, "config": config}


@app.get("/arduino")
def arduino():
    try:
        return json.loads((data / "arduino.json").read_text())
    except FileNotFoundError:
        return {"Status": "Waiting for simulator"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010)
