from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

# CrystalDiskInfo-like Japanese labels for common SMART IDs / names
ATTR_LABELS_JA: dict[str, str] = {
    "01": "リードエラー率",
    "02": "スループット性能",
    "03": "スピンアップ時間",
    "04": "始動・停止回数",
    "05": "代替処理済セクタ数",
    "07": "シークエラー率",
    "09": "使用時間",
    "0A": "スピンアップ回数",
    "0C": "電源投入回数",
    "B8": "エンドツーエンドエラー",
    "BB": "報告済み訂正不能エラー",
    "BC": "コマンドタイムアウト",
    "BD": "衝撃検出回数",
    "BE": "エアフロー温度",
    "C0": "電源断回数",
    "C1": "ロード／アンロード回数",
    "C2": "温度",
    "C3": "ハードウェアECC発生率",
    "C4": "代替処理発生回数",
    "C5": "代替処理保留中セクタ数",
    "C6": "訂正不可能セクタ数",
    "C7": "UltraDMA CRCエラー数",
    "C8": "ライトエラー率",
    "F1": "総書込量",
    "F2": "総読込量",
    "Reallocated_Sector_Ct": "代替処理済セクタ数",
    "Power_On_Hours": "使用時間",
    "Power_Cycle_Count": "電源投入回数",
    "Temperature_Celsius": "温度",
    "Current_Pending_Sector": "代替処理保留中セクタ数",
    "Offline_Uncorrectable": "訂正不可能セクタ数",
    "UDMA_CRC_Error_Count": "UltraDMA CRCエラー数",
    "Reported_Uncorrect": "報告済み訂正不能エラー",
    "Wear_Leveling_Count": "ウェアレベリング回数",
    "Used_Rsvd_Blk_Cnt_Tot": "使用済み予約ブロック",
    "Program_Fail_Cnt_Total": "プログラム失敗回数",
    "Erase_Fail_Count_Total": "消去失敗回数",
    "Runtime_Bad_Block": "ランタイム不良ブロック",
    "End-to-End_Error": "エンドツーエンドエラー",
    "Airflow_Temperature_Cel": "エアフロー温度",
    "Hardware_ECC_Recovered": "ハードウェアECC復旧",
    "Reallocated_Event_Count": "代替処理発生回数",
    "Percentage_Used": "SSD使用率",
    "Media_Errors": "メディアエラー",
    "Wear": "摩耗度",
    "ReadErrorsTotal": "読取エラー合計",
    "WriteErrorsTotal": "書込エラー合計",
    "Start_Stop_Count": "始動・停止回数",
    "Spin_Retry_Count": "スピンリトライ回数",
    "Raw_Read_Error_Rate": "リードエラー率",
    "Seek_Error_Rate": "シークエラー率",
    "Throughput_Performance": "スループット性能",
    "Spin_Up_Time": "スピンアップ時間",
}


def _run_ps(script: str) -> Any:
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    out = (result.stdout or "").strip()
    if not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def smartctl_available() -> bool:
    return shutil.which("smartctl") is not None


def is_elevated() -> bool:
    """True when running with administrator privileges (needed for WMI SMART)."""
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _smart_is_sparse(smart: dict[str, Any] | None) -> bool:
    """True when SMART payload lacks temp / POH / a real attribute table."""
    if not smart:
        return True
    table = smart.get("attribute_table") or []
    if smart.get("temperature_c") is None and smart.get("power_on_hours") is None:
        return True
    if len(table) < 3 and smart.get("source") == "storage_reliability":
        return True
    return False


def _smartctl_available() -> bool:
    return smartctl_available()


def _attr_status(current: int | None, threshold: int | None, when_failed: str | None) -> str:
    if when_failed and str(when_failed).strip() and str(when_failed).upper() not in ("", "-", "NONE"):
        return "FAIL"
    if current is not None and threshold is not None and threshold > 0 and current <= threshold:
        return "WARN"
    return "OK"


def _label_for(attr_id: str | None, name: str | None) -> str:
    if attr_id:
        key = f"{int(attr_id):02X}" if str(attr_id).isdigit() else str(attr_id).upper()
        if key in ATTR_LABELS_JA:
            return ATTR_LABELS_JA[key]
    if name and name in ATTR_LABELS_JA:
        return ATTR_LABELS_JA[name]
    return name or (f"ID {attr_id}" if attr_id else "不明")


def _row_dict(
    *,
    attr_id: str | int | None = None,
    name: str | None = None,
    current: int | None = None,
    worst: int | None = None,
    threshold: int | None = None,
    raw: Any = None,
    when_failed: str | None = None,
    flags: str | None = None,
) -> dict[str, Any]:
    aid = None
    if attr_id is not None:
        try:
            aid = f"{int(attr_id):02X}"
        except (TypeError, ValueError):
            aid = str(attr_id)
    status = _attr_status(current, threshold, when_failed)
    return {
        "id": aid,
        "name": name,
        "label_ja": _label_for(aid, name),
        "current": current,
        "worst": worst,
        "threshold": threshold,
        "raw": raw,
        "when_failed": when_failed or "-",
        "flags": flags,
        "status": status,
    }


