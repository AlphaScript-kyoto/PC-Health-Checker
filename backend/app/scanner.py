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
_map_thread: threading.Thread | None = None
_last_scan: dict[str, Any] | None = None
_on_status_change: Callable[[str], None] | None = None

_progress_lock = threading.Lock()
_progress: dict[str, Any] = {
    "running": False,
    "phase": "idle",
    "percent": 0,
    "message": "",
    "error": None,
    "started_at": None,
    "finished_at": None,
    "health": {
        "running": False,
        "percent": 0,
        "message": "",
        "error": None,
    },
    "mapping": {
        "running": False,
        "percent": 0,
        "message": "",
        "error": None,
        "current_drive": None,
    },
}


def set_status_callback(cb: Callable[[str], None] | None) -> None:
    global _on_status_change
    _on_status_change = cb


def get_last_scan() -> dict[str, Any] | None:
    return _last_scan


def get_scan_progress() -> dict[str, Any]:
    with _progress_lock:
        return {
            **_progress,
            "health": dict(_progress["health"]),
            "mapping": dict(_progress["mapping"]),
        }


def _recompute_overall(*, finished_error: str | None = None) -> None:
    """健康診断・マッピングの両トラックから全体進捗を合成する。"""
    health = _progress["health"]
    mapping = _progress["mapping"]
    h_pct = int(health.get("percent") or 0)
    m_pct = int(mapping.get("percent") or 0)
    # 健康診断の体感をやや重めに（SMART 取得が重いため）
    overall = int(h_pct * 0.55 + m_pct * 0.45)
    _progress["percent"] = max(0, min(100, overall))

    health_running = bool(health.get("running"))
    mapping_running = bool(mapping.get("running"))
    _progress["running"] = health_running or mapping_running

    if health_running and mapping_running:
        _progress["phase"] = "parallel"
        _progress["message"] = "健康診断と容量マップを並行処理中…"
    elif health_running:
        _progress["phase"] = health.get("phase") or "health"
        _progress["message"] = health.get("message") or "健康診断中…"
    elif mapping_running:
        _progress["phase"] = "space_map"
        _progress["message"] = mapping.get("message") or "容量マップ作成中…"
    else:
        err = finished_error or health.get("error") or mapping.get("error")
        if err:
            _progress["phase"] = "error"
            _progress["message"] = "スキャンに失敗しました"
            _progress["error"] = err
        else:
            _progress["phase"] = "done"
            _progress["message"] = "健康診断と容量マップの作成が完了しました"
            _progress["error"] = None
            _progress["percent"] = 100
        _progress["finished_at"] = datetime.now(timezone.utc).isoformat()


def _set_health_progress(
    *,
    running: bool | None = None,
    phase: str | None = None,
    percent: int | None = None,
    message: str | None = None,
    error: str | None = None,
    finished: bool = False,
) -> None:
    with _progress_lock:
        health = _progress["health"]
        if running is not None:
            health["running"] = running
        if phase is not None:
            health["phase"] = phase
        if percent is not None:
            health["percent"] = max(0, min(100, int(percent)))
        if message is not None:
            health["message"] = message
        if error is not None:
            health["error"] = error
        if finished:
            health["running"] = False
            if error is None and health.get("error") is None:
                health["percent"] = 100
                health["message"] = health.get("message") or "健康診断が完了しました"
            elif error is not None:
                health["error"] = error
                health["message"] = "健康診断に失敗しました"
        _recompute_overall(finished_error=error if finished else None)


def _set_mapping_progress(
    *,
    running: bool | None = None,
    percent: int | None = None,
    message: str | None = None,
    error: str | None = None,
    current_drive: str | None = None,
    finished: bool = False,
) -> None:
    with _progress_lock:
        mapping = _progress["mapping"]
        if running is not None:
            mapping["running"] = running
        if percent is not None:
            mapping["percent"] = max(0, min(100, int(percent)))
        if message is not None:
            mapping["message"] = message
        if error is not None:
            mapping["error"] = error
        if current_drive is not None:
            mapping["current_drive"] = current_drive
        if finished:
            mapping["running"] = False
            mapping["current_drive"] = None
            if error is None and mapping.get("error") is None:
                mapping["percent"] = 100
                mapping["message"] = mapping.get("message") or "容量マップの作成が完了しました"
            elif error is not None:
                mapping["error"] = error
                mapping["message"] = "容量マップの作成に失敗しました"
        _recompute_overall(finished_error=error if finished else None)


