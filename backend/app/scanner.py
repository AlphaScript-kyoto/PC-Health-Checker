from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from app import db
from app.collectors import collect_all
from app.engine import evaluate
from app.notify import notify
from app.recommend import build_recommendations

_lock = threading.Lock()
_last_scan: dict[str, Any] | None = None
_on_status_change: Callable[[str], None] | None = None


def set_status_callback(cb: Callable[[str], None] | None) -> None:
    global _on_status_change
    _on_status_change = cb


def get_last_scan() -> dict[str, Any] | None:
    return _last_scan


def run_scan(notify_alerts: bool = True) -> dict[str, Any]:
    global _last_scan
    with _lock:
        settings = db.get_settings()
        raw = collect_all()
        changes = db.upsert_known_disks(raw.get("disks") or [])
        evaluated = evaluate(raw, settings)

        for disk in changes.get("appeared") or []:
            evaluated["alerts"].append(
                {
                    "level": "Watch",
                    "title": "新しいディスクを検出",
                    "message": f"{disk.get('model')} (id={disk.get('device_id')})",
                    "device_id": disk.get("device_id"),
                    "kind": "change",
                }
            )
            if evaluated["overall_status"] == "OK":
                evaluated["overall_status"] = "Watch"

        for disk in changes.get("disappeared") or []:
            evaluated["alerts"].append(
                {
                    "level": "Watch",
                    "title": "ディスクが消えました",
                    "message": f"{disk.get('model')} (id={disk.get('device_id')})",
                    "device_id": disk.get("device_id"),
                    "kind": "change",
                }
            )
            if evaluated["overall_status"] == "OK":
                evaluated["overall_status"] = "Watch"

        recommendations = build_recommendations(evaluated, settings)
        payload = {
            **evaluated,
            "recommendations": recommendations,
            "settings": settings,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

        db.save_snapshot(evaluated["overall_status"], payload)
        db.save_disk_history(evaluated.get("disks") or [])

        recent = db.get_recent_alerts(limit=40)
        recent_keys = {
            (a.get("level"), a.get("title"), a.get("message")) for a in recent[:15]
        }

        for alert in evaluated.get("alerts") or []:
            key = (alert["level"], alert["title"], alert["message"])
            should_notify = (
                notify_alerts
                and settings.get("notify_enabled", True)
                and alert.get("level") in ("ReplaceSoon", "Critical", "Watch")
                and key not in recent_keys
            )
            ok = False
            if should_notify:
                ok = notify(alert["title"], alert["message"])
            # Always record new alert rows when content is new; skip pure duplicates
            if key not in recent_keys:
                db.add_alert(
                    alert["level"],
                    alert["title"],
                    alert["message"],
                    alert.get("device_id"),
                    notified=ok,
                )

        _last_scan = payload
        if _on_status_change:
            try:
                _on_status_change(evaluated["overall_status"])
            except Exception:
                pass
        return payload
