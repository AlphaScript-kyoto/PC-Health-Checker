from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _app_dir() -> Path:
    if _is_frozen():
        # PyInstaller extracts sources under _MEIPASS/app
        return Path(sys._MEIPASS) / "app"
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    if _is_frozen():
        base = Path.home() / "AppData" / "Local" / "PCHealth"
        return base / "data"
    return _app_dir() / "data"


APP_NAME = "PC Health"
APP_VERSION = "0.2.4"
APP_AUTHOR = "Alpha Script"
APP_HOMEPAGE = "https://alphascript-kyoto.github.io/as-homepage/"
APP_CONTACT = ""

HOST = "127.0.0.1"
PORT = 8787
BASE_URL = f"http://{HOST}:{PORT}"

APP_DIR = _app_dir()
ROOT_DIR = APP_DIR.parent if not _is_frozen() else Path(sys.executable).resolve().parent
DATA_DIR = _data_dir()
UI_DIR = APP_DIR / "ui"
DB_PATH = DATA_DIR / "health.db"

# Fallback wait if scheduler math fails (seconds)
SCAN_INTERVAL_SEC = 60

# Default thresholds (percent free space)
DEFAULT_SETTINGS = {
    "notify_enabled": True,
    "capacity_warn_pct": 10.0,
    "capacity_critical_pct": 5.0,
    "budget_max_yen": 30000,
    "prefer_new_used": "either",  # new | used | either
    "prefer_media": "ssd",  # ssd | hdd | either
    "capacity_preference_tb": 2.0,
    "priority": "speed",  # speed | quiet | capacity | price
    "daily_scan_time": "09:00",  # local HH:MM — scan once at app start, then daily at this time
    "startup_enabled": False,
}

# Known-old drive models (rough age risk hints)
OLD_DRIVE_HINTS = {
    "ST3160815AS": "2007-2008世代のHDD。故障リスクが高めです。",
    "ST3160815": "2007-2008世代のHDD。故障リスクが高めです。",
}
