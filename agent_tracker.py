#!/usr/bin/env python3
import time
import sqlite3
import threading
import datetime
import os
import psutil
import pymongo
from bson import ObjectId

try:
    import pygetwindow as gw
except ImportError:
    gw = None

# === CONFIG ===
from dotenv import load_dotenv

# carica .env dalla directory corrente
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DB_PATH = os.path.expanduser(os.getenv("DB_PATH", "~/activity.db"))
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "300"))
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "productivity")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "activity_logs")

if not MONGO_URI:
    raise ValueError("❌ MONGO_URI mancante. Inseriscilo in .env")


# === INIT ===
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute(
    """
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    process TEXT,
    window_title TEXT,
    cpu_percent REAL,
    synced INTEGER DEFAULT 0
)
"""
)
conn.commit()


def get_active_window():
    """Rileva la finestra attiva."""
    if gw:
        try:
            win = gw.getActiveWindow()
            if win:
                return win.title
        except Exception:
            pass
    return "Unknown"


from datetime import datetime, timezone


def collect_activity():
    """Rileva il processo attivo e la CPU."""
    try:
        process_name = psutil.Process(psutil.Process().pid).name()
    except Exception:
        process_name = "unknown"

    window_title = get_active_window()
    cpu_percent = psutil.cpu_percent(interval=0.5)

    ts = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """
        INSERT INTO activity (timestamp, process, window_title, cpu_percent, synced)
        VALUES (?, ?, ?, ?, 0)
    """,
        (ts, process_name, window_title, cpu_percent),
    )
    conn.commit()


def sync_to_mongo():
    """Invia i dati non sincronizzati a MongoDB Atlas."""
    client = pymongo.MongoClient(MONGO_URI)
    coll = client[MONGO_DB][MONGO_COLLECTION]

    cur.execute("SELECT * FROM activity WHERE synced = 0")
    rows = cur.fetchall()

    if not rows:
        return

    docs = [
        {
            "_id": ObjectId(),
            "timestamp": r[1],
            "process": r[2],
            "window_title": r[3],
            "cpu_percent": r[4],
        }
        for r in rows
    ]

    coll.insert_many(docs)
    ids = [r[0] for r in rows]
    cur.executemany("UPDATE activity SET synced = 1 WHERE id = ?", [(i,) for i in ids])
    conn.commit()


def sync_loop():
    """Thread di sincronizzazione periodica."""
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            sync_to_mongo()
        except Exception as e:
            print("⚠️  Errore sync:", e)


def main():
    threading.Thread(target=sync_loop, daemon=True).start()
    print("🚀 Agent in esecuzione... Ctrl+C per uscire.")

    try:
        while True:
            collect_activity()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n🛑 Arresto agent.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
