#!/usr/bin/env python3
import time
import sqlite3
import platform
import subprocess
import threading
import datetime
import os
import psutil
import Quartz
import tkinter as tk
from tkinter import ttk

# --- Fix Quartz LazyImport bug (ignora warning Pylance) ---
try:
    _ = Quartz.CGEventGetLocation  # type: ignore[attr-defined]
except KeyError:
    from Quartz import CoreGraphics

    Quartz.CGEventGetLocation = CoreGraphics.CGEventGetLocation  # type: ignore[attr-defined]
from pynput import mouse, keyboard
import pymongo
import uuid, re
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# === CONFIG ===
from dotenv import load_dotenv

# carica .env dalla directory corrente
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DB_PATH = os.path.expanduser(os.getenv("DB_PATH", "~/activity.db"))
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "300"))
TRACKING_INTERVAL = int(os.getenv("TRACKING_INTERVAL", "30"))
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "productivity")
ACTIVITY_LOGS_TABLE = "activity_logs"
PROCESS_WINDOW_TABLE = "process_windows"
DEVICES_TABLE = "devices"
PROCESS_BLACKLIST = [
    "[PAUSE]",
    "[RESUME]",
    "unknown",
    "Finder",
    "Activity Monitor",
    "Agent Tracker",
]

root = None
mongo_executor = ThreadPoolExecutor(max_workers=2)
_last_timer = {}

# === IDENTIFICATORI DEVICE ===
DEVICE_ID = str(uuid.getnode())
USERNAME = os.getenv("USERNAME") or os.getenv("USER") or "unknown"
SYSTEM = platform.system()
DEVICE_NAME = platform.node()

# tempo di inattività massimo in secondi (es. 60 = 1 minuto)
INACTIVITY_THRESHOLD = 60
_last_input_time = time.time()

DEV_SHELLS = ("zsh", "bash", "fish")
DEV_COMMANDS = [
    "git",
]
MAX_AGE = 10

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

mongo_client = pymongo.MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB]


def get_apps():
    global mongo_db
    col = mongo_db[PROCESS_WINDOW_TABLE]

    voices = list(
        col.find(
            {
                "device_id": DEVICE_ID,
                "process": {"$not": {"$regex": r"\[PAUSE\]|\[RESUME\]|unknown"}},
            },
            {"_id": 1, "process": 1, "window_title": 1, "level": 1},
        )
    )
    return voices


APPS = get_apps()
indicators = {}


def add_process_window(i, voce):
    global root

    if voce in PROCESS_BLACKLIST:
        return
    initial_level = voce["level"] if isinstance(voce["level"], (int, float)) else 5

    # pallino di stato
    indicator = tk.Label(root, text="●", fg="gray", bg="white", font=("Arial", 12))
    indicator.grid(row=i, column=0, padx=5, pady=3, sticky="w")

    # testo app
    text_label = tk.Label(
        root,
        text=f"{voce['process']} ({voce['window_title']})",
        bg="white",
        fg="black",
        font=("Arial", 10),
    )
    text_label.grid(row=i, column=1, sticky="w", padx=5, pady=3)

    indicators[voce["_id"]] = {
        "indicator": indicator,
        "label": text_label,
        "process": voce["process"],
        "window_title": voce["window_title"],
    }

    def set_level_async(voce_id, level=5):
        def worker():
            try:
                col = mongo_db[PROCESS_WINDOW_TABLE]
                result = col.update_one({"_id": voce_id}, {"$set": {"level": level}})

                if result.modified_count:
                    print(f"✅ Aggiornato {voce_id} → level {level}")
                else:
                    print(f"ℹ️ Nessun cambiamento {voce_id} → {level}")
            except Exception as e:
                print("[SET LEVEL ERROR]", e)

        mongo_executor.submit(worker)

    # callback per quando rilasci il mouse
    def on_release(event, voce_id):
        level = int(float(event.widget.get()))
        if voce_id in _last_timer:
            _last_timer[voce_id].cancel()
        _last_timer[voce_id] = threading.Timer(
            0.3, lambda: set_level_async(voce_id, level)
        )
        _last_timer[voce_id].start()

    scale = ttk.Scale(root, from_=1, to=10, orient="horizontal", length=150)
    scale.set(initial_level)
    scale.grid(row=i, column=2, padx=10, pady=3)
    scale.bind("<ButtonRelease-1>", lambda e, vid=voce["_id"]: on_release(e, vid))


