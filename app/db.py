from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.config import DATA_DIR, DB_PATH, DEFAULT_SETTINGS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS disk_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                device_id TEXT NOT NULL,
                model TEXT,
                health_status TEXT,
                free_pct REAL,
                risk_level TEXT,
                smart_json TEXT
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                level TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                device_id TEXT,
                notified INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS known_disks (
                device_id TEXT PRIMARY KEY,
                model TEXT,
                serial TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tracked_parts (
                catalog_id TEXT PRIMARY KEY,
                keep_legacy INTEGER NOT NULL DEFAULT 0,
                pending_decision INTEGER NOT NULL DEFAULT 0,
                display_name TEXT,
                category TEXT,
                query TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                catalog_id TEXT NOT NULL,
                price_yen INTEGER,
                source TEXT,
                url TEXT,
                note TEXT,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        _ensure_default_settings(conn)


def _ensure_default_settings(conn: sqlite3.Connection) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        row = conn.execute("SELECT 1 FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_settings() -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    settings = dict(DEFAULT_SETTINGS)
    for row in rows:
        try:
            settings[row["key"]] = json.loads(row["value"])
        except json.JSONDecodeError:
            settings[row["key"]] = row["value"]
    return settings


def update_settings(updates: dict[str, Any]) -> dict[str, Any]:
    with connect() as conn:
        for key, value in updates.items():
            if key not in DEFAULT_SETTINGS:
                continue
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )
    return get_settings()


def save_snapshot(overall_status: str, payload: dict[str, Any]) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO snapshots (created_at, overall_status, payload_json) VALUES (?, ?, ?)",
            (_utc_now(), overall_status, json.dumps(payload, ensure_ascii=False)),
        )
        return int(cur.lastrowid)


def save_disk_history(disks: list[dict[str, Any]]) -> None:
    now = _utc_now()
    with connect() as conn:
        for d in disks:
            conn.execute(
                """
                INSERT INTO disk_history
                (created_at, device_id, model, health_status, free_pct, risk_level, smart_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    d.get("device_id", ""),
                    d.get("model"),
                    d.get("health_status"),
                    d.get("free_pct"),
                    d.get("risk_level"),
                    json.dumps(d.get("smart") or {}, ensure_ascii=False),
                ),
            )


def get_latest_snapshot() -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, created_at, overall_status, payload_json "
            "FROM snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "overall_status": row["overall_status"],
        "payload": json.loads(row["payload_json"]),
    }


def get_disk_history(device_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT created_at, device_id, model, health_status, free_pct, risk_level, smart_json
            FROM disk_history
            WHERE device_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (device_id, limit),
        ).fetchall()
    result = []
    for row in rows:
        result.append(
            {
                "created_at": row["created_at"],
                "device_id": row["device_id"],
                "model": row["model"],
                "health_status": row["health_status"],
                "free_pct": row["free_pct"],
                "risk_level": row["risk_level"],
                "smart": json.loads(row["smart_json"] or "{}"),
            }
        )
    return list(reversed(result))


def add_alert(
    level: str,
    title: str,
    message: str,
    device_id: str | None = None,
    notified: bool = False,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO alerts (created_at, level, title, message, device_id, notified)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_utc_now(), level, title, message, device_id, 1 if notified else 0),
        )
        return int(cur.lastrowid)


def get_recent_alerts(limit: int = 30) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, level, title, message, device_id, notified
            FROM alerts ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_known_disks(disks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Track disk appearance/disappearance. Returns changes."""
    now = _utc_now()
    current_ids = {d["device_id"] for d in disks if d.get("device_id")}
    appeared: list[dict[str, Any]] = []
    disappeared: list[dict[str, Any]] = []

    with connect() as conn:
        known = {
            row["device_id"]: dict(row)
            for row in conn.execute("SELECT * FROM known_disks").fetchall()
        }
        for d in disks:
            did = d.get("device_id")
            if not did:
                continue
            if did not in known:
                conn.execute(
                    """
                    INSERT INTO known_disks (device_id, model, serial, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (did, d.get("model"), d.get("serial"), now, now),
                )
                appeared.append(d)
            else:
                conn.execute(
                    """
                    UPDATE known_disks
                    SET model = ?, serial = ?, last_seen = ?
                    WHERE device_id = ?
                    """,
                    (d.get("model"), d.get("serial"), now, did),
                )
        for did, info in known.items():
            if did not in current_ids:
                disappeared.append(info)
                conn.execute("DELETE FROM known_disks WHERE device_id = ?", (did,))

    return {"appeared": appeared, "disappeared": disappeared}


def get_meta(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_catalog_version() -> str | None:
    return get_meta("catalog_version")


def set_catalog_version(version: str) -> None:
    set_meta("catalog_version", version)


def get_tracked_parts() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT catalog_id, keep_legacy, pending_decision, display_name, category, query, created_at
            FROM tracked_parts ORDER BY category, display_name
            """
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_tracked(
    catalog_id: str,
    *,
    keep_legacy: bool = False,
    pending_decision: bool = False,
    display_name: str | None = None,
    category: str | None = None,
    query: str | None = None,
) -> None:
    with connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM tracked_parts WHERE catalog_id = ?", (catalog_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE tracked_parts
                SET keep_legacy = ?, pending_decision = ?,
                    display_name = COALESCE(?, display_name),
                    category = COALESCE(?, category),
                    query = COALESCE(?, query)
                WHERE catalog_id = ?
                """,
                (
                    1 if keep_legacy else 0,
                    1 if pending_decision else 0,
                    display_name,
                    category,
                    query,
                    catalog_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO tracked_parts
                (catalog_id, keep_legacy, pending_decision, display_name, category, query, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    catalog_id,
                    1 if keep_legacy else 0,
                    1 if pending_decision else 0,
                    display_name,
                    category,
                    query,
                    _utc_now(),
                ),
            )


def mark_tracked_pending(catalog_id: str, pending: bool) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE tracked_parts SET pending_decision = ? WHERE catalog_id = ?",
            (1 if pending else 0, catalog_id),
        )


def remove_tracked(catalog_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM tracked_parts WHERE catalog_id = ?", (catalog_id,))


def add_price_point(
    catalog_id: str,
    *,
    price_yen: int | None,
    source: str | None,
    url: str | None,
    note: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO price_history (catalog_id, price_yen, source, url, note, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (catalog_id, price_yen, source, url, note, _utc_now()),
        )


def get_latest_prices(catalog_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not catalog_ids:
        return {}
    result: dict[str, dict[str, Any]] = {}
    with connect() as conn:
        for cid in catalog_ids:
            row = conn.execute(
                """
                SELECT catalog_id, price_yen, source, url, note, fetched_at
                FROM price_history
                WHERE catalog_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (cid,),
            ).fetchone()
            if row:
                result[cid] = dict(row)
    return result


def get_price_history(catalog_id: str, limit: int = 24) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT price_yen, source, url, note, fetched_at
            FROM price_history
            WHERE catalog_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (catalog_id, limit),
        ).fetchall()
    return list(reversed([dict(r) for r in rows]))
