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

# === CONFIG ===
from dotenv import load_dotenv

# carica .env dalla directory corrente
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DB_PATH = os.path.expanduser(os.getenv("DB_PATH", "~/activity.db"))
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "300"))
TRACKING_INTERVAL = int(os.getenv("TRACKING_INTERVAL", "30"))
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "productivity")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "activity_logs")

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

        print(f"[Active Window] {window_title}")

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


_insert_counter = 0


def collect_activity():
    global _insert_counter

    print(f"[collect_activity]")

    try:
        result = get_active_window()
        if not result or len(result) != 2:
            process_name, window_title = "unknown", "Unknown"
        else:
            process_name, window_title = result

        # --- normalizza il nome del processo ---
        process_name = os.path.basename(process_name)  # prende solo il nome finale
        process_name = re.sub(
            r"\.app$", "", process_name, flags=re.IGNORECASE
        )  # rimuove .app

        print(f"[Activity] {process_name} - {window_title}")

    except Exception:
        process_name, window_title = "unknown", "Unknown"

    cpu_percent = psutil.cpu_percent(interval=None)
    ts = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """
        INSERT INTO activity (timestamp, process, window_title, cpu_percent, synced, device_id, username)
        VALUES (?, ?, ?, ?, 0, ?, ?)
        """,
        (ts, process_name, window_title, cpu_percent, DEVICE_ID, USERNAME),
    )

    _insert_counter += 1
    if _insert_counter >= 10:
        conn.commit()
        _insert_counter = 0

    conn.commit()


def collect_terminal_activity():
    """Monitora la shell history e registra i comandi DEV rilevanti."""
    print("[TERMINAL TRACKER] Avviato...")
    history_file = os.path.expanduser("~/.zsh_history")

    try:
        proc = subprocess.Popen(
            ["tail", "-F", history_file],
            stdout=subprocess.PIPE,  # 👈 garantisce che stdout non sia None
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
                    cpu_percent = psutil.cpu_percent(interval=None)

                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    cur.execute(
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
                    conn.commit()
                    conn.close()

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
        col = db[MONGO_COLLECTION]

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

        col.insert_many(docs)
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


last_sync = time.time()


def tracking():
    """Thread di tracking periodica."""
    conn_local = None  # 👈 previene NameError nel finally
    try:
        conn_local = sqlite3.connect(DB_PATH)
        cur_local = conn_local.cursor()
        paused = False
        while True:
            if not is_user_active():
                if not paused:
                    print("[PAUSE] Nessuna attività utente, tracking sospeso...")
                    paused = True
                time.sleep(TRACKING_INTERVAL)
                continue
            elif paused:
                print("[RESUME] Attività rilevata, tracking ripreso ✅")
                paused = False

            try:
                result = get_active_window()
                process_name, window_title = (
                    result if result and len(result) == 2 else ("unknown", "Unknown")
                )
                process_name = os.path.basename(process_name)
                process_name = re.sub(r"\.app$", "", process_name, flags=re.IGNORECASE)
                cpu_percent = psutil.cpu_percent(interval=None)
                ts = datetime.now(timezone.utc).isoformat()

                cur_local.execute(
                    """
                    INSERT INTO activity (timestamp, process, window_title, cpu_percent, synced, device_id, username)
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (ts, process_name, window_title, cpu_percent, DEVICE_ID, USERNAME),
                )
                conn_local.commit()
            except Exception as e:
                print("[TRACK ERROR]", e)

            time.sleep(TRACKING_INTERVAL)

    except KeyboardInterrupt:
        print("\nArresto richiesto dall'utente.")
    except Exception as e:
        print("[TRACKING FATAL ERROR]", e)
    finally:
        if conn_local:
            try:
                conn_local.close()
            except Exception as e:
                print("[CLOSE ERROR]", e)


def main():
    print("Agent tracker avviato... Ctrl+C per fermare.")
    while True:
        time.sleep(1)


def start_listeners():
    mouse.Listener(
        on_move=on_input_activity,
        on_click=on_input_activity,
        on_scroll=on_input_activity,
    ).start()
    keyboard.Listener(on_press=on_input_activity).start()


threading.Thread(target=start_listeners, daemon=True).start()

if __name__ == "__main__":
    threading.Thread(target=sync_loop, daemon=True).start()
    threading.Thread(target=tracking, daemon=True).start()
    threading.Thread(target=collect_terminal_activity, daemon=True).start()
    main()
