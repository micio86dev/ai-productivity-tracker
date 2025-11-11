"""Logica di tracking attività utente"""

import os
import re
import time
import psutil
from pynput import mouse, keyboard
from core.database import DatabaseManager
from core.mongo_sync import MongoSyncManager
from core.window_detector import WindowDetector
from config.settings import Config


class ActivityTracker:
    """Traccia l'attività dell'utente"""

    def __init__(
        self,
        config: Config,
        db_manager: DatabaseManager,
        mongo_manager: MongoSyncManager,
    ):
        self.config = config
        self.db_manager = db_manager
        self.mongo_manager = mongo_manager
        self._last_input_time = time.time()
        self._paused = False
        self._last_window = None
        self._last_process = None
        self._init_input_listeners()

    def _init_input_listeners(self):
        """Inizializza i listener per mouse e tastiera"""
        mouse.Listener(
            on_move=self._on_input_activity,
            on_click=self._on_input_activity,
            on_scroll=self._on_input_activity,
        ).start()
        keyboard.Listener(on_press=self._on_input_activity).start()

    def _on_input_activity(self, *args, **kwargs):
        """Callback per attività input"""
        self._last_input_time = time.time()

    def is_user_active(self) -> bool:
        """Verifica se l'utente è attivo"""
        elapsed = time.time() - self._last_input_time
        return elapsed < self.config.INACTIVITY_THRESHOLD

    def track_event(self, process_name: str, window_title: str):
        """Registra un evento di attività"""
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            self.db_manager.insert_activity(
                process_name,
                window_title,
                cpu_percent,
                self.config.DEVICE_ID,
                self.config.USERNAME,
            )
            print(f"[TRACK] {process_name} - {window_title}")
        except Exception as e:
            print(f"[TRACK ERROR] {e}")

    def tracking_loop(self):
        """Loop principale di tracking"""

        while True:
            try:
                # Gestione pausa per inattività
                if not self.is_user_active():
                    if not self._paused:
                        print("[PAUSE] ⏸️")
                        self._paused = True
                        self.track_event("[PAUSE]", "[PAUSE]")
                    time.sleep(self.config.TRACKING_INTERVAL)
                    continue
                elif self._paused:
                    print("[RESUME] ✅")
                    self._paused = False
                    self.track_event("[RESUME]", "[RESUME]")

                # Rileva finestra attiva
                process_name, window_title = WindowDetector.get_active_window()
                process_name = os.path.basename(process_name)
                process_name = re.sub(r"\.app$", "", process_name, flags=re.IGNORECASE)

                # Ignora processi blacklist
                if process_name in self.config.PROCESS_BLACKLIST:
                    time.sleep(self.config.TRACKING_INTERVAL)
                    continue

                # Traccia solo se cambiato
                if (
                    window_title != self._last_window
                    or process_name != self._last_process
                ):
                    self.track_event(process_name, window_title)
                    self._last_window = window_title
                    self._last_process = process_name

                time.sleep(self.config.TRACKING_INTERVAL)

            except Exception as e:
                print(f"[TRACKING ERROR] {e}")
                time.sleep(self.config.TRACKING_INTERVAL)

    def sync_loop(self):
        """Loop di sincronizzazione periodica"""
        print("[SYNC] Loop avviato...")

        while True:
            time.sleep(self.config.SYNC_INTERVAL)
            try:
                records = self.db_manager.get_unsynced_records()
                if records:
                    self.mongo_manager.sync_activities(records)
                    self.db_manager.mark_as_synced()
            except Exception as e:
                print(f"[SYNC ERROR] {e}")
