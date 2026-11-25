import argparse
from datetime import datetime, timezone
from threading import Event

import paho.mqtt.client as mqtt
from pymongo import MongoClient
from pymongo.errors import PyMongoError


MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MONGO_URI = "mongodb://127.0.0.1:27017"
DATABASE_NAME = "aiot_platform"
COLLECTION_NAME = "chat_messages"
TOPIC_PREFIX = "iot/demo/chat"


def show_history(messages, name, peer):
    conversation = {
        "$or": [
            {"sender": name, "recipient": peer},
            {"sender": peer, "recipient": name},
        ]
    }

    try:
        recent = list(
            messages.find(conversation)
            .sort([("timestamp", -1), ("_id", -1)])
            .limit(10)
        )
    except PyMongoError as exc:
        print(f"Could not load history: {exc}")
        return

    if not recent:
        print("No saved messages yet.")
        return

    for message in reversed(recent):
        print(f"{message['sender']}: {message['text']}")


def main():
    parser = argparse.ArgumentParser(description="Two-person MQTT chat")
    parser.add_argument("name", choices=["alice", "bob"])
    name = parser.parse_args().name
    peer = "bob" if name == "alice" else "alice"

    send_topic = f"{TOPIC_PREFIX}/{name}"
    receive_topic = f"{TOPIC_PREFIX}/{peer}"
    ready = Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Broker rejected the connection: {reason_code}")
            return
        client.subscribe(receive_topic, qos=1)

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        if reason_codes and not reason_codes[0].is_failure:
            ready.set()

    def on_disconnect(client, userdata, flags, reason_code, properties):
        ready.clear()

    def on_message(client, userdata, message):
        text = message.payload.decode("utf-8", errors="replace")
        print(f"\n{peer}: {text}", flush=True)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    with MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tz_aware=True) as mongo:
        try:
            mongo.admin.command("ping")
        except PyMongoError as exc:
            raise SystemExit(f"Could not connect to MongoDB: {exc}")

        messages = mongo[DATABASE_NAME][COLLECTION_NAME]

        try:
            client.connect(MQTT_HOST, MQTT_PORT)
        except OSError as exc:
            raise SystemExit(f"Could not connect to Mosquitto: {exc}")

        client.loop_start()
        try:
            if not ready.wait(timeout=5):
                raise SystemExit("Could not subscribe to the chat topic.")

            print(f"Connected as {name}. Type a message, /history, or /quit.")

            while True:
                text = input("> ").strip()
                if text == "/quit":
                    break
                if text == "/history":
                    show_history(messages, name, peer)
                    continue
                if not text:
                    continue

                try:
                    messages.insert_one(
                        {
                            "sender": name,
                            "recipient": peer,
                            "text": text,
                            "timestamp": datetime.now(timezone.utc),
                        }
                    )
                except PyMongoError as exc:
                    print(f"Could not save the message: {exc}")
                    continue

                if not ready.is_set():
                    print("Message saved to history. MQTT is reconnecting.")
                    continue

                result = client.publish(send_topic, text, qos=1)
                try:
                    result.wait_for_publish(timeout=5)
                except RuntimeError as exc:
                    print(f"Message saved to history. MQTT publish error: {exc}")
                    continue

                if not result.is_published():
                    print("Message saved to history. Broker acknowledgment timed out.")

        except (KeyboardInterrupt, EOFError):
            print()
        finally:
            client.disconnect()
            client.loop_stop()


if __name__ == "__main__":
    main()