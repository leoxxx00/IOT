from contextlib import asynccontextmanager
from typing import Literal, Optional
from datetime import datetime, timezone
from pymongo.errors import PyMongoError
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from config import API_CONFIG
from mqtt_chat import COLLECTION_NAME, TOPIC_PREFIX
from mongo_repository import TelemetryRepository
from mqtt_commands import MQTTCommandPublisher

repository = None
command_publisher = None

@asynccontextmanager
async def lifespan(app):
    global repository, command_publisher
    repository = TelemetryRepository()
    repository.ping()
    command_publisher = MQTTCommandPublisher()
    yield
    command_publisher.close()
    repository.close()

app = FastAPI(title=API_CONFIG["title"], version=API_CONFIG["version"], lifespan=lifespan)

class CommandRequest(BaseModel):
    command: str = Field(..., description="START, STOP or STATUS")
    reason: Optional[str] = None
    correlation_id: Optional[str] = None

def serialize(doc):
    if not doc: return None
    doc = dict(doc)
    if "_id" in doc: doc["_id"] = str(doc["_id"])
    for k,v in list(doc.items()):
        if hasattr(v, "isoformat"): doc[k] = v.isoformat()
    return doc

@app.get("/health", tags=["Platform"])
def health():
    try: repository.ping(); mongo = "healthy"
    except Exception: mongo = "unavailable"
    mqtt = "healthy" if command_publisher and command_publisher.connected else "unavailable"
    return {"status": "healthy" if mongo == "healthy" and mqtt == "healthy" else "degraded",
            "services": {"mongodb": mongo, "mqtt": mqtt}}

@app.get("/devices/{device_id}/telemetry/latest", tags=["Telemetry"])
def latest_telemetry(device_id: str):
    doc = repository.latest(device_id)
    if not doc: raise HTTPException(404, f"No telemetry found for {device_id}")
    return serialize(doc)

@app.get("/devices/{device_id}/telemetry", tags=["Telemetry"])
def telemetry_history(device_id: str, limit: int = Query(20, ge=1, le=100)):
    docs = repository.history(device_id, limit)
    return {"device_id": device_id, "count": len(docs), "records": [serialize(d) for d in docs]}

@app.get("/devices/{device_id}/events/warnings", tags=["Telemetry"])
def warning_events(device_id: str, limit: int = Query(20, ge=1, le=100)):
    docs = repository.warnings(device_id, limit)
    return {"device_id": device_id, "count": len(docs), "records": [serialize(d) for d in docs]}

@app.get("/devices/{device_id}/status", tags=["Devices"])
def device_status(device_id: str):
    doc = repository.latest(device_id)
    if not doc: raise HTTPException(404, f"No status available for {device_id}")
    return {"device_id": device_id, "state": doc.get("state"), "timestamp": doc.get("timestamp"), "message": doc.get("message")}

@app.post("/devices/{device_id}/commands", tags=["Commands"])
def send_command(device_id: str, request: CommandRequest):
    command = request.command.upper().strip()
    if command not in {"START", "STOP", "STATUS"}:
        raise HTTPException(400, "Unsupported command. Use START, STOP or STATUS.")
    try:
        result = command_publisher.send_command(device_id, command, request.reason, request.correlation_id)
    except Exception as exc:
        raise HTTPException(503, str(exc))
    return {"status": "accepted", "message": "Command published to MQTT.", **result}

class ChatRequest(BaseModel):
    sender: Literal["alice", "bob"]
    text: str = Field(min_length=1, max_length=8192)


@app.get("/chat/messages", tags=["Chat"])
def chat_history(limit: int = Query(10, ge=1, le=100)):
    collection = repository.collection.database[COLLECTION_NAME]
    try:
        records = list(collection.find().sort([("timestamp", -1), ("_id", -1)]).limit(limit))
    except PyMongoError as exc:
        raise HTTPException(503, "Chat history unavailable") from exc
    return [serialize(record) for record in reversed(records)]


@app.post("/chat/messages", status_code=201, tags=["Chat"])
def post_chat(request: ChatRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(422, "Enter a message containing text.")
    document = {
        "sender": request.sender,
        "recipient": "bob" if request.sender == "alice" else "alice",
        "text": text,
        "timestamp": datetime.now(timezone.utc),
    }
    try:
        repository.collection.database[COLLECTION_NAME].insert_one(document)
    except PyMongoError as exc:
        raise HTTPException(503, "Could not save chat message") from exc

    acknowledged = False
    try:
        result = command_publisher.client.publish(
            f"{TOPIC_PREFIX}/{request.sender}", text, qos=1
        )
        if result.rc == 0:
            result.wait_for_publish(timeout=3)
            acknowledged = result.is_published()
    except (RuntimeError, ValueError, OSError):
        pass
    return {"message": serialize(document), "broker_acknowledged": acknowledged}
