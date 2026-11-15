from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from app.config import DATA_DIR, DB_PATH, DEFAULT_SETTINGS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# 診断・価格の履歴を無期限に貯めない
HISTORY_RETENTION_DAYS = 180


def _purge_expired(conn: sqlite3.Connection) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)).isoformat()
    conn.execute("DELETE FROM snapshots WHERE created_at < ?", (cutoff,))
    conn.execute("DELETE FROM disk_history WHERE created_at < ?", (cutoff,))
    conn.execute("DELETE FROM alerts WHERE created_at < ?", (cutoff,))
    conn.execute("DELETE FROM price_history WHERE fetched_at < ?", (cutoff,))


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
                notified INTEGER NOT NULL DEFAULT 0,
                kind TEXT,
                dedupe_key TEXT
            );

            CREATE TABLE IF NOT EXISTS known_disks (
                device_id TEXT PRIMARY KEY,
                model TEXT,
                serial TEXT,
                pnp_id TEXT,
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

            CREATE INDEX IF NOT EXISTS idx_disk_history_device_id
                ON disk_history (device_id, id);
            CREATE INDEX IF NOT EXISTS idx_price_history_catalog_id
                ON price_history (catalog_id, id);
            CREATE INDEX IF NOT EXISTS idx_price_history_catalog_source
                ON price_history (catalog_id, source, id);
            CREATE INDEX IF NOT EXISTS idx_snapshots_created_at
                ON snapshots (created_at);
            CREATE INDEX IF NOT EXISTS idx_alerts_created_at
                ON alerts (created_at);
            CREATE INDEX IF NOT EXISTS idx_price_history_fetched_at
                ON price_history (fetched_at);
            """
        )
        _ensure_alert_columns(conn)
        _ensure_known_disk_columns(conn)
        _backfill_alert_keys(conn)
        _ensure_default_settings(conn)
        _purge_expired(conn)


def _ensure_alert_columns(conn: sqlite3.Connection) -> None:
    """既存DBには kind / dedupe_key が無い。通知の安定キー用に足す。"""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
    if "kind" not in cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN kind TEXT")
    if "dedupe_key" not in cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN dedupe_key TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_dedupe_key ON alerts (dedupe_key, id)"
    )


def _ensure_known_disk_columns(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(known_disks)").fetchall()}
    if "pnp_id" not in cols:
        conn.execute("ALTER TABLE known_disks ADD COLUMN pnp_id TEXT")


def _backfill_alert_keys(conn: sqlite3.Connection) -> None:
    """安定キーが無い古い通知に、分かる範囲でキーを付ける。全部を一度に再通知しないため。"""
    from app.alert_policy import legacy_dedupe_key

    rows = conn.execute(
        """
        SELECT id, title, device_id FROM alerts
        WHERE dedupe_key IS NULL OR dedupe_key = ''
        """
    ).fetchall()
    for row in rows:
        guessed = legacy_dedupe_key(row["title"], row["device_id"])
        if not guessed:
            continue
        kind, key = guessed
        conn.execute(
            "UPDATE alerts SET kind = COALESCE(kind, ?), dedupe_key = ? WHERE id = ?",
            (kind, key, row["id"]),
        )


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
        _purge_expired(conn)
        return int(cur.lastrowid)


def save_disk_history(disks: list[dict[str, Any]]) -> None:
    now = _utc_now()
    with connect() as conn:
        for d in disks:
            # 履歴は Windows のディスク番号ではなく個体IDで残す（差し替え・再接続で混ざらない）
            history_id = d.get("stable_id") or d.get("device_id") or ""
            conn.execute(
                """
                INSERT INTO disk_history
                (created_at, device_id, model, health_status, free_pct, risk_level, smart_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    history_id,
                    d.get("model"),
                    d.get("health_status"),
                    d.get("free_pct"),
                    d.get("risk_level"),
                    json.dumps(d.get("smart") or {}, ensure_ascii=False),
                ),
            )
        _purge_expired(conn)


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
    kind: str | None = None,
    dedupe_key: str | None = None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO alerts (created_at, level, title, message, device_id, notified, kind, dedupe_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now(),
                level,
                title,
                message,
                device_id,
                1 if notified else 0,
                kind,
                dedupe_key,
            ),
        )
        return int(cur.lastrowid)