def render_apps():
    for i, voce in enumerate(APPS, start=1):
        add_process_window(i, voce)


def update_active_indicator(root):
    """Aggiorna i colori per l'app attiva."""
    try:
        active_process, active_title = get_active_window()
        for data in indicators.values():
            if (
                data["process"] == active_process
                and data["window_title"] == active_title
            ):
                data["indicator"].config(fg="green")
                data["label"].config(fg="green", font=("Arial", 10, "bold"))
            else:
                data["indicator"].config(fg="gray")
                data["label"].config(fg="black", font=("Arial", 10))
    except Exception as e:
        print("[UI UPDATE ERROR]", e)
    finally:
        root.after(1000, update_active_indicator, root)


def main_window():
    """
    Finestra con slider da 1 a 10 per ogni voce.
    """
    global root

    root = tk.Tk()
    root.title("Livelli di attenzione")
    root.geometry("640x480")
    root.configure(bg="white")

    # intestazioni
    tk.Label(
        root, text="Finestra", bg="white", fg="black", font=("Arial", 10, "bold")
    ).grid(row=0, column=0, padx=10, pady=5, sticky="w")
    tk.Label(
        root, text="Livello", bg="white", fg="black", font=("Arial", 10, "bold")
    ).grid(row=0, column=1, padx=10, pady=5, sticky="e")

    update_active_indicator(root)
    render_apps()

    root.mainloop()


def sync_device():
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        col = db[DEVICES_TABLE]

        db[DEVICES_TABLE].create_index([("device_id", 1)], unique=True)

        col.update_one(
            {
                "device_id": DEVICE_ID,
            },
            {
                "$setOnInsert": {
                    "device_id": DEVICE_ID,
                    "user_id": None,
                }
            },
            upsert=True,
        )
    except Exception as e:
        print("[DEVICE SYNC ERROR]", e)

    print(f"[DEVICE SYNC] {DEVICE_ID}")


def on_input_activity(*args, **kwargs):
    global _last_input_time
    _last_input_time = time.time()


# listener mouse e tastiera
mouse.Listener(
    on_move=on_input_activity, on_click=on_input_activity, on_scroll=on_input_activity
).start()
keyboard.Listener(on_press=on_input_activity).start()


def is_user_active():
    """Ritorna True se l'utente è attivo (input recente)."""
    return (time.time() - _last_input_time) < INACTIVITY_THRESHOLD


