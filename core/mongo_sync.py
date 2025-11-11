"""Sincronizzazione con MongoDB"""

import pymongo
from typing import List, Tuple, Dict
from config.settings import Config


class MongoSyncManager:
    """Gestisce la sincronizzazione con MongoDB"""

    def __init__(self, config: Config):
        self.config = config
        self.client = pymongo.MongoClient(config.MONGO_URI)
        self.db = self.client[config.MONGO_DB]
        self._init_indexes()

    def _init_indexes(self):
        """Crea gli indici necessari"""
        self.db[self.config.PROCESS_WINDOW_TABLE].create_index(
            [("device_id", 1), ("process", 1), ("window_title", 1)], unique=True
        )
        self.db[self.config.DEVICES_TABLE].create_index([("device_id", 1)], unique=True)

    def sync_device(self):
        """Sincronizza le informazioni del device"""
        try:
            self.db[self.config.DEVICES_TABLE].update_one(
                {"device_id": self.config.DEVICE_ID},
                {
                    "$setOnInsert": {
                        "device_id": self.config.DEVICE_ID,
                        "user_id": None,
                    }
                },
                upsert=True,
            )
            print(f"[DEVICE SYNC] {self.config.DEVICE_ID}")
        except Exception as e:
            print(f"[DEVICE SYNC ERROR] {e}")

    def sync_activities(self, records: List[Tuple]):
        """Sincronizza i record di attività"""
        if not records:
            return

        docs = [
            {
                "timestamp": r[1],
                "process": r[2],
                "window_title": r[3],
                "cpu_percent": r[4],
                "device_id": r[6],
                "username": r[7],
                "system": self.config.SYSTEM,
                "device_name": self.config.DEVICE_NAME,
            }
            for r in records
        ]

        # Inserisci attività
        self.db[self.config.ACTIVITY_LOGS_TABLE].insert_many(docs)

        # Aggiorna tabella processi
        for doc in docs:
            try:
                self.db[self.config.PROCESS_WINDOW_TABLE].update_one(
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
                            "level": 5,
                            "active": True,
                        }
                    },
                    upsert=True,
                )
            except Exception as e:
                print(f"[PROCESS UPSERT ERROR] {e}")

        print(f"[SYNC] {len(docs)} record sincronizzati")

    def get_process_windows(self) -> List[Dict]:
        """Recupera i processi/finestre dal database"""
        return list(
            self.db[self.config.PROCESS_WINDOW_TABLE].find(
                {
                    "device_id": self.config.DEVICE_ID,
                    "process": {"$not": {"$regex": r"\[PAUSE\]|\[RESUME\]|unknown"}},
                },
                {"_id": 1, "process": 1, "window_title": 1, "level": 1},
            )
        )

    def update_level(self, voce_id, level: int):
        """Aggiorna il livello di attenzione"""
        try:
            result = self.db[self.config.PROCESS_WINDOW_TABLE].update_one(
                {"_id": voce_id}, {"$set": {"level": level}}
            )
            if result.modified_count:
                print(f"✅ Aggiornato {voce_id} → level {level}")
        except Exception as e:
            print(f"[SET LEVEL ERROR] {e}")
