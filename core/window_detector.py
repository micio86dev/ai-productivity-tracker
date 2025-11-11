"""Rilevamento finestra attiva cross-platform"""

import os
import re
import platform
import subprocess
from typing import Tuple, Optional
import psutil


class WindowDetector:
    """Rileva la finestra attiva in modo cross-platform"""

    @staticmethod
    def get_active_window() -> Tuple[str, str]:
        """Ritorna (process_name, window_title)"""
        system = platform.system()

        if system == "Darwin":
            return WindowDetector._get_macos_window()
        elif system == "Windows":
            return WindowDetector._get_windows_window()
        elif system == "Linux":
            return WindowDetector._get_linux_window()
        else:
            return "unknown", "Unknown"

    @staticmethod
    def _get_macos_window() -> Tuple[str, str]:
        """Rileva finestra attiva su macOS"""
        app_name, window_title = "unknown", "Unknown"

        try:
            script = """
                tell application "System Events"
                    set frontApp to name of (first application process whose frontmost is true)
                    return frontApp
                end tell
            """
            result = subprocess.check_output(["osascript", "-e", script])
            app_name = result.decode("utf-8").strip()
            window_title = app_name

            # Gestione browser
            browsers = ["Google Chrome", "Safari", "Firefox", "Brave Browser"]
            if app_name in browsers:
                url = WindowDetector._get_browser_url(app_name)
                if url:
                    match = re.search(r"https?://([a-zA-Z0-9.-]+)", url)
                    window_title = match.group(1) if match else url
        except Exception as e:
            print(f"[WARN] macOS detection failed: {e}")

        return app_name, window_title

    @staticmethod
    def _get_browser_url(browser_name: str) -> Optional[str]:
        """Estrae l'URL dal browser su macOS"""
        scripts = {
            "Google Chrome": 'tell application "Google Chrome" to return URL of '
            "active tab of front window",
            "Safari": 'tell application "Safari" to return URL of '
            "current tab of front window",
            "Firefox": 'tell application "Firefox" to return URL of '
            "current tab of front window",
            "Brave Browser": 'tell application "Brave Browser" to return URL of '
            "active tab of front window",
        }

        try:
            url = (
                subprocess.check_output(["osascript", "-e", scripts[browser_name]])
                .decode()
                .strip()
            )
            return url if url else None
        except Exception:
            return None

    @staticmethod
    def _get_windows_window() -> Tuple[str, str]:
        """Rileva finestra attiva su Windows"""
        try:
            import win32gui  # type: ignore
            import win32process  # type: ignore

            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            window_title = win32gui.GetWindowText(hwnd)

            match = re.search(r"https?://([a-zA-Z0-9.-]+)", window_title)
            if match:
                window_title = match.group(1)

            return proc.name(), window_title or proc.name()
        except Exception as e:
            print(f"[WARN] Windows detection failed: {e}")
            return "unknown", "Unknown"

    @staticmethod
    def _get_linux_window() -> Tuple[str, str]:
        """Rileva finestra attiva su Linux"""
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

            match = re.search(r"https?://([a-zA-Z0-9.-]+)", title)
            if match:
                title = match.group(1)

            return "unknown", title
        except Exception:
            return "unknown", "Unknown"