# 後方互換: 旧コードが _set_progress を呼んでも健康診断トラックに流す
def _set_progress(
    *,
    running: bool | None = None,
    phase: str | None = None,
    percent: int | None = None,
    message: str | None = None,
    error: str | None = None,
    finished: bool = False,
) -> None:
    _set_health_progress(
        running=running,
        phase=phase,
        percent=percent,
        message=message,
        error=error,
        finished=finished,
    )


def _collect_all_with_progress() -> dict[str, Any]:
    _set_health_progress(phase="inventory", percent=8, message="PC情報（CPU / メモリ / OS など）を取得中…")
    inventory = collect_inventory()

    _set_health_progress(phase="disks", percent=35, message="ディスク情報・SMART を取得中…")
    disks = collect_disks()

    _set_health_progress(phase="volumes", percent=60, message="ドライブの空き容量を確認中…")
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


def run_scan(notify_alerts: bool = True, *, include_maps: bool = False) -> dict[str, Any]:
    """健康診断スキャン。include_maps=True のときは従来どおりマップも直列実行（互換用）。"""
    global _last_scan
    with _lock:
        _set_health_progress(
            running=True,
            phase="start",
            percent=2,
            message="スキャンを開始しました…",
        )
        try:
            settings = db.get_settings()
            raw = _collect_all_with_progress()

            _set_health_progress(phase="evaluate", percent=75, message="リスク判定と提案を作成中…")
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

            _set_health_progress(phase="save", percent=90, message="結果を保存中…")
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

            if include_maps:
                try:
                    _run_space_maps()
                except Exception as map_exc:
                    print("space map after health failed", map_exc)

            _set_health_progress(
                phase="done",
                percent=100,
                message="健康診断が完了しました",
                finished=True,
            )
            return payload
        except Exception as exc:
            _set_health_progress(
                phase="error",
                message="スキャンに失敗しました",
                error=str(exc),
                finished=True,
            )
            raise


def _run_space_maps() -> None:
    from app.space_scan import list_drives, run_scan_blocking

    _set_mapping_progress(
        running=True,
        percent=2,
        message="容量マップの対象ドライブを確認中…",
        current_drive="",
    )
    try:
        drives = list_drives()
        if not drives:
            _set_mapping_progress(
                percent=100,
                message="マッピング対象のドライブがありません",
                finished=True,
            )
            return
        total = len(drives)
        for index, drive in enumerate(drives):
            letter = drive.get("letter") or "?"
            root = drive.get("rootPath") or f"{letter}:\\"
            percent = 5 + int((index / max(total, 1)) * 90)
            _set_mapping_progress(
                percent=percent,
                message=f"{letter}: のマッピングを作成中…（{index + 1}/{total}）",
                current_drive=f"{letter}:",
            )
            run_scan_blocking(root)
        _set_mapping_progress(
            percent=100,
            message="容量マップの作成が完了しました",
            finished=True,
        )
    except Exception as exc:
        _set_mapping_progress(
            message="容量マップの作成に失敗しました",
            error=str(exc),
            finished=True,
        )
        raise


def start_scan(notify_alerts: bool = True) -> dict[str, Any]:
    """健康診断と容量マップを並行でバックグラウンド開始する。"""
    global _scan_thread, _map_thread
    with _progress_lock:
        if _progress.get("running"):
            return {"ok": True, "started": False, "message": "already running"}
        now = datetime.now(timezone.utc).isoformat()
        _progress["running"] = True
        _progress["phase"] = "queued"
        _progress["percent"] = 1
        _progress["message"] = "健康診断と容量マップを準備中…"
        _progress["error"] = None
        _progress["started_at"] = now
        _progress["finished_at"] = None
        _progress["health"] = {
            "running": True,
            "percent": 1,
            "message": "健康診断を準備中…",
            "error": None,
            "phase": "queued",
        }
        _progress["mapping"] = {
            "running": True,
            "percent": 1,
            "message": "容量マップを準備中…",
            "error": None,
            "current_drive": None,
        }

    def _health_worker() -> None:
        try:
            run_scan(notify_alerts=notify_alerts, include_maps=False)
        except Exception:
            pass

    def _map_worker() -> None:
        try:
            _run_space_maps()
        except Exception:
            pass

    _scan_thread = threading.Thread(target=_health_worker, name="pchc-health-scan", daemon=True)
    _map_thread = threading.Thread(target=_map_worker, name="pchc-space-maps", daemon=True)
    _scan_thread.start()
    _map_thread.start()
    return {"ok": True, "started": True, "parallel": True}
