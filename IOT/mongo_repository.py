from pymongo import MongoClient, DESCENDING
from config import MONGODB_CONFIG

class TelemetryRepository:
    def __init__(self):
        self.client = MongoClient(MONGODB_CONFIG["uri"], serverSelectionTimeoutMS=5000)
        self.collection = self.client[MONGODB_CONFIG["database"]][MONGODB_CONFIG["collection"]]
    def ping(self):
        self.client.admin.command("ping")
    def latest(self, device_id):
        return self.collection.find_one({"device_id": device_id}, sort=[("timestamp", DESCENDING)])
    def history(self, device_id, limit=20):
        limit = max(1, min(limit, 100))
        return list(self.collection.find({"device_id": device_id}).sort("timestamp", DESCENDING).limit(limit))
    def warnings(self, device_id, limit=20):
        limit = max(1, min(limit, 100))
        return list(self.collection.find({"device_id": device_id, "state": "WARNING"}).sort("timestamp", DESCENDING).limit(limit))
    def close(self):
        self.client.close()