def get_recent_alerts(limit: int = 30) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, level, title, message, device_id, notified, kind, dedupe_key
            FROM alerts ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _latest_alert_rows() -> list[dict[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT a.dedupe_key, a.level, a.message
            FROM alerts a
            INNER JOIN (
                SELECT dedupe_key, MAX(id) AS max_id
                FROM alerts
                WHERE dedupe_key IS NOT NULL AND dedupe_key != ''
                GROUP BY dedupe_key
            ) m ON a.id = m.max_id
            """
        ).fetchall()
        return [
            {
                "dedupe_key": str(row["dedupe_key"] or ""),
                "level": str(row["level"] or ""),
                "message": str(row["message"] or ""),
            }
            for row in rows
        ]


def get_latest_alert_levels() -> dict[str, str]:
    """安定キーごとの、いちばん新しい危険度。"""
    return {str(row["dedupe_key"]): str(row["level"]) for row in _latest_alert_rows()}


def get_latest_alert_states() -> dict[str, dict[str, str]]:
    """安定キーごとの、いちばん新しい危険度と本文。"""
    return {
        str(row["dedupe_key"]): {
            "level": str(row["level"] or ""),
            "message": str(row["message"] or ""),
        }
        for row in _latest_alert_rows()
    }


def _rekey_known_disk(
    conn: sqlite3.Connection,
    old_pk: str,
    new_id: str,
    disk: dict[str, Any],
    first_seen: str,
    now: str,
    pnp_id: str | None,
) -> None:
    serial = disk.get("serial")
    model = disk.get("model")
    if old_pk == new_id:
        conn.execute(
            """
            UPDATE known_disks
            SET model = ?, serial = ?, pnp_id = ?, last_seen = ?
            WHERE device_id = ?
            """,
            (model, serial, pnp_id, now, new_id),
        )
        return
    existing = conn.execute(
        "SELECT first_seen FROM known_disks WHERE device_id = ?",
        (new_id,),
    ).fetchone()
    kept_first = first_seen
    if existing and existing["first_seen"]:
        kept_first = min(str(existing["first_seen"]), str(first_seen))
        conn.execute("DELETE FROM known_disks WHERE device_id = ?", (new_id,))
    conn.execute(
        """
        INSERT INTO known_disks (device_id, model, serial, pnp_id, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (new_id, model, serial, pnp_id, kept_first, now),
    )
    conn.execute("DELETE FROM known_disks WHERE device_id = ?", (old_pk,))
    conn.execute(
        "UPDATE disk_history SET device_id = ? WHERE device_id = ?",
        (new_id, old_pk),
    )


def _adopt_legacy_row(
    disk: dict[str, Any],
    rows: list[dict[str, Any]],
    consumed: set[str],
) -> dict[str, Any] | None:
    """昔の「ディスク番号」行を、シリアルやモデルが一致する個体へ引き継ぐ。

    番号だけで引き継ぐと、同じ番号に別のディスクが刺さったことを見逃す。
    シリアルが無い行は、モデルが一意なときだけ引き継ぐ。
    """
    from app.disk_identity import is_legacy_number_id, normalize_model, serial_usable

    candidates = []
    for row in rows:
        pk = str(row.get("device_id") or "")
        if pk in consumed or not is_legacy_number_id(pk):
            continue
        if serial_usable(row.get("serial")):
            # シリアルがある昔の行は、安定IDの照合で見つかるはず。ここには来ない。
            continue
        candidates.append(row)
    if not candidates:
        return None

    model = normalize_model(disk.get("model"))
    same_model = [
        row for row in candidates if model and normalize_model(row.get("model")) == model
    ]
    if len(same_model) == 1:
        return same_model[0]

    number = str(disk.get("device_id") or "")
    same_number = [row for row in candidates if str(row.get("device_id")) == number]
    if serial_usable(disk.get("serial")) and len(same_number) == 1:
        legacy_model = normalize_model(same_number[0].get("model"))
        if not legacy_model or legacy_model == model:
            return same_number[0]
    return None


def upsert_known_disks(disks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """個体IDで出現・消滅を追跡する。記録が空の初回はベースラインで、新規通知は出さない。"""
    from app.disk_identity import (
        STABLE_PREFIXES,
        assign_collision_ids,
        candidate_identities,
        choose_stored_id,
        identity_from_known_row,
        normalized_pnp,
        serial_usable,
    )

    now = _utc_now()
    appeared: list[dict[str, Any]] = []
    disappeared: list[dict[str, Any]] = []

    with connect() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM known_disks").fetchall()]
        baseline = len(rows) == 0
        assign_collision_ids(disks, rows)
        # シリアルの無い昔の番号行は、ここで潰すと別の個体と衝突する。モデルが一意なときだけ引き継ぐ。
        by_identity: dict[str, dict[str, Any]] = {}
        for row in rows:
            device_id = str(row.get("device_id") or "")
            if device_id.startswith(STABLE_PREFIXES):
                by_identity[device_id] = row
            elif serial_usable(row.get("serial")):
                by_identity[identity_from_known_row(row)] = row
            pnp_id = str(row.get("pnp_id") or "")
            if pnp_id:
                by_identity.setdefault(f"pnp:{pnp_id}", row)
        consumed: set[str] = set()
        seen: set[str] = set()

        for disk in disks:
            candidates = candidate_identities(disk)
            best = candidates[0]
            paired = str(disk.pop("_paired_id", "") or "")
            row = by_identity.get(paired) if paired else None
            if row is not None and str(row.get("device_id") or "") in consumed:
                row = None
            if row is None:
                for key in candidates:
                    found = by_identity.get(key)
                    if found is not None and str(found.get("device_id") or "") not in consumed:
                        row = found
                        break
            if row is None:
                row = _adopt_legacy_row(disk, rows, consumed)
            pnp_id = normalized_pnp(disk) or None
            if row is None:
                ident = paired or best
                if ident in seen:
                    ident = f"{best}|n:{len(seen)}"
                seen.add(ident)
                disk["stable_id"] = ident
                conn.execute(
                    """
                    INSERT INTO known_disks
                    (device_id, model, serial, pnp_id, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ident, disk.get("model"), disk.get("serial"), pnp_id, now, now),
                )
                if not baseline:
                    appeared.append(disk)
                continue

            old_pk = str(row.get("device_id") or "")
            # 同型の対応づけは、その行の ID を維持する。シリアルが弱い情報に戻っても ID は下げない。
            ident = paired or choose_stored_id(best, old_pk)
            if ident in seen and ident != old_pk:
                ident = old_pk
            seen.add(ident)
            disk["stable_id"] = ident
            consumed.add(old_pk)
            _rekey_known_disk(
                conn,
                old_pk,
                ident,
                disk,
                str(row.get("first_seen") or now),
                now,
                pnp_id or (str(row.get("pnp_id") or "") or None),
            )

        if not baseline:
            for row in rows:
                pk = str(row.get("device_id") or "")
                if pk not in consumed:
                    gone = dict(row)
                    gone["stable_id"] = identity_from_known_row(row)
                    disappeared.append(gone)
                    conn.execute("DELETE FROM known_disks WHERE device_id = ?", (pk,))

    return {"appeared": appeared, "disappeared": disappeared, "baseline": baseline}


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
        _purge_expired(conn)


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


def get_latest_prices_by_source(catalog_ids: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    """Latest price per catalog_id and source (kakaku / amazon)."""
    if not catalog_ids:
        return {}
    result: dict[str, dict[str, dict[str, Any]]] = {cid: {} for cid in catalog_ids}
    with connect() as conn:
        for cid in catalog_ids:
            for source in ("kakaku", "amazon"):
                row = conn.execute(
                    """
                    SELECT catalog_id, price_yen, source, url, note, fetched_at
                    FROM price_history
                    WHERE catalog_id = ? AND source = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (cid, source),
                ).fetchone()
                if row:
                    result[cid][source] = dict(row)
    return result


def get_price_history(
    catalog_id: str, limit: int = 52, source: str | None = None
) -> list[dict[str, Any]]:
    with connect() as conn:
        if source:
            rows = conn.execute(
                """
                SELECT price_yen, source, url, note, fetched_at
                FROM price_history
                WHERE catalog_id = ? AND source = ?
                ORDER BY id DESC LIMIT ?
                """,
                (catalog_id, source, limit),
            ).fetchall()
        else:
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