def _parse_smartctl_text_table(text: str) -> list[dict[str, Any]]:
    """Parse classic `smartctl -A` attribute table."""
    rows: list[dict[str, Any]] = []
    # ID# ATTRIBUTE_NAME FLAG VALUE WORST THRESH TYPE UPDATED WHEN_FAILED RAW_VALUE
    pattern = re.compile(
        r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\S+\s+\S+\s+(\S+)\s+(.+?)\s*$",
        re.M,
    )
    for m in pattern.finditer(text):
        raw_text = m.group(8).strip()
        raw_num = None
        num_m = re.match(r"(\d+)", raw_text)
        if num_m:
            raw_num = int(num_m.group(1))
        rows.append(
            _row_dict(
                attr_id=int(m.group(1)),
                name=m.group(2),
                flags=m.group(3),
                current=int(m.group(4)),
                worst=int(m.group(5)),
                threshold=int(m.group(6)),
                when_failed=m.group(7),
                raw=raw_num if raw_num is not None else raw_text,
            )
        )
    return rows


def _parse_smartctl(text: str) -> dict[str, Any]:
    smart: dict[str, Any] = {"source": "smartctl", "attribute_table": [], "attributes": {}}
    table = _parse_smartctl_text_table(text)
    smart["attribute_table"] = table
    for row in table:
        if row.get("name"):
            smart["attributes"][row["name"]] = row.get("raw")

    temp = re.search(r"Temperature_Celsius.*?(\d+)\s*(?:\(|$)", text, re.I)
    if not temp:
        temp = re.search(r"Current Drive Temperature:\s*(\d+)", text, re.I)
    if temp:
        smart["temperature_c"] = int(temp.group(1))

    poh = re.search(r"Power_On_Hours.*?(\d+)\s*$", text, re.M | re.I)
    if not poh:
        poh = re.search(r"Power on Hours:\s*(\d+)", text, re.I)
    if poh:
        smart["power_on_hours"] = int(poh.group(1))

    for name in (
        "Reallocated_Sector_Ct",
        "Current_Pending_Sector",
        "Offline_Uncorrectable",
        "UDMA_CRC_Error_Count",
        "Reported_Uncorrect",
    ):
        if name not in smart["attributes"]:
            m = re.search(rf"{name}\s+.*?\s+(\d+)\s*$", text, re.M | re.I)
            if m:
                smart["attributes"][name] = int(m.group(1))

    m = re.search(r"Percentage Used:\s*(\d+)%", text, re.I)
    if m:
        smart["attributes"]["Percentage_Used"] = int(m.group(1))
    m = re.search(r"Media and Data Integrity Errors:\s*(\d+)", text, re.I)
    if m:
        smart["attributes"]["Media_Errors"] = int(m.group(1))

    health = re.search(r"SMART overall-health self-assessment test result:\s*(\w+)", text, re.I)
    if health:
        smart["overall"] = health.group(1)
    else:
        nvme_health = re.search(r"SMART overall-health.*?:\s*(\w+)", text, re.I)
        if nvme_health:
            smart["overall"] = nvme_health.group(1)

    # Fill temp / hours from table if missing
    for row in table:
        if row.get("name") == "Temperature_Celsius" and "temperature_c" not in smart:
            try:
                smart["temperature_c"] = int(row["raw"])
            except (TypeError, ValueError):
                pass
        if row.get("name") == "Power_On_Hours" and "power_on_hours" not in smart:
            try:
                smart["power_on_hours"] = int(row["raw"])
            except (TypeError, ValueError):
                pass

    _merge_identity(smart, _parse_identity_from_text(text))
    return smart


def _gbps_to_sata_mode(gbps: float | None) -> str | None:
    if gbps is None:
        return None
    # CrystalDiskInfo 風: 1.5→SATA/150, 3.0→SATA/300, 6.0→SATA/600
    code = int(round(gbps * 100))
    if code <= 0:
        return None
    return f"SATA/{code}"


