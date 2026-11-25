"""Read-only dashboard and telemetry API for other devices on the demo LAN."""
from fastapi import FastAPI
from backend import views

app = FastAPI(title="SolarMind telemetry viewer")
app.include_router(views)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
