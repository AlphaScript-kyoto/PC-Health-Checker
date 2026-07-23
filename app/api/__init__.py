from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db
from app.config import UI_DIR
from app.scanner import get_last_scan, run_scan

app = FastAPI(title="PC Health Monitor", docs_url="/api/docs")


class SettingsUpdate(BaseModel):
    notify_enabled: bool | None = None
    capacity_warn_pct: float | None = Field(None, ge=1, le=50)
    capacity_critical_pct: float | None = Field(None, ge=0.5, le=30)
    budget_max_yen: int | None = Field(None, ge=1000, le=500000)
    prefer_new_used: str | None = None
    prefer_media: str | None = None
    capacity_preference_tb: float | None = Field(None, ge=0.1, le=20)
    priority: str | None = None
    daily_scan_time: str | None = None
    startup_enabled: bool | None = None


def _valid_daily_scan_time(value: str) -> bool:
    try:
        hour_s, minute_s = value.strip().split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
        return 0 <= hour <= 23 and 0 <= minute <= 59 and len(minute_s) == 2
    except Exception:
        return False


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/about")
def api_about() -> dict[str, Any]:
    from app.collectors.disks import is_elevated, smartctl_available
    from app.config import (
        APP_AUTHOR,
        APP_CONTACT,
        APP_HOMEPAGE,
        APP_NAME,
        APP_VERSION,
    )

    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "author": APP_AUTHOR,
        "homepage": APP_HOMEPAGE,
        "contact": APP_CONTACT,
        "elevated": is_elevated(),
        "smartctl_available": smartctl_available(),
    }


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    last = get_last_scan()
    if last:
        return last
    snap = db.get_latest_snapshot()
    if snap:
        return {
            "overall_status": snap["overall_status"],
            "scanned_at": snap["created_at"],
            **snap["payload"],
        }
    return {"overall_status": "Unknown", "message": "まだスキャンされていません"}


@app.post("/api/scan")
def api_scan() -> dict[str, Any]:
    return run_scan(notify_alerts=True)


@app.get("/api/settings")
def api_get_settings() -> dict[str, Any]:
    settings = db.get_settings()
    from app.startup import is_startup_enabled

    settings["startup_enabled"] = is_startup_enabled()
    return settings


@app.put("/api/settings")
def api_put_settings(body: SettingsUpdate) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "prefer_new_used" in updates and updates["prefer_new_used"] not in (
        "new",
        "used",
        "either",
    ):
        raise HTTPException(400, "prefer_new_used must be new|used|either")
    if "prefer_media" in updates and updates["prefer_media"] not in (
        "ssd",
        "hdd",
        "either",
    ):
        raise HTTPException(400, "prefer_media must be ssd|hdd|either")
    if "priority" in updates and updates["priority"] not in (
        "speed",
        "quiet",
        "capacity",
        "price",
    ):
        raise HTTPException(400, "priority must be speed|quiet|capacity|price")
    if "daily_scan_time" in updates:
        raw = str(updates["daily_scan_time"]).strip()
        if not _valid_daily_scan_time(raw):
            raise HTTPException(400, "daily_scan_time must be HH:MM (24-hour)")
        updates["daily_scan_time"] = f"{int(raw.split(':')[0]):02d}:{int(raw.split(':')[1]):02d}"
    settings = db.update_settings(updates)
    if "startup_enabled" in updates:
        from app.startup import set_startup

        set_startup(bool(updates["startup_enabled"]))
    return settings


@app.get("/api/alerts")
def api_alerts() -> list[dict[str, Any]]:
    return db.get_recent_alerts()


@app.get("/api/disks/{device_id}/history")
def api_disk_history(device_id: str) -> list[dict[str, Any]]:
    return db.get_disk_history(device_id)


@app.get("/api/recommendations")
def api_recommendations() -> dict[str, Any]:
    last = get_last_scan()
    if last:
        return {
            "recommendations": last.get("recommendations") or [],
            "scanned_at": last.get("scanned_at"),
        }
    snap = db.get_latest_snapshot()
    if snap:
        payload = snap["payload"]
        return {
            "recommendations": payload.get("recommendations") or [],
            "scanned_at": snap["created_at"],
        }
    return {"recommendations": [], "scanned_at": None}


@app.get("/api/news")
def api_news(force: bool = False) -> dict[str, Any]:
    from app.news import fetch_news

    return fetch_news(force=force)


class TrackedUpdate(BaseModel):
    ids: list[str]


class OrphanDecisions(BaseModel):
    decisions: dict[str, str]  # id -> keep|drop


@app.get("/api/prices")
def api_prices() -> dict[str, Any]:
    from app.price_tracker import get_tracker_state

    return get_tracker_state()


@app.put("/api/prices/tracked")
def api_prices_tracked(body: TrackedUpdate) -> dict[str, Any]:
    from app.price_tracker import set_tracked

    return set_tracked(body.ids)


@app.post("/api/prices/orphans")
def api_prices_orphans(body: OrphanDecisions) -> dict[str, Any]:
    from app.price_tracker import resolve_orphans

    cleaned = {
        k: v for k, v in body.decisions.items() if v in ("keep", "drop")
    }
    return resolve_orphans(cleaned)


@app.post("/api/prices/refresh")
def api_prices_refresh(force: bool = True) -> dict[str, Any]:
    from app.price_tracker import refresh_prices

    return refresh_prices(force=force)


def mount_ui(application: FastAPI) -> None:
    index = UI_DIR / "index.html"
    if UI_DIR.exists():
        application.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

    @application.get("/")
    def index_page() -> FileResponse:
        if not index.exists():
            raise HTTPException(404, "UI not found")
        return FileResponse(
            index,
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
