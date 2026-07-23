from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from app import db
from app.collectors.capacity import collect_volumes
from app.collectors.disks import collect_disks, is_elevated, smartctl_available
from app.collectors.inventory import collect_inventory
from app.engine import evaluate
from app.notify import notify
from app.recommend import build_recommendations

_lock = threading.Lock()
_scan_thread: threading.Thread | None = None
_last_scan: dict[str, Any] | None = None
_on_status_change: Callable[[str], None] | None = None
_progress: dict[str, Any] = {
    "running": False,
    "phase": "idle",
    "percent": 0,
    "message": "",
    "error": None,
    "started_at": None,
    "finished_at": None,
}
_progress_lock = threading.Lock()


def set_status_callback(cb: Callable[[str], None] | None) -> None:
    global _on_status_change
    _on_status_change = cb


def get_last_scan() -> dict[str, Any] | None:
    return _last_scan


def get_scan_progress() -> dict[str, Any]:
    with _progress_lock:
        return dict(_progress)


def _set_progress(
    *,
    running: bool | None = None,
    phase: str | None = None,
    percent: int | None = None,
    message: str | None = None,
    error: str | None = None,
    finished: bool = False,
) -> None:
    with _progress_lock:
        if running is not None:
            _progress["running"] = running
        if phase is not None:
            _progress["phase"] = phase
        if percent is not None:
            _progress["percent"] = max(0, min(100, int(percent)))
        if message is not None:
            _progress["message"] = message
        if error is not None:
            _progress["error"] = error
        if running is True and _progress.get("started_at") is None:
            _progress["started_at"] = datetime.now(timezone.utc).isoformat()
            _progress["finished_at"] = None
            _progress["error"] = None
        if finished:
            _progress["running"] = False
            _progress["finished_at"] = datetime.now(timezone.utc).isoformat()
            _progress["percent"] = 100 if error is None else _progress.get("percent", 0)


def _collect_all_with_progress() -> dict[str, Any]:
    _set_progress(phase="inventory", percent=8, message="PC情報（CPU / メモリ / OS など）を取得中…")
    inventory = collect_inventory()

    _set_progress(phase="disks", percent=35, message="ディスク情報・SMART を取得中…")
    disks = collect_disks()

    _set_progress(phase="volumes", percent=60, message="ドライブの空き容量を確認中…")
    volumes = collect_volumes()

    elevated = is_elevated()

    vol_by_disk: dict[str, list] = {}
    for v in volumes:
        for did in v.get("physical_disk_ids") or []:
            vol_by_disk.setdefault(did, []).append(v)

    for d in disks:
        related = vol_by_disk.get(d["device_id"], [])
        if related:
            worst = min(related, key=lambda x: x.get("free_pct", 100))
            d["free_pct"] = worst.get("free_pct")
            d["volumes"] = [
                {
                    "letter": x.get("letter"),
                    "free_pct": x.get("free_pct"),
                    "free_gb": x.get("free_gb"),
                    "size_gb": x.get("size_gb"),
                }
                for x in related
            ]
        else:
            d["free_pct"] = None
            d["volumes"] = []

    return {
        "inventory": inventory,
        "disks": disks,
        "volumes": volumes,
        "elevated": elevated,
        "smartctl_available": smartctl_available(),
    }


def run_scan(notify_alerts: bool = True) -> dict[str, Any]:
    global _last_scan
    with _lock:
        _set_progress(
            running=True,
            phase="start",
            percent=2,
            message="スキャンを開始しました…",
        )
        try:
            settings = db.get_settings()
            raw = _collect_all_with_progress()

            _set_progress(phase="evaluate", percent=75, message="リスク判定と提案を作成中…")
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

            _set_progress(phase="save", percent=90, message="結果を保存中…")
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

            _set_progress(
                phase="done",
                percent=100,
                message="スキャンが完了しました",
                finished=True,
            )
            return payload
        except Exception as exc:
            _set_progress(
                phase="error",
                message="スキャンに失敗しました",
                error=str(exc),
                finished=True,
            )
            raise


def start_scan(notify_alerts: bool = True) -> dict[str, Any]:
    """バックグラウンドで健康診断スキャンを開始する。"""
    global _scan_thread
    with _progress_lock:
        if _progress.get("running"):
            return {"ok": True, "started": False, "message": "already running"}
        _progress["running"] = True
        _progress["phase"] = "queued"
        _progress["percent"] = 1
        _progress["message"] = "スキャンを準備中…"
        _progress["error"] = None
        _progress["started_at"] = datetime.now(timezone.utc).isoformat()
        _progress["finished_at"] = None

    def _worker() -> None:
        try:
            run_scan(notify_alerts=notify_alerts)
        except Exception:
            # progress already marked error in run_scan
            pass

    _scan_thread = threading.Thread(target=_worker, name="pchc-health-scan", daemon=True)
    _scan_thread.start()
    return {"ok": True, "started": True}
