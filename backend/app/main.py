from __future__ import annotations

import argparse
import logging
import os
import socket
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
from app.config import APP_NAME, BASE_URL, DATA_DIR, HOST, PORT, SCAN_INTERVAL_SEC
from app.net_bind import port_is_free
from app.scanner import run_scan, scan_outcome, set_status_callback
from app.schedule import (
    DAILY_RETRY_SEC,
    daily_is_due,
    daily_outcome_covers_today,
    startup_covers_daily,
    startup_should_delay_daily,
)

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


def _pid_path() -> Path:
    return DATA_DIR / "backend.pid"


def write_backend_pid() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _pid_path().write_text(str(os.getpid()), encoding="utf-8")


def remove_backend_pid() -> None:
    path = _pid_path()
    try:
        if path.is_file() and path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            path.unlink()
    except OSError:
        pass


def _wait_until_accepting(timeout_sec: float) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _run_scan_jobs(label: str, *, announce: bool) -> str:
    """ok / cancelled / failed。失敗や中断を「今日は済んだ」にしない。"""
    from app.notify import notify
    from app.scanner import get_last_scan, get_scan_progress, start_scan

    log.info("%s starting…", label)
    started = start_scan(notify_alerts=True)
    if not started.get("started"):
        if started.get("message") == "already running":
            log.info("%s: another scan is already running — waiting for it", label)
        else:
            log.warning("%s: could not start (%s)", label, started)
            return "failed"

    deadline = time.time() + 60 * 45
    while time.time() < deadline and not _scheduler_stop.is_set():
        progress = get_scan_progress()
        if not progress.get("running"):
            break
        time.sleep(1.0)
    else:
        if not _scheduler_stop.is_set():
            log.warning("%s: timed out waiting for scan to finish", label)
            return "failed"

    outcome = scan_outcome()
    last = None
    try:
        last = get_last_scan()
    except Exception:
        pass
    log.info("%s finished: outcome=%s status=%s", label, outcome, (last or {}).get("overall_status"))
    if outcome != "ok":
        return outcome

    try:
        from app.price_tracker import maybe_weekly_price_job

        maybe_weekly_price_job()
    except Exception:
        log.exception("Weekly price job failed")

    if announce:
        try:
            notify(APP_NAME, f"{label}が完了しました", open_dashboard=False)
        except Exception:
            log.exception("Daily scan notify failed")
    return "ok"


def _scheduler_loop() -> None:
    """待ち受けのあと起動時スキャンを行い、成功したときだけ定刻分を済ませる。"""
    from datetime import datetime, timedelta

    startup_outcome = "failed"
    try:
        startup_outcome = _run_scan_jobs("起動時スキャン", announce=False)
    except Exception:
        log.exception("Startup scan failed")
        startup_outcome = "failed"

    last_daily_scan_date = None
    failed_daily_at: float | None = None
    try:
        settings = db.get_settings()
        hour, minute = _parse_daily_scan_time(settings.get("daily_scan_time"))
        now = datetime.now()
        target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        past_slot = now >= target_today
        if startup_covers_daily(
            startup_succeeded=startup_outcome == "ok",
            now_past_slot=past_slot,
        ):
            last_daily_scan_date = now.date()
            log.info(
                "起動時スキャンが成功したため、本日 %02d:%02d の定刻スキャンは見送ります",
                hour,
                minute,
            )
        elif startup_should_delay_daily(startup_outcome):
            # 利用者が止めた直後に、定刻分としてもう一度歩き始めない
            failed_daily_at = time.time()
            log.info(
                "起動時スキャンは中断されたため、定刻スキャンは約%d分待ってから判断します",
                DAILY_RETRY_SEC // 60,
            )
        elif past_slot:
            log.info(
                "起動時スキャンでは本日分を賄えていないため、定刻スキャンを実行します (%02d:%02d)",
                hour,
                minute,
            )
        else:
            log.info("Next daily scan today at %02d:%02d", hour, minute)
    except Exception:
        log.exception("Scheduler init failed")

    while not _scheduler_stop.is_set():
        try:
            settings = db.get_settings()
            hour, minute = _parse_daily_scan_time(settings.get("daily_scan_time"))
            now = datetime.now()
            today = now.date()
            target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            past_slot = now >= target_today
            covered = last_daily_scan_date == today
            since_failure = None if failed_daily_at is None else time.time() - failed_daily_at
            if daily_is_due(
                now_past_slot=past_slot,
                covered_today=covered,
                seconds_since_failure=since_failure,
                retry_sec=DAILY_RETRY_SEC,
            ):
                outcome = _run_scan_jobs("毎日の自動スキャン", announce=True)
                if daily_outcome_covers_today(outcome):
                    last_daily_scan_date = today
                    failed_daily_at = None
                    if outcome == "cancelled":
                        log.info("毎日の自動スキャンは中断されたため、本日分はここまでにします")
                else:
                    failed_daily_at = time.time()
                    log.warning("毎日の自動スキャンに失敗したため、本日分としては数えません")

            if last_daily_scan_date == today:
                next_target = target_today + timedelta(days=1)
            else:
                next_target = target_today
            wait = (next_target - datetime.now()).total_seconds()
            # 設定変更を反映するため最大30秒で起床
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
    try:
        server.run()
    finally:
        # ポートを取れなかったのにプロセスとスケジューラだけ残さない
        if not getattr(server, "started", False) and not _scheduler_stop.is_set():
            log.error(
                "ポート %s を使用できません。古いバックエンドが残っている可能性があります。終了します。",
                PORT,
            )
            remove_backend_pid()
            os._exit(1)


def main(headless: bool = False) -> None:
    global _icon

    db.init_db()
    try:
        _main_after_pid(headless)
    finally:
        _scheduler_stop.set()
        remove_backend_pid()


def _main_after_pid(headless: bool) -> None:
    global _icon
    set_status_callback(_update_tray_status)

    if not port_is_free(HOST, PORT):
        log.error(
            "ポート %s はすでに使用中です。待ち受けできないため終了します。",
            PORT,
        )
        sys.exit(1)

    server_thread = threading.Thread(target=_run_server, daemon=True, name="pchc-api")
    server_thread.start()
    if not _wait_until_accepting(30):
        log.error("ポート %s で待ち受けを開始できなかったため終了します。", PORT)
        sys.exit(1)

    # 待ち受けに成功してから PID を書く。失敗時に、動いている古いバックエンドの PID を消さない。
    write_backend_pid()
    # 待ち受けできてから起動時スキャンと定刻スキャンを始める
    sched = threading.Thread(target=_scheduler_loop, daemon=True, name="pchc-scheduler")
    sched.start()

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
