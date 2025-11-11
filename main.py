#!/usr/bin/env python3
"""
Activity Tracker - Entry point principale
"""
import threading
from config.settings import config
from core.database import DatabaseManager
from core.mongo_sync import MongoSyncManager
from core.tracker import ActivityTracker
from gui.manager import GUIManager


def main():
    """Entry point principale"""
    print("=" * 60)
    print("🔍 ACTIVITY TRACKER")
    print("=" * 60)

    # Inizializza componenti
    db_manager = DatabaseManager(config.DB_PATH)
    mongo_manager = MongoSyncManager(config)
    tracker = ActivityTracker(config, db_manager, mongo_manager)
    gui_manager = GUIManager(config, mongo_manager)

    # Sincronizza device
    mongo_manager.sync_device()

    # Avvia thread background
    threading.Thread(target=tracker.tracking_loop, daemon=True).start()
    threading.Thread(target=tracker.sync_loop, daemon=True).start()

    print("[INFO] Tracking avviato. Premi Ctrl+C per fermare.")
    print("=" * 60)

    # Avvia GUI (blocking)
    gui_manager.create_window()
    gui_manager.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[EXIT] Arresto richiesto dall'utente.")
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        raise
