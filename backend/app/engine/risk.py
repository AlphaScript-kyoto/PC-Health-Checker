from __future__ import annotations

from typing import Any

from app.config import OLD_DRIVE_HINTS

# Unknown は「問題なし」より優先する。Watch 以上の明確な問題があればそちらを採用する。
STATUS_ORDER = {"OK": 0, "Unknown": 1, "Watch": 2, "ReplaceSoon": 3, "Critical": 4}


def _worse(a: str, b: str) -> str:
    return a if STATUS_ORDER.get(a, 0) >= STATUS_ORDER.get(b, 0) else b


def evaluate(raw: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    warn_pct = float(settings.get("capacity_warn_pct", 10))
    crit_pct = float(settings.get("capacity_critical_pct", 5))

    disks_out: list[dict[str, Any]] = []
    volume_issues: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    disk_error = raw.get("disk_collection_error")
    overall = "Unknown" if disk_error else "OK"
    if disk_error:
        alerts.append(
            {
                "level": "Unknown",
                "title": "ディスク情報を取得できませんでした",
                "message": "PowerShellからの取得に失敗したため、判定は不明です。",
                "device_id": None,
                "kind": "disk",
            }
        )

    for vol in raw.get("volumes") or []:
        free_pct = vol.get("free_pct")
        if free_pct is None:
            continue
        level = "OK"
        if free_pct <= crit_pct:
            level = "Critical"
        elif free_pct <= warn_pct:
            level = "Watch"
        if level != "OK":
            issue = {
                "letter": vol.get("letter"),
                "free_pct": free_pct,
                "free_gb": vol.get("free_gb"),
                "size_gb": vol.get("size_gb"),
                "risk_level": level,
                "reason": f"{vol.get('letter')} の空き容量が {free_pct}%（{vol.get('free_gb')} GB）です",
            }
            volume_issues.append(issue)
            alerts.append(
                {
                    "level": level,
                    "title": f"容量不足: {vol.get('letter')}",
                    "message": issue["reason"],
                    "device_id": None,
                    "kind": "capacity",
                }
            )
            overall = _worse(overall, level)

    for d in raw.get("disks") or []:
        evaluated = dict(d)
        reasons: list[str] = []
        level = "OK"
        health = (d.get("os_health_status") or d.get("health_status") or "").strip().lower()
        smart = dict(d.get("smart") or {})
        attrs = smart.get("attributes") or {}

        # OS が返す状態。SMART の合否とは混ぜない。
        if health == "unhealthy":
            evaluated["os_health_status"] = "Unhealthy"
            level = _worse(level, "Critical")
            reasons.append(f"OS報告のディスク状態: {d.get('health_status')}")
        elif health == "warning":
            evaluated["os_health_status"] = "Warning"
            level = _worse(level, "ReplaceSoon")
            reasons.append(f"OS報告のディスク状態: {d.get('health_status')}")
        elif health == "healthy":
            evaluated["os_health_status"] = "Healthy"
        else:
            evaluated["os_health_status"] = "Unknown"
            level = _worse(level, "Unknown")
            reasons.append("OSのディスク状態を取得できませんでした")

        overall_smart = (smart.get("smart_status") or smart.get("overall") or "").upper()
        if overall_smart == "FAILED":
            evaluated["smart_status"] = "FAILED"
            level = _worse(level, "Critical")
            reasons.append("SMART自己診断が FAILED")
        elif overall_smart == "PASSED":
            evaluated["smart_status"] = "PASSED"
        elif overall_smart == "CAUTION":
            evaluated["smart_status"] = "CAUTION"
        else:
            # 未取得を合格にしない
            evaluated["smart_status"] = "UNKNOWN"
            smart["overall"] = "UNKNOWN"
            smart["smart_status"] = "UNKNOWN"
            if smart.get("health_meter") in (None, "", "Good"):
                smart["health_meter"] = "Unknown"

        realloc = attrs.get("Reallocated_Sector_Ct") or 0
        pending = attrs.get("Current_Pending_Sector") or 0
        uncorrect = attrs.get("Offline_Uncorrectable") or attrs.get("Reported_Uncorrect") or 0
        media_errors = attrs.get("Media_Errors") or 0
        wear = attrs.get("Wear") or attrs.get("Percentage_Used")

        if realloc and realloc > 0:
            level = _worse(level, "ReplaceSoon" if realloc < 50 else "Critical")
            reasons.append(f"代替処理済セクタ: {realloc}")
        if pending and pending > 0:
            level = _worse(level, "Critical")
            reasons.append(f"保留中セクタ: {pending}")
        if uncorrect and uncorrect > 0:
            level = _worse(level, "Critical")
            reasons.append(f"訂正不能セクタ: {uncorrect}")
        if media_errors and media_errors > 0:
            level = _worse(level, "ReplaceSoon")
            reasons.append(f"メディアエラー: {media_errors}")
        if wear is not None and wear >= 90:
            level = _worse(level, "ReplaceSoon" if wear < 95 else "Critical")
            reasons.append(f"SSD摩耗度: {wear}%")

        temp = smart.get("temperature_c")
        if temp is not None:
            try:
                t = int(temp)
                if t >= 60:
                    level = _worse(level, "Watch")
                    reasons.append(f"温度高め: {t}°C")
                if t >= 70:
                    level = _worse(level, "ReplaceSoon")
                    reasons.append(f"温度危険: {t}°C")
            except (TypeError, ValueError):
                pass

        poh = smart.get("power_on_hours")
        if poh is not None:
            try:
                hours = int(poh)
                years = hours / 8760
                if years >= 5:
                    level = _worse(level, "Watch")
                    reasons.append(f"通電時間約 {years:.1f} 年（{hours} h）")
                if years >= 8:
                    level = _worse(level, "ReplaceSoon")
            except (TypeError, ValueError):
                pass

        model = d.get("model") or ""
        for key, hint in OLD_DRIVE_HINTS.items():
            if key.upper() in model.upper():
                level = _worse(level, "ReplaceSoon")
                reasons.append(hint)
                break

        free_pct = d.get("free_pct")
        if free_pct is not None:
            if free_pct <= crit_pct:
                level = _worse(level, "Critical")
                reasons.append(f"関連ボリューム空き {free_pct}%")
            elif free_pct <= warn_pct:
                level = _worse(level, "Watch")
                reasons.append(f"関連ボリューム空き {free_pct}%")

        evaluated["smart"] = smart
        evaluated["risk_level"] = level
        evaluated["reasons"] = reasons
        evaluated["needs_replacement"] = level in ("ReplaceSoon", "Critical")
        disks_out.append(evaluated)
        overall = _worse(overall, level)

        if level != "OK":
            alerts.append(
                {
                    "level": level,
                    "title": (
                        f"ディスク状態は不明です: {model}"
                        if level == "Unknown"
                        else f"ディスク注意: {model}"
                    ),
                    "message": " / ".join(reasons) if reasons else level,
                    "device_id": d.get("device_id"),
                    "kind": "disk",
                }
            )

    replacement_targets = [d for d in disks_out if d.get("needs_replacement")]

    result = {
        "overall_status": overall,
        "inventory": raw.get("inventory") or {},
        "disks": disks_out,
        "volumes": raw.get("volumes") or [],
        "volume_issues": volume_issues,
        "alerts": alerts,
        "replacement_targets": replacement_targets,
        "elevated": bool(raw.get("elevated")),
        "smartctl_available": bool(raw.get("smartctl_available")),
    }
    if disk_error:
        result["message"] = "ディスク情報を取得できなかったため、判定は不明です。"
        result["disk_collection_error"] = str(disk_error)
    return result