def get_active_window():
    """
    Ritorna (process_name, window_title_or_site) della finestra attiva in modo cross-platform.
    Per i browser prova a estrarre il dominio del sito.
    """
    system = platform.system()

    # --- macOS ---
    if system == "Darwin":
        app_name, window_title = "unknown", "Unknown"

        try:
            script = """
                tell application "System Events"
                    set frontApp to name of first application process whose frontmost is true
                    return frontApp
                end tell
                """
            result = subprocess.check_output(["osascript", "-e", script])
            app_name = result.decode("utf-8").strip()
            if app_name != "Electron":
                window_title = app_name
            else:
                from AppKit import NSWorkspace  # type: ignore

                active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
                app_name = active_app.localizedName()
                window_title = app_name
        except Exception as e:
            print(f"[WARN] MAC OS active window detection failed: {e}")

        # Browser principali
        if app_name in ["Google Chrome", "Safari", "Firefox", "Brave Browser"]:
            scripts = {
                "Google Chrome": """
                    tell application "Google Chrome"
                        if windows = {} then return ""
                        return URL of active tab of front window
                    end tell
                """,
                "Safari": """
                    tell application "Safari"
                        if windows = {} then return ""
                        return URL of current tab of front window
                    end tell
                """,
                "Firefox": """
                    tell application "Firefox"
                        if windows = {} then return ""
                        return URL of current tab of front window
                    end tell
                """,
                "Brave Browser": """
                    tell application "Brave Browser"
                        if windows = {} then return ""
                        return URL of current tab of front window
                    end tell
                """,
            }
            try:
                url = (
                    subprocess.check_output(["osascript", "-e", scripts[app_name]])
                    .decode()
                    .strip()
                )
                if url:
                    # estrai dominio
                    match = re.search(r"https?://([a-zA-Z0-9.-]+)", url)
                    if match:
                        window_title = match.group(1)
                    else:
                        window_title = url
                else:
                    window_title = app_name
            except Exception:
                window_title = app_name

        return app_name, window_title or app_name

    # --- Windows ---
    elif system == "Windows":
        try:
            import win32gui  # type: ignore
            import win32process  # type: ignore

            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            window_title = win32gui.GetWindowText(hwnd)

            # se sembra un URL o un titolo browser, prova a estrarre dominio
            match = re.search(r"https?://([a-zA-Z0-9.-]+)", window_title)
            if match:
                window_title = match.group(1)

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
            if not title:
                title = "Unknown"

            # prova a estrarre dominio
            match = re.search(r"https?://([a-zA-Z0-9.-]+)", title)
            if match:
                title = match.group(1)

            return "unknown", title
        except Exception:
            return "unknown", "Unknown"

    # --- fallback ---
    else:
        return "unknown", "Unknown"


