"""Interfaccia grafica Tkinter"""

import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict
from concurrent.futures import ThreadPoolExecutor

from core.mongo_sync import MongoSyncManager
from core.window_detector import WindowDetector
from config.settings import Config


class GUIManager:
    """Gestisce l'interfaccia grafica Tkinter"""

    def __init__(self, config: Config, mongo_manager: MongoSyncManager):
        self.config = config
        self.mongo_manager = mongo_manager
        self.indicators = {}
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._last_timer = {}
        self.root = None

    def create_window(self):
        """Crea la finestra principale"""
        self.root = tk.Tk()
        self.root.title("Livelli di attenzione")
        self.root.geometry("640x480")
        self.root.configure(bg="white")

        # Intestazioni
        tk.Label(
            self.root,
            text="Finestra",
            bg="white",
            fg="black",
            font=("Arial", 10, "bold"),
        ).grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        tk.Label(
            self.root,
            text="Livello",
            bg="white",
            fg="black",
            font=("Arial", 10, "bold"),
        ).grid(row=0, column=2, padx=10, pady=5, sticky="e")

        # Carica applicazioni
        apps = self.mongo_manager.get_process_windows()
        for i, app in enumerate(apps, start=1):
            if app["process"] not in self.config.PROCESS_BLACKLIST:
                self._add_process_row(i, app)

        # Avvia aggiornamento indicatori
        self._update_active_indicator()

        return self.root

    def _add_process_row(self, row: int, app: Dict):
        """Aggiunge una riga per un processo"""
        level = app.get("level", 5)

        # Indicatore stato
        indicator = tk.Label(
            self.root, text="●", fg="gray", bg="white", font=("Arial", 12)
        )
        indicator.grid(row=row, column=0, padx=5, pady=3, sticky="w")

        # Nome applicazione
        label = tk.Label(
            self.root,
            text=f"{app['process']} ({app['window_title']})",
            bg="white",
            fg="black",
            font=("Arial", 10),
        )
        label.grid(row=row, column=1, sticky="w", padx=5, pady=3)

        # Slider livello
        scale = ttk.Scale(self.root, from_=1, to=10, orient="horizontal", length=150)
        scale.set(level)
        scale.grid(row=row, column=2, padx=10, pady=3)
        scale.bind(
            "<ButtonRelease-1>", lambda e, aid=app["_id"]: self._on_level_change(e, aid)
        )

        self.indicators[app["_id"]] = {
            "indicator": indicator,
            "label": label,
            "process": app["process"],
            "window_title": app["window_title"],
        }

    def _on_level_change(self, event, app_id):
        """Callback per cambio livello"""
        level = int(float(event.widget.get()))

        if app_id in self._last_timer:
            self._last_timer[app_id].cancel()

        self._last_timer[app_id] = threading.Timer(
            0.3, lambda: self.mongo_manager.update_level(app_id, level)
        )
        self._last_timer[app_id].start()

    def _update_active_indicator(self):
        """Aggiorna gli indicatori per l'app attiva"""
        try:
            active_process, active_title = WindowDetector.get_active_window()

            for data in self.indicators.values():
                is_active = (
                    data["process"] == active_process
                    and data["window_title"] == active_title
                )

                if is_active:
                    data["indicator"].config(fg="green")
                    data["label"].config(fg="green", font=("Arial", 10, "bold"))
                else:
                    data["indicator"].config(fg="gray")
                    data["label"].config(fg="black", font=("Arial", 10))
        except Exception as e:
            print(f"[UI UPDATE ERROR] {e}")
        finally:
            if self.root:
                self.root.after(1000, self._update_active_indicator)

    def run(self):
        """Avvia la GUI"""
        if self.root:
            self.root.mainloop()
