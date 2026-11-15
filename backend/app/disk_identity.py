"""物理ディスクを、Windows のディスク番号ではなく個体で識別する。"""

from __future__ import annotations

import re
from typing import Any

# known_disks.device_id に保存する安定IDの接頭辞。
# 昔の「0」「1」のような番号と混ざらないようにする。
STABLE_PREFIXES = ("sn:", "pnp:", "fb:", "num:")

_BAD_SERIALS = {
    "",
    "NONE",
    "NULL",
    "UNKNOWN",
    "N/A",
    "NA",
    "NOT AVAILABLE",
    "NOTAVAILABLE",
    "TO BE FILLED BY O.E.M.",
    "TOBEFILLEDBYO.E.M.",
    "00000000",
    "000000000000",
    "0000000000000000",
    "0000_0000_0000_0000",
    "00000000000000000000",
}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def normalize_model(value: Any) -> str:
    return _norm(value)


def serial_usable(serial: Any) -> bool:
    """メーカーが埋めていないプレースホルダや、全部 0 のシリアルは個体の鍵にしない。"""
    text = _norm(serial).replace(" ", "")
    compact = text.replace("_", "").replace("-", "")
    if text in _BAD_SERIALS or compact in _BAD_SERIALS:
        return False
    if not compact:
        return False
    if set(compact) <= {"0"}:
        return False
    return True


def disk_stable_id(disk: dict[str, Any]) -> str:
    """シリアル＋モデルを優先し、無ければ接続情報、最後にディスク番号へ落とす。"""
    model = normalize_model(disk.get("model") or disk.get("friendly_name"))
    if serial_usable(disk.get("serial")):
        serial = _norm(disk.get("serial")).replace(" ", "")
        return f"sn:{serial}|mdl:{model}"

    pnp = _norm(disk.get("pnp_device_id")).replace(" ", "")
    if pnp and pnp not in {"NONE", "UNKNOWN", "NULL"}:
        return f"pnp:{pnp}"

    size = disk.get("size_bytes")
    if size in (None, ""):
        size = disk.get("size_gb") if disk.get("size_gb") not in (None, "") else ""
    bus = _norm(disk.get("bus_type") or disk.get("interface"))
    media = _norm(disk.get("media_type"))
    if model and model not in {"UNKNOWN", "DISK"}:
        return f"fb:{model}|{size}|{bus}|{media}"

    number = str(disk.get("device_id") or "").strip() or "unknown"
    return f"num:{number}"


def identity_from_known_row(row: dict[str, Any]) -> str:
    """保存済み行の照合キー。新しい安定IDならそのまま、昔の番号なら計算し直す。"""
    device_id = str(row.get("device_id") or "")
    if device_id.startswith(STABLE_PREFIXES):
        return device_id
    return disk_stable_id(
        {
            "serial": row.get("serial"),
            "model": row.get("model"),
            "device_id": device_id,
        }
    )


def identity_rank(ident: str) -> int:
    """強い識別ほど大きい。シリアルがある行を、あとから PnP だけに落とさない。"""
    if ident.startswith("sn:"):
        return 3
    if ident.startswith("pnp:"):
        return 2
    if ident.startswith("fb:"):
        return 1
    return 0


def normalized_pnp(disk: dict[str, Any]) -> str:
    pnp = _norm(disk.get("pnp_device_id")).replace(" ", "")
    if pnp in {"", "NONE", "UNKNOWN", "NULL"}:
        return ""
    return pnp


def candidate_identities(disk: dict[str, Any]) -> list[str]:
    """強い順。同じ個体を、取れた情報のどれかで見つけられるようにする。"""
    found: list[str] = []

    def add(value: str) -> None:
        if value and value not in found:
            found.append(value)

    model = normalize_model(disk.get("model") or disk.get("friendly_name"))
    if serial_usable(disk.get("serial")):
        serial = _norm(disk.get("serial")).replace(" ", "")
        add(f"sn:{serial}|mdl:{model}")
    pnp = normalized_pnp(disk)
    if pnp:
        add(f"pnp:{pnp}")
    size = disk.get("size_bytes")
    if size in (None, ""):
        size = disk.get("size_gb") if disk.get("size_gb") not in (None, "") else ""
    bus = _norm(disk.get("bus_type") or disk.get("interface"))
    media = _norm(disk.get("media_type"))
    if model and model not in {"UNKNOWN", "DISK"}:
        add(f"fb:{model}|{size}|{bus}|{media}")
    number = str(disk.get("device_id") or "").strip() or "unknown"
    add(f"num:{number}")
    return found


def choose_stored_id(current_best: str, existing_id: str | None) -> str:
    """一度シリアルで覚えた個体を、次回シリアルが取れないからといって別IDにしない。"""
    if not existing_id:
        return current_best
    if identity_rank(current_best) > identity_rank(existing_id):
        return current_best
    return existing_id


def assign_collision_ids(disks: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    """シリアルの無い同型が複数あるとき、Windows の番号ではなく既存の並びで対応づける。

    番号を接尾辞にすると、挿し替えのたびに「消えた」「新しい」になる。
    台数が同じなら、先に見た順の ID を再利用する。
    """
    from collections import defaultdict

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for disk in disks:
        groups[candidate_identities(disk)[0]].append(disk)
    for base, group in groups.items():
        if len(group) < 2 or base.startswith("sn:"):
            continue
        existing = [
            row
            for row in rows
            if str(row.get("device_id") or "") == base
            or str(row.get("device_id") or "").startswith(base + "|n:")
        ]
        existing.sort(key=lambda row: (str(row.get("first_seen") or ""), str(row.get("device_id") or "")))
        group.sort(
            key=lambda disk: (
                str(disk.get("size_bytes") or ""),
                normalize_model(disk.get("model")),
                str(disk.get("bus_type") or ""),
                str(disk.get("device_id") or ""),
            )
        )
        for index, disk in enumerate(group):
            if index < len(existing):
                disk["_paired_id"] = str(existing[index].get("device_id") or "")
            else:
                disk["_paired_id"] = f"{base}|n:{index}"


def is_legacy_number_id(device_id: Any) -> bool:
    text = str(device_id or "")
    return bool(text) and not text.startswith(STABLE_PREFIXES)