def collect_terminal_activity():
    """Monitora la shell history e registra i comandi DEV rilevanti."""
    history_file = os.path.expanduser("~/.zsh_history")

    try:
        proc = subprocess.Popen(
            ["tail", "-F", history_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        if proc.stdout is None:
            print("[TERMINAL ERROR] Nessun output da tail -F")
            return

        for line in proc.stdout:
            line = line.strip()
            if not line or ";" not in line:
                continue

            cmdline = line.split(";", 1)[1].strip()
            if not cmdline:
                continue

            for cmd in DEV_COMMANDS:
                if cmdline.startswith(cmd + " "):
                    ts = datetime.now(timezone.utc).isoformat()
                    process_name = cmd
                    window_title = "terminal"

                    eventTrack(process_name, window_title)

                    print(f"[TERMINAL] {cmd} command logged ✅")
                    break

    except Exception as e:
        print("[TERMINAL ERROR]", e)


def sync_to_mongo():
    """Sincronizza le attività non ancora inviate."""
    conn_sync = None
    try:
        conn_sync = sqlite3.connect(DB_PATH)
        cur_sync = conn_sync.cursor()

        unsynced = cur_sync.execute(
            "SELECT * FROM activity WHERE synced = 0"
        ).fetchall()
        if not unsynced:
            return

        client = pymongo.MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        col_activity = db[ACTIVITY_LOGS_TABLE]
        col_process = db[PROCESS_WINDOW_TABLE]

        db[PROCESS_WINDOW_TABLE].create_index(
            [("device_id", 1), ("process", 1), ("window_title", 1)], unique=True
        )

        # --- 1️⃣ Inserisci attività ---
        docs = [
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
            for r in unsynced
        ]

        col_activity.insert_many(docs)

        # --- 2️⃣ Aggiorna tabella processi univoci ---
        for doc in docs:
            try:
                col_process.update_one(
                    {
                        "device_id": doc["device_id"],
                        "process": doc["process"],
                        "window_title": doc["window_title"],
                    },
                    {
                        "$setOnInsert": {
                            "device_id": doc["device_id"],
                            "process": doc["process"],
                            "window_title": doc["window_title"],
                            "level": 5,  # 5 is default
                            "active": True,
                        }
                    },
                    upsert=True,
                )
            except Exception as e:
                print("[PROCESS UPSERT ERROR]", e)

        cur_sync.execute("UPDATE activity SET synced = 1 WHERE synced = 0")
        conn_sync.commit()
        print(f"[SYNC] {len(docs)} record sincronizzati su MongoDB")

    except Exception as e:
        print("[SYNC ERROR]", e)

    finally:
        if conn_sync:
            conn_sync.close()


def sync_loop():
    """Thread di sincronizzazione periodica, con connessione indipendente."""
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            sync_to_mongo()
        except Exception as e:
            print("⚠️  Errore nel thread di sync:", e)


def eventTrack(process_name, window_title):
    conn_local = None
    try:
        conn_local = sqlite3.connect(DB_PATH)
        cur_local = conn_local.cursor()
        ts = datetime.now(timezone.utc).isoformat()
        cpu_percent = psutil.cpu_percent(interval=None)

        print(f"[EVENT TRACK] {process_name} {window_title}")

        cur_local.execute(
            """
                INSERT INTO activity (timestamp, process, window_title, cpu_percent, synced, device_id, username)
                VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (
                ts,
                process_name,
                window_title,
                cpu_percent,
                DEVICE_ID,
                USERNAME,
            ),
        )
        conn_local.commit()

        # --- Aggiorna GUI se nuova voce ---
        def maybe_add_to_ui():
            if any(
                data["window_title"] == window_title for data in indicators.values()
            ):
                return

            voce = {
                "_id": f"{process_name}:{window_title}",
                "process": process_name,
                "window_title": window_title,
                "level": 5,
            }
            row_index = len(indicators) + 1
            add_process_window(row_index, voce)

        if root:
            root.after(0, maybe_add_to_ui)
    except Exception as e:
        print("[TRACK ERROR]", e)

    finally:
        if conn_local:
            try:
                conn_local.close()
            except Exception as e:
                print("[CLOSE ERROR]", e)


def tracking():
    """Thread di tracking periodica."""
    try:
        paused = False
        last_window = None
        last_process = None

        while True:
            if not is_user_active():
                if not paused:
                    print("[PAUSE] Nessuna attività utente, tracking sospeso... ⏸️")
                    paused = True
                    eventTrack("[PAUSE]", "[PAUSE]")

                time.sleep(TRACKING_INTERVAL)
                continue
            elif paused:
                print("[RESUME] Attività rilevata, tracking ripreso ✅")
                paused = False

                eventTrack("[RESUME]", "[RESUME]")

            result = get_active_window()
            process_name, window_title = (
                result if result and len(result) == 2 else ("unknown", "Unknown")
            )
            process_name = os.path.basename(process_name)
            process_name = re.sub(r"\.app$", "", process_name, flags=re.IGNORECASE)
            ignored_processes = ["agent_tracker", "Python", "Finder", "unknown"]

            if process_name in ignored_processes:
                continue

            if window_title != last_window or process_name != last_process:
                eventTrack(process_name, window_title)
                last_window = window_title
                last_process = process_name

            time.sleep(TRACKING_INTERVAL)

    except KeyboardInterrupt:
        print("\nArresto richiesto dall'utente.")
    except Exception as e:
        print("[TRACKING FATAL ERROR]", e)


def main():
    print("[AGENT TRACKER] Avviato... Ctrl+C per fermare.")
    sync_device()

    while True:
        time.sleep(1)


def start_listeners():
    mouse.Listener(
        on_move=on_input_activity,
        on_click=on_input_activity,
        on_scroll=on_input_activity,
    ).start()
    keyboard.Listener(on_press=on_input_activity).start()


if __name__ == "__main__":
    threading.Thread(target=tracking, daemon=True).start()
    threading.Thread(target=sync_loop, daemon=True).start()
    threading.Thread(target=start_listeners, daemon=True).start()
    threading.Thread(target=collect_terminal_activity, daemon=True).start()

    main_window()
    main()
