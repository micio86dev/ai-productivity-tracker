"""Configurazione centralizzata dell'applicazione"""

import os
import sys
from pathlib import Path
import uuid
import platform
from dotenv import load_dotenv


class Config:
    """Configurazione centralizzata"""

    def __init__(self):
        BASE_DIR = Path(
            getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
        )
        env_path = BASE_DIR / ".env"

        load_dotenv(env_path)

        # Database
        self.DB_PATH = os.path.expanduser(os.getenv("DB_PATH", "~/activity.db"))
        self.MONGO_URI = os.getenv("MONGO_URI")
        self.MONGO_DB = os.getenv("MONGO_DB", "productivity")

        # Intervals (seconds)
        self.SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "300"))
        self.TRACKING_INTERVAL = int(os.getenv("TRACKING_INTERVAL", "30"))
        self.INACTIVITY_THRESHOLD = 60

        # Tables
        self.ACTIVITY_LOGS_TABLE = "activity_logs"
        self.PROCESS_WINDOW_TABLE = "process_windows"
        self.DEVICES_TABLE = "devices"

        # Device info
        self.DEVICE_ID = str(uuid.getnode())
        self.USERNAME = os.getenv("USERNAME") or os.getenv("USER") or "unknown"
        self.SYSTEM = platform.system()
        self.DEVICE_NAME = platform.node()

        # Blacklists
        self.PROCESS_BLACKLIST = [
            "[PAUSE]",
            "[RESUME]",
            "unknown",
            "Finder",
            "Activity Monitor",
            "AgentTracker",
            "Electron",
            "Python",
        ]
        self.IGNORED_PROCESSES = ["[PAUSE]", "[RESUME]"]

        # Validation
        if not self.MONGO_URI:
            raise ValueError("❌ MONGO_URI mancante. Inseriscilo in .env")


# Istanza globale configurazione
config = Config()
