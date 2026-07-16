from __future__ import annotations

import json
import platform
import subprocess
from typing import Any

import psutil


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
        timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    out = (result.stdout or "").strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def collect_inventory() -> dict[str, Any]:
    script = r"""
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed
$cs = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, LastBootUpTime
[PSCustomObject]@{
  CpuName = $cpu.Name
  Cores = $cpu.NumberOfCores
  LogicalProcessors = $cpu.NumberOfLogicalProcessors
  MaxClockMHz = $cpu.MaxClockSpeed
  Manufacturer = $cs.Manufacturer
  Model = $cs.Model
  TotalMemoryBytes = [int64]$cs.TotalPhysicalMemory
  OsCaption = $os.Caption
  OsVersion = $os.Version
} | ConvertTo-Json -Compress
"""
    data = _run_ps(script)
    mem = psutil.virtual_memory()
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "cpu_name": data.get("CpuName") or platform.processor(),
        "cores": data.get("Cores"),
        "logical_processors": data.get("LogicalProcessors"),
        "max_clock_mhz": data.get("MaxClockMHz"),
        "manufacturer": data.get("Manufacturer"),
        "model": data.get("Model"),
        "total_memory_gb": round((data.get("TotalMemoryBytes") or mem.total) / (1024**3), 1),
        "memory_used_pct": mem.percent,
        "os_caption": data.get("OsCaption"),
        "os_version": data.get("OsVersion"),
    }
