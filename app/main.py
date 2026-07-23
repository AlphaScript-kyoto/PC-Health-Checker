from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path when launched as script
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from PIL import Image, ImageDraw

from app import db
from app.api import app as fastapi_app, mount_ui
from app.config import APP_NAME, HOST, PORT, BASE_URL, SCAN_INTERVAL_SEC
from app.scanner import run_scan, set_status_callback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("pc-health")

_scheduler_stop = threading.Event()
_current_status = "Unknown"
_icon = None


def _make_icon_image(status: str = "OK") -> Image.Image:
    colors = {
        "OK": (62, 207, 142, 255),
        "Watch": (230, 184, 77, 255),
        "ReplaceSoon": (240, 138, 75, 255),
        "Critical": (239, 95, 95, 255),
        "Unknown": (143, 163, 181, 255),
    }
    color = colors.get(status, colors["Unknown"])
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(30, 42, 54, 255))
    draw.ellipse((14, 14, 50, 50), fill=color)
    return img


def open_dashboard(icon=None, item=None) -> None:
    webbrowser.open(BASE_URL)


def trigger_scan(icon=None, item=None) -> None:
    def _run():
        try:
            result = run_scan(notify_alerts=True)
            log.info("Manual scan done: %s", result.get("overall_status"))
        except Exception:
            log.exception("Manual scan failed")

    threading.Thread(target=_run, daemon=True).start()


def quit_app(icon=None, item=None) -> None:
    _scheduler_stop.set()
    if icon is not None:
        icon.stop()


def _update_tray_status(status: str) -> None:
    global _current_status, _icon
    _current_status = status
    if _icon is not None:
        try:
            _icon.icon = _make_icon_image(status)
            _icon.title = f"{APP_NAME}: {status}"
        except Exception:
            pass


def _parse_daily_scan_time(value: Any) -> tuple[int, int]:
    """Return (hour, minute) from 'HH:MM'. Falls back to 09:00."""
    text = str(value or "09:00").strip()
    try:
        hour_s, minute_s = text.split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except Exception:
        pass
    return 9, 0


def _run_scan_jobs(label: str) -> None:
    result = run_scan(notify_alerts=True)
    log.info("%s: %s", label, result.get("overall_status"))
    try:
        from app.price_tracker import maybe_weekly_price_job

        maybe_weekly_price_job()
    except Exception:
        log.exception("Weekly price job failed")


def _scheduler_loop() -> None:
    """Scan once at startup, then once each day at the configured local time."""
    from datetime import datetime, timedelta

    time.sleep(2)
    last_daily_scan_date = None
    try:
        _run_scan_jobs("Startup scan")
        settings = db.get_settings()
        hour, minute = _parse_daily_scan_time(settings.get("daily_scan_time"))
        now = datetime.now()
        target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Startup already covered today if the scheduled time has passed.
        if now >= target_today:
            last_daily_scan_date = now.date()
    except Exception:
        log.exception("Startup scan failed")

    while not _scheduler_stop.is_set():
        try:
            settings = db.get_settings()
            hour, minute = _parse_daily_scan_time(settings.get("daily_scan_time"))
            now = datetime.now()
            today = now.date()
            target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if now >= target_today and last_daily_scan_date != today:
                _run_scan_jobs("Daily scheduled scan")
                last_daily_scan_date = today

            if last_daily_scan_date == today:
                next_target = target_today + timedelta(days=1)
            else:
                next_target = target_today
            wait = (next_target - datetime.now()).total_seconds()
            # Wake often so setting changes apply without restart.
            wait = min(30.0, max(1.0, wait if wait > 0 else 1.0))
        except Exception:
            log.exception("Scheduled scan failed")
            wait = float(SCAN_INTERVAL_SEC)
        _scheduler_stop.wait(wait)


def _run_server() -> None:
    mount_ui(fastapi_app)
    config = uvicorn.Config(
        fastapi_app,
        host=HOST,
        port=PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def main(headless: bool = False) -> None:
    global _icon

    db.init_db()
    set_status_callback(_update_tray_status)

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    sched = threading.Thread(target=_scheduler_loop, daemon=True)
    sched.start()

    time.sleep(0.8)
    log.info("%s listening at %s (headless=%s)", APP_NAME, BASE_URL, headless)

    if headless:
        try:
            while not _scheduler_stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            _scheduler_stop.set()
        return

    try:
        import pystray
        from pystray import MenuItem as Item

        menu = pystray.Menu(
            Item("ダッシュボードを開く", open_dashboard, default=True),
            Item("今すぐスキャン", trigger_scan),
            Item("終了", quit_app),
        )
        _icon = pystray.Icon(
            APP_NAME,
            _make_icon_image("Unknown"),
            f"{APP_NAME}: starting",
            menu,
        )
        _icon.run()
    except Exception:
        log.exception("Tray unavailable — running headless. Open %s", BASE_URL)
        try:
            webbrowser.open(BASE_URL)
        except Exception:
            pass
        try:
            while not _scheduler_stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            _scheduler_stop.set()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument(
        "--headless",
        action="store_true",
        help="API + scheduler only (for Electron shell)",
    )
    args = parser.parse_args()
    main(headless=args.headless)
