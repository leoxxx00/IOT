import csv
import io
import math
import sqlite3
from contextlib import closing
from typing import Literal
import time
from datetime import datetime, timezone
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, Field
from pathlib import Path
from fastapi.responses import FileResponse, StreamingResponse
from common import config, data, fields, json, utc
from gateway import poll

app = FastAPI(title="SolarMind local test backend")
views = APIRouter()


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


@views.get("/sites/{site_id}/readings", response_model=list[Reading])
def history(site_id: str, limit: int = Query(default=100, ge=1, le=1000)):
    path = data / "backend.db"
    if not path.exists():
        return []
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='readings'").fetchone():
            return []
        rows = db.execute("SELECT payload FROM readings WHERE site=? ORDER BY stamp DESC LIMIT ?",
                          (site_id, limit))
        return [json.loads(row[0]) for row in rows]


@views.get("/sites/{site_id}/live", response_model=Reading)
def live_sample(site_id: str):
    if site_id != config["site_id"]:
        raise HTTPException(status_code=404, detail="No local inverter configured for this site")
    try:
        values = poll()
    except (OSError, EOFError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Inverter sample unavailable") from exc
    return Reading(site_id=site_id, timestamp=utc(), **values)


@views.get("/sites/{site_id}/latest", response_model=Reading)
def latest(site_id: str):
    rows = history(site_id, 1)
    if not rows:
        raise HTTPException(status_code=404, detail="No readings for this site yet")
    return rows[0]


def export_chunks(site_id, file_format, since=None):
    buffer = io.StringIO(newline="")
    csv_writer = csv.DictWriter(buffer, fieldnames=("site_id", "timestamp", *fields))
    if file_format == "csv":
        csv_writer.writeheader()
    else:
        buffer.write("[")
    path = data / "backend.db"
    if path.exists():
        # StreamingResponse may advance the generator on different worker threads.
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True,
                                     check_same_thread=False)) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='readings'").fetchone():
                query = "SELECT payload FROM readings WHERE site=?"
                params = [site_id]
                if since is not None:
                    # Gateway timestamps and the public cursor represent UTC instants.
                    # Narrow by whole second, then compare exactly for fractional seconds.
                    query += " AND CAST(strftime('%s', stamp) AS INTEGER) >= ?"
                    params.append(math.floor(since.timestamp()))
                rows = db.execute(query + " ORDER BY stamp", params)
                first = True
                for (payload,) in rows:
                    if since is not None:
                        stamp = datetime.fromisoformat(json.loads(payload)["timestamp"].replace("Z", "+00:00"))
                        if stamp.tzinfo is None:
                            stamp = stamp.replace(tzinfo=timezone.utc)
                        if stamp <= since:
                            continue
                    if file_format == "csv":
                        csv_writer.writerow(json.loads(payload))
                    else:
                        if not first:
                            buffer.write(",")
                        buffer.write(payload)
                        first = False
                    if buffer.tell() >= 65536:
                        yield buffer.getvalue()
                        buffer.seek(0)
                        buffer.truncate()
    if file_format == "json":
        buffer.write("]\n")
    yield buffer.getvalue()


@views.get("/sites/{site_id}/export.{file_format}")
def export_history(site_id: str, file_format: Literal["json", "csv"], since: AwareDatetime | None = None):
    return StreamingResponse(
        export_chunks(site_id, file_format, since),
        media_type="application/json" if file_format == "json" else "text/csv",
        headers={"Content-Disposition": f'attachment; filename="solarmind-readings.{file_format}"',
                 "Cache-Control": "no-store"},
    )


@views.get("/weather")
def weather():
    if not config.get("use_live_weather", False):
        return {"source": "daily profile", "weather_available": False}
    try:
        observation = json.loads((data/"weather.json").read_text())
    except FileNotFoundError:
        return {"source": "daily profile", "weather_available": False}
    if observation.get("station") != config.get("weather_station", "EGLL").upper():
        return {"source": "daily profile", "weather_available": False}
    fresh = 0 <= time.time()-observation["observed_epoch"] < 3600
    return {**observation, "weather_available": fresh, "source": observation["provider"] if fresh else "daily profile"}


@views.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).with_name("dashboard.html"))


@views.get("/dashboard/data")
def dashboard_data():
    readings = history(config["site_id"], 100)
    pending = None
    path = data / "queue.db"
    if path.exists():
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='queue'").fetchone():
                total, mqtt, http = db.execute(
                    "SELECT count(*),count(CASE WHEN mqtt=0 THEN 1 END),count(CASE WHEN http=0 THEN 1 END) FROM queue"
                ).fetchone()
                pending = {"Queued readings": total, "Awaiting MQTT": mqtt, "Awaiting HTTP": http}
    return {"readings": readings, "weather": weather(), "queue": pending, "config": config}


@views.get("/arduino")
def arduino():
    try:
        return json.loads((data / "arduino.json").read_text())
    except FileNotFoundError:
        return {"Status": "Waiting for simulator"}


app.include_router(views)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010)
