"""自動の容量マップを、何日に1回にするかの判断。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def space_map_due(
    last_iso: str | None,
    interval_days: int,
    *,
    now: datetime | None = None,
) -> bool:
    """interval_days が 0 以下なら毎回。それ以外は前回からその日数以上空いていれば実施。"""
    try:
        interval = int(interval_days)
    except (TypeError, ValueError):
        interval = 1
    if interval <= 0:
        return True
    if not last_iso:
        return True
    try:
        last = datetime.fromisoformat(str(last_iso))
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current - last >= timedelta(days=interval)
