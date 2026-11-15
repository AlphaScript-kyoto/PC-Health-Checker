"""通知の重複排除。文言の数字ではなく、種類・対象・危険度で判断する。"""

from __future__ import annotations

import re
from typing import Any

# Unknown は「問題なし」より上。悪化したときだけ、もう一度知らせる。
LEVEL_RANK = {"OK": 0, "Unknown": 1, "Watch": 2, "ReplaceSoon": 3, "Critical": 4}
NOTIFY_LEVELS = {"Watch", "ReplaceSoon", "Critical"}

_LETTER = re.compile(r"([A-Za-z]):")


def alert_target(alert: dict[str, Any]) -> str:
    kind = str(alert.get("kind") or "other")
    explicit = alert.get("target")
    if explicit not in (None, ""):
        return str(explicit)
    if kind == "capacity":
        letter = alert.get("letter")
        if letter:
            return str(letter)
        title = str(alert.get("title") or "")
        found = _LETTER.search(title)
        if found:
            return f"{found.group(1).upper()}:"
    return str(alert.get("stable_id") or alert.get("device_id") or "-")


def dedupe_key_for(alert: dict[str, Any]) -> str:
    """同じ事象を指す安定キー。危険度は含めない（悪化の比較に使うため）。"""
    kind = str(alert.get("kind") or "other")
    return f"{kind}|{alert_target(alert)}"


def decide_alert(alert: dict[str, Any], previous_level: str | None) -> tuple[bool, bool]:
    """戻り値は (履歴に残すか, 通知するか)。

    - 同じ危険度の繰り返しは残さない（空き％や温度の数字が変わっただけ、を含む）
    - 危険度が上がったときだけ通知する
    - 良くなったときは履歴だけ更新し、通知しない（次に悪化したら再び知らせる）
    """
    level = str(alert.get("level") or "")
    rank = LEVEL_RANK.get(level, 0)
    if previous_level is None:
        return True, level in NOTIFY_LEVELS
    previous = LEVEL_RANK.get(str(previous_level), 0)
    if rank == previous:
        return False, False
    if rank > previous:
        return True, level in NOTIFY_LEVELS
    return True, False
