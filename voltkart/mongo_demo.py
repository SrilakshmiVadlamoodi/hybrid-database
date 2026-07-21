"""
mongo_demo.py — inserts VoltKart support-chat transcripts into MongoDB as
documents, then queries them by customer and by date range.

Why Mongo here: chat transcripts are variable-length, nested, semi-structured
data (arrays of messages with sender/timestamp) that don't fit a rigid
relational schema well — a natural fit for a document store, complementing
the structured Postgres tables (customers, orders, etc.) in this hybrid setup.

Run: python mongo_demo.py
"""
import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "voltkart")

AGENT_LINES = [
    "Hi, thanks for reaching out to VoltKart support. How can I help you today?",
    "I'm sorry to hear that. Let me check your order details.",
    "I've raised a replacement request for you.",
    "Your refund has been initiated and should reflect in 3-5 business days.",
    "Is there anything else I can help you with?",
]
CUSTOMER_LINES = [
    "My order hasn't arrived yet, it's been 5 days.",
    "The product I received is defective.",
    "I was charged twice for the same order.",
    "I want to return this item, it doesn't match the description.",
    "Thanks, that resolves my issue.",
]


def build_transcript(customer_id, order_id, base_time):
    messages = []
    t = base_time
    for i in range(random.randint(3, 6)):
        sender, text = ("customer", random.choice(CUSTOMER_LINES)) if i % 2 == 0 else ("agent", random.choice(AGENT_LINES))
        messages.append({"sender": sender, "text": text, "timestamp": t})
        t += timedelta(minutes=random.randint(1, 10))
    return {
        "customer_id": customer_id,
        "order_id": order_id,
        "channel": random.choice(["chat", "whatsapp", "email"]),
        "started_at": base_time,
        "messages": messages,
    }


def seed_transcripts(collection, n=25):
    collection.delete_many({})
    docs = []
    for i in range(n):
        customer_id = random.randint(1, 60)  # matches customer_id range seeded in Postgres
        order_id = random.randint(1, 100) if random.random() < 0.8 else None
        base_time = datetime.now() - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
        docs.append(build_transcript(customer_id, order_id, base_time))
    collection.insert_many(docs)
    print(f"Inserted {len(docs)} chat transcripts.")


def query_by_customer(collection, customer_id):
    print(f"\n--- Transcripts for customer_id={customer_id} ---")
    for doc in collection.find({"customer_id": customer_id}):
        print(f"channel={doc['channel']} started_at={doc['started_at']} messages={len(doc['messages'])}")


def query_by_date_range(collection, days_back):
    since = datetime.now() - timedelta(days=days_back)
    print(f"\n--- Transcripts started in the last {days_back} days ---")
    cursor = collection.find({"started_at": {"$gte": since}}).sort("started_at", -1)
    count = 0
    for doc in cursor:
        count += 1
        print(f"customer_id={doc['customer_id']} channel={doc['channel']} started_at={doc['started_at']}")
    print(f"Total: {count} transcripts")


def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db["support_chat_transcripts"]

    random.seed(42)
    seed_transcripts(collection, n=25)

    # Index to speed up the by-customer and by-date queries (Mongo's B-tree-based index)
    collection.create_index("customer_id")
    collection.create_index("started_at")

    query_by_customer(collection, customer_id=5)
    query_by_date_range(collection, days_back=7)

    client.close()


if __name__ == "__main__":
    main()
