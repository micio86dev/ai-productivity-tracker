#!/usr/bin/env python3
import time
import sqlite3
import platform
import subprocess
import threading
import datetime
import os
import psutil
import pymongo
import uuid, hashlib, re
from datetime import datetime, timezone

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

# === IDENTIFICATORI DEVICE ===
DEVICE_ID = str(uuid.getnode())
USERNAME = os.getenv("USERNAME") or os.getenv("USER") or "unknown"
SYSTEM = platform.system()
DEVICE_NAME = platform.node()

DEV_COMMANDS = [
    "git",
    "node",
    "npm",
    "npx",
    "python",
    "php",
    "composer",
    "docker",
    "bun",
    "yarn",
]

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
    synced INTEGER DEFAULT 0,
    device_id TEXT,
    username TEXT
)
"""
)
conn.commit()


def get_active_window():
    """Ritorna (process_name, window_title) della finestra attiva in modo cross-platform."""
    system = platform.system()

    # --- macOS ---
    if system == "Darwin":
        try:
            from AppKit import NSWorkspace  # type: ignore

            active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
            app_name = active_app.localizedName()
            return app_name, app_name
        except Exception as e:
            print(f"[WARN] macOS active window detection failed: {e}")
            return "unknown", "Unknown"

    # --- Windows ---
    elif system == "Windows":
        try:
            import win32gui  # type: ignore
            import win32process  # type: ignore

            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            window_title = win32gui.GetWindowText(hwnd)
            return proc.name(), window_title or proc.name()
        except Exception as e:
            print(f"[WARN] Windows active window detection failed: {e}")
            return "unknown", "Unknown"

    # --- Linux ---
    elif system == "Linux":
        try:
            title = (
                subprocess.check_output(
                    ["xdotool", "getwindowfocus", "getwindowname"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
            return "unknown", title or "Unknown"
        except Exception:
            return "unknown", "Unknown"

    # --- fallback ---
    else:
        return "unknown", "Unknown"


def collect_activity():
    process_name, window_title = get_active_window()
    cpu_percent = psutil.cpu_percent(interval=0.5)
    ts = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """
        INSERT INTO activity (timestamp, process, window_title, cpu_percent, synced, device_id, username)
        VALUES (?, ?, ?, ?, 0, ?, ?)
        """,
        (ts, process_name, window_title, cpu_percent, DEVICE_ID, USERNAME),
    )
    conn.commit()


_last_seen = {}


def collect_terminal_activity():
    """Rileva processi dev attivi (con filtro duplicati temporanei)."""
    global _last_seen
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"]) if proc.info["cmdline"] else ""
            if any(re.search(rf"\b{cmd}\b", cmdline) for cmd in DEV_COMMANDS):
                key = hashlib.sha1(cmdline.encode()).hexdigest()
                now = time.time()
                # ignora se lo stesso comando è già loggato negli ultimi 60s
                if key in _last_seen and now - _last_seen[key] < 60:
                    continue
                _last_seen[key] = now

                ts = datetime.now(timezone.utc).isoformat()
                cur.execute(
                    """
                    INSERT INTO activity (timestamp, process, window_title, cpu_percent, synced, device_id, username)
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (ts, cmdline[:1000], "terminal", 0, DEVICE_ID, USERNAME),
                )
                conn.commit()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def sync_to_mongo():
    """Sincronizza le attività non ancora inviate."""
    unsynced = cur.execute("SELECT * FROM activity WHERE synced = 0").fetchall()
    if not unsynced:
        return

    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        col = db[MONGO_COLLECTION]

        docs = []
        for r in unsynced:
            docs.append(
                {
                    "timestamp": r[1],
                    "process": r[2],
                    "window_title": r[3],
                    "cpu_percent": r[4],
                    "device_id": r[6],
                    "username": r[7],
                    "system": SYSTEM,
                    "device_name": DEVICE_NAME,
                }
            )

        col.insert_many(docs)
        cur.execute("UPDATE activity SET synced = 1 WHERE synced = 0")
        conn.commit()
        print(f"[SYNC] {len(docs)} record sincronizzati su MongoDB")

    except Exception as e:
        print("[SYNC ERROR]", e)


def sync_loop():
    """Thread di sincronizzazione periodica."""
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            sync_to_mongo()
        except Exception as e:
            print("⚠️  Errore sync:", e)


def main():
    print("Agent tracker avviato... Ctrl+C per fermare.")
    last_sync = time.time()

    try:
        while True:
            collect_activity()
            collect_terminal_activity()

            if time.time() - last_sync > SYNC_INTERVAL:
                sync_to_mongo()
                last_sync = time.time()

            time.sleep(5)

    except KeyboardInterrupt:
        print("\nArresto richiesto dall'utente.")
    finally:
        conn.close()


if __name__ == "__main__":
    threading.Thread(target=sync_loop, daemon=True).start()
    main()
