"""自動の容量マップを、何日に1回にするかの判断。"""

from __future__ import annotations

from datetime import datetime, timezone


def space_map_due(
    last_iso: str | None,
    interval_days: int,
    *,
    now: datetime | None = None,
    tz: timezone | None = None,
) -> bool:
    """interval_days が 0 以下なら毎回。それ以外は暦の日付で、前回からその日数以上離れていれば実施。

    終了時刻から 24 時間ちょうどで数えると、同じ時刻の翌日スキャンが「まだ 24 時間経っていない」
    と見送られ、実質 2 日に 1 回になる。日付で比べる。
    """
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
    zone = tz or datetime.now().astimezone().tzinfo or timezone.utc
    elapsed_days = (current.astimezone(zone).date() - last.astimezone(zone).date()).days
    return elapsed_days >= interval
