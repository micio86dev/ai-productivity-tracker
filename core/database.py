"""Gestione database SQLite locale"""

import sqlite3
from typing import List, Tuple
from datetime import datetime, timezone


class DatabaseManager:
    """Gestisce le operazioni sul database SQLite locale"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Inizializza il database con le tabelle necessarie"""
        conn = sqlite3.connect(self.db_path)
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
        conn.close()

    def insert_activity(
        self,
        process: str,
        window_title: str,
        cpu_percent: float,
        device_id: str,
        username: str,
    ):
        """Inserisce un nuovo record di attività"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            cur.execute(
                """
                INSERT INTO activity (timestamp, process, window_title, 
                                    cpu_percent, synced, device_id, username)
                VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
                (timestamp, process, window_title, cpu_percent, device_id, username),
            )
            conn.commit()
        finally:
            conn.close()

    def get_unsynced_records(self) -> List[Tuple]:
        """Recupera tutti i record non sincronizzati"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            return cur.execute("SELECT * FROM activity WHERE synced = 0").fetchall()
        finally:
            conn.close()

    def mark_as_synced(self):
        """Marca tutti i record come sincronizzati"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute("UPDATE activity SET synced = 1 WHERE synced = 0")
            conn.commit()
        finally:
            conn.close()
