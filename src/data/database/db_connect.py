"""
MongoDB connection for Housing Aid Navigator.
Connects to H4HDB1 on MongoDB Atlas using credentials from .env
"""

import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

load_dotenv()

_client = None
_db = None


def get_client() -> MongoClient:
    """Return a singleton MongoClient, creating it on first call."""
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI")
        if not uri:
            raise ValueError("MONGO_URI not set. Check your .env file.")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    """Return the H4HDB1 database object."""
    global _db
    if _db is None:
        db_name = os.getenv("MONGO_DB_NAME", "H4HDB1")
        _db = get_client()[db_name]
    return _db


def get_programs_collection():
    """Return the 'programs' collection."""
    return get_db()["programs"]


def ping():
    """
    Test the connection. Returns True if successful, raises on failure.
    Run this at startup to fail fast if the DB is unreachable.
    """
    try:
        get_client().admin.command("ping")
        print("[db] Connected to MongoDB Atlas — H4HDB1")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        msg = str(e)
        if "SSL" in msg or "tls" in msg.lower():
            print("[db] SSL error — your IP is likely not whitelisted in MongoDB Atlas.")
            print("[db] Fix: Atlas dashboard → Network Access → Add IP (0.0.0.0/0 for hackathon)")
        print(f"[db] Connection failed: {e}")
        raise


if __name__ == "__main__":
    # Quick connection test: python -m src.data.database.db_connect
    ping()
    programs = get_programs_collection()
    count = programs.count_documents({})
    print(f"[db] Programs in collection: {count}")
