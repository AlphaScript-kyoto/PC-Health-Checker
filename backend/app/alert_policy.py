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


# 一度きりの出来事。解消記録は残さず、対象が分かる文だけを別途使う。
ONE_SHOT_KINDS = {"disk_added", "disk_removed"}
DISK_ALERT_KINDS = {"disk", "disk_added", "disk_removed"}


def reason_kinds(message: str | None) -> set[str]:
    """理由を「 / 」で分け、数字を落とした種類の集合。"""
    kinds: set[str] = set()
    for part in re.split(r"\s*/\s*", str(message or "")):
        label = re.sub(r"\d+(?:\.\d+)?", "", part)
        label = re.sub(r"[%°℃()（）]", " ", label)
        label = re.sub(r"\s+", " ", label).strip(" :：").lower()
        if label:
            kinds.add(label)
    return kinds


def decide_alert(
    alert: dict[str, Any],
    previous_level: str | None,
    previous_message: str | None = None,
) -> tuple[bool, bool]:
    """戻り値は (履歴に残すか, 通知するか)。

    - 同じ危険度で、新しい理由の種類が増えていなければ残さない
      （数字の変化、理由が減っただけ、しきい値付近の出入りを含む）
    - 危険度が上がったとき、または同じ危険度で理由の種類が増えたとき通知する
    - 良くなったときは履歴だけ更新し、通知しない
    """
    level = str(alert.get("level") or "")
    rank = LEVEL_RANK.get(level, 0)
    if previous_level is None:
        return True, level in NOTIFY_LEVELS
    previous = LEVEL_RANK.get(str(previous_level), 0)
    if rank == previous:
        if previous_message is None:
            return False, False
        added = reason_kinds(alert.get("message")) - reason_kinds(previous_message)
        if not added:
            return False, False
        return True, level in NOTIFY_LEVELS
    if rank > previous:
        return True, level in NOTIFY_LEVELS
    return True, False


def skip_kinds_for_collection_errors(*, disk_failed: bool, capacity_failed: bool) -> set[str]:
    """取得に失敗した種類は、注意が消えたとは扱わない。"""
    skip: set[str] = set()
    if disk_failed:
        skip.update(DISK_ALERT_KINDS)
    if capacity_failed:
        skip.add("capacity")
    return skip


def keys_to_resolve(
    previous_levels: dict[str, str],
    seen_keys: set[str],
    *,
    skip_kinds: set[str] | None = None,
) -> list[str]:
    """今回のスキャンに無かった継続中の注意。取得失敗の種類と、一度きりの出来事は除く。"""
    skipped = set(skip_kinds or ())
    skipped.update(ONE_SHOT_KINDS)
    found: list[str] = []
    for key, level in previous_levels.items():
        if key in seen_keys or level in ("", "OK"):
            continue
        kind = key.split("|", 1)[0]
        if kind in skipped:
            continue
        found.append(key)
    return found


def resolve_notice(key: str) -> tuple[str, str, str | None]:
    """解消記録の題・本文・対象。対象がキーに含まれるときは、履歴から分かるように残す。"""
    kind, _, target = key.partition("|")
    shown = target if target and target != "-" else "対象不明"
    device_id = None if not target or target == "-" else target
    if kind == "capacity":
        return (
            "注意は解消しました",
            f"{shown} の容量の注意は、今回のスキャンでは見当たりませんでした。",
            device_id,
        )
    if kind == "disk":
        return (
            "注意は解消しました",
            f"{shown} のディスクの注意は、今回のスキャンでは見当たりませんでした。",
            device_id,
        )
    return (
        "注意は解消しました",
        f"{shown} の前回の注意は、今回のスキャンでは見当たりませんでした。",
        device_id,
    )


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
