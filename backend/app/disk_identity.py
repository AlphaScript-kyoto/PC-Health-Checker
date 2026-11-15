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


def is_legacy_number_id(device_id: Any) -> bool:
    text = str(device_id or "")
    return bool(text) and not text.startswith(STABLE_PREFIXES)
