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


def reason_signature(message: str | None) -> str:
    """数字や単位の差を除いた理由の形。温度が 61℃ から 65℃ でも同じ、摩耗とは違う。"""
    text = re.sub(r"\d+(?:\.\d+)?", "#", str(message or ""))
    return re.sub(r"\s+", " ", text).strip().lower()


def decide_alert(
    alert: dict[str, Any],
    previous_level: str | None,
    previous_message: str | None = None,
) -> tuple[bool, bool]:
    """戻り値は (履歴に残すか, 通知するか)。

    - 同じ危険度で、理由の種類も同じなら残さない（空き％や温度の数字が変わっただけ、を含む）
    - 危険度が上がったとき、または同じ危険度でも理由の種類が変わったとき通知する
    - 良くなったときは履歴だけ更新し、通知しない（解消を OK で残すと、再発を再び知らせられる）
    """
    level = str(alert.get("level") or "")
    rank = LEVEL_RANK.get(level, 0)
    if previous_level is None:
        return True, level in NOTIFY_LEVELS
    previous = LEVEL_RANK.get(str(previous_level), 0)
    if rank == previous:
        if previous_message is not None and reason_signature(alert.get("message")) != reason_signature(
            previous_message
        ):
            return True, level in NOTIFY_LEVELS
        return False, False
    if rank > previous:
        return True, level in NOTIFY_LEVELS
    return True, False


def keys_to_resolve(previous_levels: dict[str, str], seen_keys: set[str]) -> list[str]:
    """今回のスキャンに無かった注意。OK を残して、同じ危険度の再発を再び知らせられるようにする。"""
    return [
        key
        for key, level in previous_levels.items()
        if key not in seen_keys and level not in ("", "OK")
    ]


def legacy_dedupe_key(title: str | None, device_id: str | None) -> tuple[str, str] | None:
    """更新前の通知文から、付けられる範囲で安定キーを復元する。"""
    text = str(title or "").strip()
    target = str(device_id or "").strip() or "-"
    if text.startswith("容量不足:"):
        letter = text.split(":", 1)[1].strip()
        if letter and not letter.endswith(":"):
            letter = f"{letter[:1].upper()}:"
        return "capacity", f"capacity|{letter or '-'}"
    if text.startswith("新しいディスク"):
        return "disk_added", f"disk_added|{target}"
    if "消え" in text:
        return "disk_removed", f"disk_removed|{target}"
    if text.startswith("ディスク情報を取得できませんでした"):
        return "collection", "collection|disks"
    if text.startswith("空き容量を取得できませんでした"):
        return "collection", "collection|volumes"
    if text.startswith("PC情報"):
        return "collection", "collection|inventory"
    if text.startswith("ディスク"):
        return "disk", f"disk|{target}"
    return None
