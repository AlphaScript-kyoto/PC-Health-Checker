from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _app_dir() -> Path:
    if _is_frozen():
        return Path(sys._MEIPASS) / "app"
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    if _is_frozen():
        base = Path.home() / "AppData" / "Local" / "PCHealthChecker"
        return base / "data"
    return _app_dir() / "data"


APP_NAME = "パソコンちぇっ君"
APP_NAME_EN = "Pasokon Chekkun"
APP_VERSION = "0.1.0"
APP_AUTHOR = "Alpha Script"
APP_HOMEPAGE = "https://alphascript-kyoto.github.io/as-homepage/"
APP_CONTACT = ""
APP_REPO = "https://github.com/AlphaScript-kyoto/PC-Health-Checker"

HOST = "127.0.0.1"
PORT = 8787
BASE_URL = f"http://{HOST}:{PORT}"

APP_DIR = _app_dir()
# backend/ （app パッケージの親）
ROOT_DIR = APP_DIR.parent if not _is_frozen() else Path(sys.executable).resolve().parent
# リポジトリルート（backend の親）
PROJECT_ROOT = ROOT_DIR.parent if ROOT_DIR.name == "backend" else ROOT_DIR

DATA_DIR = _data_dir()
UI_DIR = APP_DIR / "ui"
DB_PATH = DATA_DIR / "health.db"

SCAN_INTERVAL_SEC = 60

DEFAULT_SETTINGS = {
    "notify_enabled": True,
    "capacity_warn_pct": 10.0,
    "capacity_critical_pct": 5.0,
    "budget_max_yen": 30000,
    "prefer_new_used": "either",
    "prefer_media": "ssd",
    "capacity_preference_tb": 2.0,
    "priority": "speed",
    "daily_scan_time": "09:00",
    "startup_enabled": False,
}

OLD_DRIVE_HINTS = {
    "ST3160815AS": "2007-2008世代のHDD。故障リスクが高めです。",
    "ST3160815": "2007-2008世代のHDD。故障リスクが高めです。",
}
