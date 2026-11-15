"""起動時スキャンと毎日スキャンが、互いの失敗を「済んだこと」にしないための判断。"""

from __future__ import annotations

# 定刻スキャンが失敗したあと、ディスクを叩き続けないための再試行間隔（秒）
DAILY_RETRY_SEC = 15 * 60


def startup_covers_daily(*, startup_succeeded: bool, now_past_slot: bool) -> bool:
    """起動時スキャンが実際に成功し、すでに定刻を過ぎているときだけ当日分とみなす。

    プロセスを定刻のあとに起動した、という事実だけでは済ませない。
    画面側の起動スキャンが失敗して消えても、定刻スキャンは残る。
    """
    return bool(startup_succeeded and now_past_slot)


def daily_is_due(
    *,
    now_past_slot: bool,
    covered_today: bool,
    seconds_since_failure: float | None,
    retry_sec: float = DAILY_RETRY_SEC,
) -> bool:
    if not now_past_slot or covered_today:
        return False
    if seconds_since_failure is None:
        return True
    return seconds_since_failure >= retry_sec