def _parse_gbps(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([\d.]+)\s*Gb/?s", text, re.I)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_identity_from_text(text: str) -> dict[str, Any]:
    """smartctl -i / -a のテキストから CrystalDiskInfo 相当の識別情報を拾う。"""
    ident: dict[str, Any] = {}
    features: list[str] = []

    m = re.search(r"ATA Version is:\s*(.+)", text, re.I)
    if m:
        ident["ata_standard"] = m.group(1).strip()
    m = re.search(r"SATA Version is:\s*(.+)", text, re.I)
    if m:
        line = m.group(1).strip()
        ident["sata_version"] = line
        cur = re.search(r"current:\s*([\d.]+)\s*Gb/?s", line, re.I)
        if cur:
            try:
                ident["transfer_mode"] = _gbps_to_sata_mode(float(cur.group(1)))
            except ValueError:
                pass
        elif not ident.get("transfer_mode"):
            ident["transfer_mode"] = _gbps_to_sata_mode(_parse_gbps(line))
    m = re.search(r"Rotation Rate:\s*(.+)", text, re.I)
    if m:
        rr = m.group(1).strip()
        if re.search(r"Solid State|SSD|0\s*rpm", rr, re.I):
            ident["rotation_rate"] = 0
            ident["rotation_label"] = "SSD（回転なし）"
        else:
            num = re.search(r"(\d+)", rr)
            if num:
                ident["rotation_rate"] = int(num.group(1))
                ident["rotation_label"] = f"{num.group(1)} rpm"
            else:
                ident["rotation_label"] = rr
    m = re.search(r"Form Factor:\s*(.+)", text, re.I)
    if m:
        ident["form_factor"] = m.group(1).strip()
    m = re.search(r"Buffer Size:\s*(.+)", text, re.I)
    if m:
        buf = m.group(1).strip()
        if re.search(r"unavailable|unknown|---|N/?A", buf, re.I):
            ident["buffer_size_kb"] = None
        else:
            num = re.search(r"([\d.]+)", buf)
            if num:
                try:
                    # 単位が bytes の場合もあるが、多くは kBytes
                    val = float(num.group(1))
                    if re.search(r"byte", buf, re.I) and not re.search(r"k", buf, re.I):
                        val = val / 1024.0
                    ident["buffer_size_kb"] = int(val)
                except ValueError:
                    pass
    m = re.search(r"NV Cache Size:\s*(.+)", text, re.I)
    if m:
        nv = m.group(1).strip()
        if not re.search(r"unavailable|unknown|---|N/?A", nv, re.I):
            ident["nv_cache_size"] = nv

    if re.search(r"SMART support is:\s*Available", text, re.I) or re.search(
        r"SMART support is:\s*Enabled", text, re.I
    ):
        features.append("S.M.A.R.T.")
    if re.search(r"48[- ]bit\s+(Address|LBA)|LBA\s*48", text, re.I):
        features.append("48bit LBA")
    if re.search(r"Advanced Power Management|\bAPM\b", text, re.I):
        features.append("APM")
    if re.search(r"Automatic Acoustic Management|\bAAM\b", text, re.I):
        features.append("AAM")
    if re.search(r"\bNCQ\b|Native Command Queuing", text, re.I):
        features.append("NCQ")
    if re.search(r"\bTRIM\b|Deterministic.*Trim|Data Set Management", text, re.I):
        features.append("TRIM")
    if re.search(r"Device supports DSM|TRIM supported", text, re.I):
        if "TRIM" not in features:
            features.append("TRIM")

    # インターフェース表記
    if ident.get("sata_version") or ident.get("transfer_mode"):
        ident["interface"] = "Serial ATA"
    elif re.search(r"NVMe", text, re.I):
        ident["interface"] = "NVM Express"
    elif re.search(r"Transport protocol:\s*SAS", text, re.I):
        ident["interface"] = "SAS"

    if features:
        # 順序を CrystalDiskInfo 風にそろえる
        order = ["S.M.A.R.T.", "48bit LBA", "APM", "AAM", "NCQ", "TRIM"]
        ordered = [f for f in order if f in features]
        for f in features:
            if f not in ordered:
                ordered.append(f)
        ident["features"] = ordered
        ident["features_text"] = ", ".join(ordered)

    return ident


def _identity_from_smartctl_json(data: dict[str, Any]) -> dict[str, Any]:
    """smartctl -j の JSON から識別情報を抽出する。"""
    ident: dict[str, Any] = {}
    features: list[str] = []

    ata = data.get("ata_version")
    if isinstance(ata, dict) and ata.get("string"):
        ident["ata_standard"] = str(ata["string"]).strip()
    elif isinstance(ata, str) and ata.strip():
        ident["ata_standard"] = ata.strip()

    sata = data.get("sata_version")
    if isinstance(sata, dict) and sata.get("string"):
        ident["sata_version"] = str(sata["string"]).strip()
    elif isinstance(sata, str) and sata.strip():
        ident["sata_version"] = sata.strip()

    speed = data.get("interface_speed") or {}
    current = speed.get("current") if isinstance(speed, dict) else None
    if isinstance(current, dict):
        cur_str = current.get("string")
        units = current.get("units_per_second")
        gbps = _parse_gbps(str(cur_str) if cur_str else None)
        if gbps is None and isinstance(units, (int, float)):
            # units_per_second が bit/s の場合もあるが、smartctl はしばしば Gb/s 文字列を持つ
            try:
                # 典型: 6000000000 → 6.0 Gb/s
                if units >= 1_000_000_000:
                    gbps = float(units) / 1_000_000_000.0
            except Exception:
                gbps = None
        mode = _gbps_to_sata_mode(gbps)
        if mode:
            ident["transfer_mode"] = mode

    device = data.get("device") or {}
    protocol = str(device.get("protocol") or "").upper()
    if protocol in ("ATA", "SAT", "USB"):
        ident["interface"] = "Serial ATA"
    elif protocol == "NVME":
        ident["interface"] = "NVM Express"
    elif protocol:
        ident["interface"] = protocol

    rr = data.get("rotation_rate")
    if rr is not None:
        try:
            rr_i = int(rr)
            ident["rotation_rate"] = rr_i
            ident["rotation_label"] = "SSD（回転なし）" if rr_i == 0 else f"{rr_i} rpm"
        except (TypeError, ValueError):
            pass

    if data.get("form_factor"):
        ident["form_factor"] = data.get("form_factor")

    smart_support = data.get("smart_support") or {}
    if smart_support.get("available") or smart_support.get("enabled"):
        features.append("S.M.A.R.T.")

    # 能力フラグ（ある範囲で）
    caps = ((data.get("ata_smart_data") or {}).get("capabilities")) or {}
    if caps.get("attribute_autosave_enabled") is not None and "S.M.A.R.T." not in features:
        features.append("S.M.A.R.T.")

    trim = data.get("ata_device_statistics") or data.get("trim") or {}
    if isinstance(trim, dict) and trim:
        # TRIM 関連の統計やフラグがあれば
        if any("trim" in str(k).lower() for k in trim.keys()):
            features.append("TRIM")
    if data.get("nvme_smart_health_information_log") is not None:
        if "TRIM" not in features:
            features.append("TRIM")
        if "S.M.A.R.T." not in features:
            features.append("S.M.A.R.T.")

    # smartctl JSON に ncq 明示がある場合
    for key in ("ncq", "sata_ncq", "native_command_queueing"):
        if data.get(key):
            features.append("NCQ")
            break

    # 48bit LBA はほぼ現行 HDD/SSD で前提。user_capacity が大きい場合に付与
    capacity = ((data.get("user_capacity") or {}).get("bytes")) or 0
    try:
        if int(capacity) >= 137_438_953_472:  # > 128 GiB 相当なら 48bit LBA が実質必須
            features.append("48bit LBA")
    except (TypeError, ValueError):
        pass

    if features:
        order = ["S.M.A.R.T.", "48bit LBA", "APM", "AAM", "NCQ", "TRIM"]
        ordered = [f for f in order if f in features]
        for f in features:
            if f not in ordered:
                ordered.append(f)
        ident["features"] = ordered
        ident["features_text"] = ", ".join(ordered)

    return ident


def _merge_identity(target: dict[str, Any], identity: dict[str, Any]) -> None:
    for key, value in identity.items():
        if value is None or value == "" or value == []:
            continue
        if key == "features" and target.get("features"):
            # 和集合
            merged = list(dict.fromkeys([*(target.get("features") or []), *value]))
            order = ["S.M.A.R.T.", "48bit LBA", "APM", "AAM", "NCQ", "TRIM"]
            ordered = [f for f in order if f in merged]
            for f in merged:
                if f not in ordered:
                    ordered.append(f)
            target["features"] = ordered
            target["features_text"] = ", ".join(ordered)
            continue
        if target.get(key) in (None, "", [], "----"):
            target[key] = value


def _normalize_smartctl_json(data: dict[str, Any]) -> dict[str, Any]:
    smart: dict[str, Any] = {
        "source": "smartctl",
        "attributes": {},
        "attribute_table": [],
        "model_family": (data.get("model_family") or None),
        "firmware": (data.get("firmware_version") or None),
        "serial": (data.get("serial_number") or None),
        "form_factor": (data.get("form_factor") or None),
        "rotation_rate": data.get("rotation_rate"),
        "logical_block_size": (data.get("logical_block_size") or None),
        "user_capacity_bytes": ((data.get("user_capacity") or {}).get("bytes")),
    }
    _merge_identity(smart, _identity_from_smartctl_json(data))

    status = (data.get("smart_status") or {}).get("passed")
    if status is True:
        smart["overall"] = "PASSED"
    elif status is False:
        smart["overall"] = "FAILED"

    temp = data.get("temperature") or {}
    if "current" in temp:
        smart["temperature_c"] = temp["current"]

    ata = data.get("ata_smart_attributes") or {}
    table = ata.get("table") or []
    for row in table:
        name = row.get("name")
        raw = (row.get("raw") or {}).get("value")
        raw_string = (row.get("raw") or {}).get("string")
        current = row.get("value")
        worst = row.get("worst")
        threshold = row.get("thresh")
        when_failed = row.get("when_failed") or "-"
        flags = None
        flag_obj = row.get("flags") or {}
        if flag_obj:
            flags = ",".join(k for k, v in flag_obj.items() if v is True and k != "value")

        entry = _row_dict(
            attr_id=row.get("id"),
            name=name,
            current=current,
            worst=worst,
            threshold=threshold,
            raw=raw if raw is not None else raw_string,
            when_failed=when_failed,
            flags=flags,
        )
        smart["attribute_table"].append(entry)
        if name is not None and raw is not None:
            smart["attributes"][name] = raw
        if name == "Power_On_Hours" and raw is not None:
            smart["power_on_hours"] = raw
        if name == "Temperature_Celsius" and raw is not None and "temperature_c" not in smart:
            # raw often encodes temp in low byte
            try:
                smart["temperature_c"] = int(raw) & 0xFF
            except (TypeError, ValueError):
                pass

    nvme = data.get("nvme_smart_health_information_log") or {}
    if nvme:
        if "temperature" in nvme:
            smart["temperature_c"] = nvme["temperature"]
        if "power_on_hours" in nvme:
            smart["power_on_hours"] = nvme["power_on_hours"]
        if "power_cycles" in nvme:
            smart["power_cycles"] = nvme["power_cycles"]
        if "unsafe_shutdowns" in nvme:
            smart["unsafe_shutdowns"] = nvme["unsafe_shutdowns"]
        if "percentage_used" in nvme:
            smart["attributes"]["Percentage_Used"] = nvme["percentage_used"]
        if "media_errors" in nvme:
            smart["attributes"]["Media_Errors"] = nvme["media_errors"]
        if "available_spare" in nvme:
            smart["available_spare"] = nvme["available_spare"]
        if "data_units_written" in nvme:
            smart["data_units_written"] = nvme["data_units_written"]
        if "data_units_read" in nvme:
            smart["data_units_read"] = nvme["data_units_read"]

        # Represent NVMe log as pseudo attribute table
        for key, label in (
            ("percentage_used", "Percentage_Used"),
            ("available_spare", "Available_Spare"),
            ("media_errors", "Media_Errors"),
            ("num_err_log_entries", "Error_Log_Entries"),
            ("controller_busy_time", "Controller_Busy_Time"),
            ("power_cycles", "Power_Cycles"),
            ("power_on_hours", "Power_On_Hours"),
            ("unsafe_shutdowns", "Unsafe_Shutdowns"),
            ("data_units_written", "Data_Units_Written"),
            ("data_units_read", "Data_Units_Read"),
            ("host_reads", "Host_Reads"),
            ("host_writes", "Host_Writes"),
            ("temperature", "Temperature_Celsius"),
        ):
            if key in nvme:
                smart["attribute_table"].append(
                    _row_dict(name=label, raw=nvme[key], current=None, threshold=None)
                )

    # Power cycle from ATA attributes
    for row in smart["attribute_table"]:
        if row.get("name") == "Power_Cycle_Count" and row.get("raw") is not None:
            smart["power_cycles"] = row["raw"]

    return smart


def _smartctl_identity_text(index: int) -> str:
    """バッファサイズ・対応機能など、JSON に出にくい項目用の -i テキスト。"""
    try:
        result = subprocess.run(
            ["smartctl", "-i", f"/dev/pd{index}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return result.stdout or ""
    except Exception:
        return ""


def _collect_smart_for_index(index: int) -> dict[str, Any] | None:
    if not _smartctl_available():
        return None
    try:
        result = subprocess.run(
            ["smartctl", "-a", "-j", f"/dev/pd{index}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        out = result.stdout.strip()
        # smartctl may return non-zero even with usable JSON
        if out.startswith("{"):
            try:
                data = json.loads(out)
                smart = _normalize_smartctl_json(data)
                # CrystalDiskInfo 相当の Buffer / Features をテキストからも補完
                ident_text = _smartctl_identity_text(index)
                if ident_text.strip():
                    _merge_identity(smart, _parse_identity_from_text(ident_text))
                return smart
            except json.JSONDecodeError:
                pass

        result2 = subprocess.run(
            ["smartctl", "-A", "-H", "-i", f"/dev/pd{index}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        text = (result2.stdout or "") + "\n" + (result.stdout or "")
        if text.strip():
            return _parse_smartctl(text)
    except Exception:
        return None
    return None


def _reliability_counters() -> dict[str, dict[str, Any]]:
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$out = @()
Get-PhysicalDisk | ForEach-Object {
  $pd = $_
  $c = Get-StorageReliabilityCounter -PhysicalDisk $pd
  if ($c) {
    $out += [PSCustomObject]@{
      DeviceId = [string]$pd.DeviceId
      Temperature = $c.Temperature
      TemperatureMax = $c.TemperatureMax
      Wear = $c.Wear
      ReadErrorsTotal = $c.ReadErrorsTotal
      ReadErrorsCorrected = $c.ReadErrorsCorrected
      ReadErrorsUncorrected = $c.ReadErrorsUncorrected
      WriteErrorsTotal = $c.WriteErrorsTotal
      WriteErrorsCorrected = $c.WriteErrorsCorrected
      WriteErrorsUncorrected = $c.WriteErrorsUncorrected
      ManufactureDate = [string]$c.ManufactureDate
      StartStopCycleCount = $c.StartStopCycleCount
      PowerOnHours = $c.PowerOnHours
    }
  }
}
$out | ConvertTo-Json -Compress -Depth 4
"""
    data = _run_ps(script)
    if isinstance(data, dict):
        data = [data]
    result: dict[str, dict[str, Any]] = {}
    for row in data or []:
        did = str(row.get("DeviceId", ""))
        attrs = {
            k: v
            for k, v in {
                "Wear": row.get("Wear"),
                "ReadErrorsTotal": row.get("ReadErrorsTotal"),
                "ReadErrorsCorrected": row.get("ReadErrorsCorrected"),
                "ReadErrorsUncorrected": row.get("ReadErrorsUncorrected"),
                "WriteErrorsTotal": row.get("WriteErrorsTotal"),
                "WriteErrorsCorrected": row.get("WriteErrorsCorrected"),
                "WriteErrorsUncorrected": row.get("WriteErrorsUncorrected"),
                "StartStopCycleCount": row.get("StartStopCycleCount"),
                "TemperatureMax": row.get("TemperatureMax"),
            }.items()
            if v is not None
        }
        table = [_row_dict(name=name, raw=val) for name, val in attrs.items()]
        if row.get("PowerOnHours") is not None:
            table.insert(0, _row_dict(name="Power_On_Hours", raw=row.get("PowerOnHours")))
        if row.get("Temperature") is not None:
            table.insert(0, _row_dict(name="Temperature_Celsius", raw=row.get("Temperature")))

        result[did] = {
            "source": "storage_reliability",
            "temperature_c": row.get("Temperature"),
            "power_on_hours": row.get("PowerOnHours"),
            "manufacture_date": row.get("ManufactureDate") or None,
            "attributes": attrs,
            "attribute_table": table,
            "overall": None,
            "note": "Windows 信頼性カウンタのみ。フルSMARTは管理者権限 + smartctl で取得できます。",
        }
    return result


# Common SMART attribute ID -> name (ATA)
_SMART_ID_NAMES: dict[int, str] = {
    1: "Raw_Read_Error_Rate",
    2: "Throughput_Performance",
    3: "Spin_Up_Time",
    4: "Start_Stop_Count",
    5: "Reallocated_Sector_Ct",
    7: "Seek_Error_Rate",
    9: "Power_On_Hours",
    10: "Spin_Retry_Count",
    12: "Power_Cycle_Count",
    184: "End-to-End_Error",
    187: "Reported_Uncorrect",
    188: "Command_Timeout",
    190: "Airflow_Temperature_Cel",
    191: "G-Sense_Error_Rate",
    192: "Power-Off_Retract_Count",
    193: "Load_Cycle_Count",
    194: "Temperature_Celsius",
    196: "Reallocated_Event_Count",
    197: "Current_Pending_Sector",
    198: "Offline_Uncorrectable",
    199: "UDMA_CRC_Error_Count",
    200: "Multi_Zone_Error_Rate",
    241: "Total_LBAs_Written",
    242: "Total_LBAs_Read",
}


def _parse_wmi_vendor_specific(vendor: list[int]) -> list[dict[str, Any]]:
    """Parse MSStorageDriver_FailurePredictData.VendorSpecific (512 bytes)."""
    if not vendor or len(vendor) < 2:
        return []
    rows: list[dict[str, Any]] = []
    # Attributes typically start at offset 2, 12 bytes each, up to 30 entries
    offset = 2
    for _ in range(30):
        if offset + 12 > len(vendor):
            break
        attr_id = int(vendor[offset])
        if attr_id == 0:
            offset += 12
            continue
        current = int(vendor[offset + 3])
        worst = int(vendor[offset + 4])
        raw_bytes = vendor[offset + 5 : offset + 11]
        raw = 0
        for i, b in enumerate(raw_bytes):
            raw |= (int(b) & 0xFF) << (8 * i)
        name = _SMART_ID_NAMES.get(attr_id, f"Attribute_{attr_id}")
        rows.append(
            _row_dict(
                attr_id=attr_id,
                name=name,
                current=current,
                worst=worst,
                threshold=None,
                raw=raw,
            )
        )
        offset += 12
    return rows


def _wmi_smart_by_model() -> dict[str, dict[str, Any]]:
    """Collect SMART via WMI (often requires elevation). Keyed by normalized model."""
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$out = @()
$statusMap = @{}
Get-CimInstance -Namespace root\wmi -ClassName MSStorageDriver_FailurePredictStatus | ForEach-Object {
  $statusMap[$_.InstanceName] = $_
}
Get-CimInstance -Namespace root\wmi -ClassName MSStorageDriver_FailurePredictData | ForEach-Object {
  $st = $statusMap[$_.InstanceName]
  $out += [PSCustomObject]@{
    InstanceName = $_.InstanceName
    PredictFailure = if ($st) { [bool]$st.PredictFailure } else { $null }
    Reason = if ($st) { $st.Reason } else { $null }
    VendorSpecific = @($_.VendorSpecific)
  }
}
$out | ConvertTo-Json -Compress -Depth 6
"""
    data = _run_ps(script)
    if isinstance(data, dict):
        data = [data]
    result: dict[str, dict[str, Any]] = {}
    for row in data or []:
        instance = row.get("InstanceName") or ""
        vendor = row.get("VendorSpecific") or []
        # InstanceName often contains model-ish path; keep raw list for matching later
        table = _parse_wmi_vendor_specific(vendor)
        attrs = {r["name"]: r["raw"] for r in table if r.get("name")}
        smart: dict[str, Any] = {
            "source": "wmi",
            "instance_name": instance,
            "attributes": attrs,
            "attribute_table": table,
            "overall": "FAILED" if row.get("PredictFailure") else "PASSED",
            "note": "WMI SMART（管理者権限で取得）。smartctl の方が詳細です。",
        }
        for r in table:
            if r.get("name") == "Temperature_Celsius" and r.get("raw") is not None:
                smart["temperature_c"] = int(r["raw"]) & 0xFF
            if r.get("name") == "Airflow_Temperature_Cel" and "temperature_c" not in smart:
                smart["temperature_c"] = int(r["raw"]) & 0xFF
            if r.get("name") == "Power_On_Hours" and r.get("raw") is not None:
                smart["power_on_hours"] = int(r["raw"])
            if r.get("name") == "Power_Cycle_Count" and r.get("raw") is not None:
                smart["power_cycles"] = int(r["raw"])
        # Index by instance for fuzzy match
        result[instance.lower()] = smart
    return result


def _win32_disk_drives() -> dict[str, dict[str, Any]]:
    script = r"""
Get-CimInstance Win32_DiskDrive | Select-Object `
  @{N='Index';E={[string]$_.Index}},
  Model, SerialNumber, FirmwareRevision, InterfaceType, Status, MediaType,
  @{N='SizeBytes';E={[int64]$_.Size}},
  PNPDeviceID, Partitions |
  ConvertTo-Json -Compress -Depth 4
"""
    data = _run_ps(script)
    if isinstance(data, dict):
        data = [data]
    return {str(row.get("Index")): row for row in (data or [])}


def _normalize_pnp(pnp: str | None) -> str:
    if not pnp:
        return ""
    # WMI InstanceName often ends with _0; PNPDeviceID does not
    return pnp.lower().rstrip().removesuffix("_0")


def _match_wmi_smart(
    wmi_map: dict[str, dict[str, Any]],
    model: str,
    serial: str | None,
    pnp_device_id: str | None = None,
) -> dict[str, Any] | None:
    if not wmi_map:
        return None

    # 1) Best: match Win32 PNPDeviceID to WMI InstanceName
    pnp = _normalize_pnp(pnp_device_id)
    if pnp:
        for key, smart in wmi_map.items():
            if _normalize_pnp(key) == pnp or pnp in key or key.startswith(pnp):
                return smart

    # 2) Model tokens (handles "WDC WD20EZRZ-..." vs "ven_wdc&prod_wd20ezrz-...")
    model_l = (model or "").lower()
    tokens = [t for t in model_l.replace("-", " ").replace("_", " ").split() if len(t) >= 3]
    if tokens:
        for key, smart in wmi_map.items():
            key_compact = key.replace("&", " ").replace("_", " ").replace("\\", " ")
            if all(t in key_compact for t in tokens):
                return smart
            # also try contiguous model without spaces
            compact_model = "".join(tokens)
            if compact_model and compact_model in key.replace("_", "").replace("&", "").replace("\\", ""):
                return smart

    # 3) Serial
    serial_l = (serial or "").strip().lower()
    if serial_l:
        for key, smart in wmi_map.items():
            if serial_l in key:
                return smart

    return None


def _flag_critical_raw(smart: dict[str, Any]) -> dict[str, Any]:
    """Mark caution when critical SMART raw counters are non-zero (CrystalDiskInfo-like)."""
    critical = {
        "Reallocated_Sector_Ct",
        "Current_Pending_Sector",
        "Offline_Uncorrectable",
        "Reported_Uncorrect",
    }
    caution = False
    for row in smart.get("attribute_table") or []:
        name = row.get("name")
        raw = row.get("raw")
        if name in critical and raw not in (None, 0, "0"):
            try:
                if int(raw) > 0:
                    row["status"] = "WARN"
                    caution = True
            except (TypeError, ValueError):
                pass
    if caution and smart.get("health_meter") in (None, "Good", "Unknown"):
        smart["health_meter"] = "Caution"
        if (smart.get("overall") or "").upper() == "PASSED":
            smart["overall"] = "CAUTION"
    return smart


def _enrich_summary(smart: dict[str, Any]) -> dict[str, Any]:
    """Add CrystalDiskInfo-like summary fields."""
    poh = smart.get("power_on_hours")
    if poh is not None:
        try:
            hours = int(poh)
            smart["power_on_hours"] = hours
            smart["power_on_days"] = round(hours / 24, 1)
            smart["power_on_years"] = round(hours / 8760, 2)
        except (TypeError, ValueError):
            pass

    overall = (smart.get("overall") or "").upper()
    table = smart.get("attribute_table") or []
    fails = sum(1 for r in table if r.get("status") == "FAIL")
    warns = sum(1 for r in table if r.get("status") == "WARN")
    if overall == "FAILED" or fails:
        smart["health_meter"] = "Bad"
    elif warns or (overall and overall not in ("PASSED", "OK", "")):
        smart["health_meter"] = "Caution"
    elif table or overall == "PASSED":
        smart["health_meter"] = "Good"
    elif smart.get("source") in ("none", None) and not table:
        smart["health_meter"] = "Unknown"
    else:
        smart["health_meter"] = "Unknown"

    smart["smartctl_available"] = _smartctl_available()
    return smart


def collect_disks() -> list[dict[str, Any]]:
    script = r"""
Get-PhysicalDisk | Select-Object `
  @{N='DeviceId';E={[string]$_.DeviceId}},
  FriendlyName, Model, SerialNumber, MediaType, BusType,
  HealthStatus, OperationalStatus, FirmwareVersion, SpindleSpeed,
  @{N='SizeBytes';E={[int64]$_.Size}},
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}} |
  ConvertTo-Json -Compress -Depth 4
"""
    data = _run_ps(script)
    if isinstance(data, dict):
        data = [data]
    if not data:
        return []

    reliability = _reliability_counters()
    wmi_map = _wmi_smart_by_model()
    win32 = _win32_disk_drives()
    disks: list[dict[str, Any]] = []

    for row in data:
        device_id = str(row.get("DeviceId", ""))
        model = row.get("Model") or row.get("FriendlyName") or "Unknown"
        bus = row.get("BusType")
        disk: dict[str, Any] = {
            "device_id": device_id,
            "model": model,
            "friendly_name": row.get("FriendlyName"),
            "serial": row.get("SerialNumber"),
            "media_type": row.get("MediaType"),
            "bus_type": bus,
            "health_status": row.get("HealthStatus"),
            "operational_status": row.get("OperationalStatus"),
            "firmware": row.get("FirmwareVersion"),
            "size_bytes": row.get("SizeBytes"),
            "size_gb": row.get("SizeGB"),
            "smart": {},
        }
        # OS 側の推測（smartctl が取れないときの下書き）
        if bus:
            bus_l = str(bus).lower()
            if "nvme" in bus_l:
                disk["interface"] = "NVM Express"
            elif "sata" in bus_l or "ata" in bus_l:
                disk["interface"] = "Serial ATA"
            else:
                disk["interface"] = str(bus)
        spindle = row.get("SpindleSpeed")
        if spindle is not None:
            try:
                sp = int(spindle)
                disk["rotation_rate"] = sp
                disk["rotation_label"] = "SSD（回転なし）" if sp == 0 else f"{sp} rpm"
            except (TypeError, ValueError):
                pass

        w32 = win32.get(device_id)
        pnp = None
        if w32:
            disk["interface_type"] = w32.get("InterfaceType")
            if not disk.get("interface") and w32.get("InterfaceType"):
                iface = str(w32.get("InterfaceType"))
                disk["interface"] = "Serial ATA" if iface.upper() in ("IDE", "SCSI", "ATA") else iface
            disk["wmi_status"] = w32.get("Status")
            pnp = w32.get("PNPDeviceID")
            disk["pnp_device_id"] = pnp
            if not disk.get("serial"):
                disk["serial"] = (w32.get("SerialNumber") or "").strip() or None
            if not disk.get("firmware"):
                disk["firmware"] = w32.get("FirmwareRevision")

        try:
            idx = int(device_id)
            smart = _collect_smart_for_index(idx)
        except (TypeError, ValueError):
            smart = None

        rel = reliability.get(device_id)
        wmi_smart = _match_wmi_smart(
            wmi_map, model, disk.get("serial"), pnp_device_id=pnp
        )

        # Prefer richest source: smartctl > full WMI table > reliability counters
        if not smart:
            if wmi_smart and not _smart_is_sparse(wmi_smart):
                smart = dict(wmi_smart)
                if rel:
                    for key in ("temperature_c", "power_on_hours"):
                        if smart.get(key) is None and rel.get(key) is not None:
                            smart[key] = rel[key]
            elif rel:
                smart = dict(rel)
                # Overlay WMI when reliability is sparse (e.g. Wear:0 only)
                if wmi_smart and _smart_is_sparse(smart):
                    merged = dict(wmi_smart)
                    for key in ("temperature_c", "power_on_hours", "power_cycles"):
                        if merged.get(key) is None and smart.get(key) is not None:
                            merged[key] = smart[key]
                    smart = merged
            elif wmi_smart:
                smart = dict(wmi_smart)

        elevated = is_elevated()
        if not smart:
            note = (
                "詳細SMART未取得。"
                + (
                    "管理者権限でも取得できませんでした。smartmontools（smartctl）の導入を検討してください。"
                    if elevated
                    else (
                        "温度・通電時間は管理者として起動すると WMI SMART で取得できます。"
                        "トレイの「管理者として再起動」、または同梱の run_as_admin.bat を使ってください。"
                    )
                )
            )
            smart = {
                "source": "none",
                "attributes": {},
                "attribute_table": [],
                "note": note,
                "needs_elevation": not elevated,
            }

        if not smart.get("serial"):
            smart["serial"] = disk["serial"]
        if not smart.get("firmware"):
            smart["firmware"] = disk["firmware"]

        # If OS health is Healthy and we have no SMART table, still show basic meter from OS
        if smart.get("source") == "none" and (disk.get("health_status") or "").lower() == "healthy":
            smart["overall"] = "PASSED"
            smart["health_meter"] = "Good"
            if not elevated:
                smart["needs_elevation"] = True
                smart["note"] = (
                    "OS上は Healthy ですが、属性テーブル・温度は未取得です。"
                    "管理者として再起動すると WMI SMART（温度・通電時間など）を取得できます。"
                )
            else:
                smart["note"] = (
                    "OS上は Healthy。属性テーブルは未取得です。"
                    "smartctl があるとさらに詳細を取得できます。"
                )

        smart = _enrich_summary(smart)
        smart = _flag_critical_raw(smart)

        # CrystalDiskInfo 風の識別項目をディスク直下にも展開（UI 用）
        for key in (
            "interface",
            "transfer_mode",
            "ata_standard",
            "sata_version",
            "features",
            "features_text",
            "buffer_size_kb",
            "nv_cache_size",
            "rotation_rate",
            "rotation_label",
            "form_factor",
        ):
            if smart.get(key) is not None and disk.get(key) in (None, "", []):
                disk[key] = smart[key]
        if not disk.get("firmware"):
            disk["firmware"] = smart.get("firmware")
        if not disk.get("serial"):
            disk["serial"] = smart.get("serial")

        disk["smart"] = smart
        disks.append(disk)

    return disks
