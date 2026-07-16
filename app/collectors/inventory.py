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


# SMBIOSMemoryType -> human name (SMBIOS spec 7.18.2)
_MEMORY_TYPE_NAMES = {
    20: "DDR",
    21: "DDR2",
    24: "DDR3",
    26: "DDR4",
    27: "LPDDR",
    28: "LPDDR2",
    29: "LPDDR3",
    30: "LPDDR4",
    34: "DDR5",
    35: "LPDDR5",
}


def _memory_summary(modules: Any) -> str | None:
    """e.g. 'DDR4 16GB×2 3200MHz' from Win32_PhysicalMemory rows."""
    if not modules:
        return None
    if isinstance(modules, dict):
        modules = [modules]
    sizes: list[int] = []
    types: set[str] = set()
    speeds: set[int] = set()
    for m in modules:
        try:
            cap = int(m.get("Capacity") or 0)
        except (TypeError, ValueError):
            cap = 0
        if cap > 0:
            sizes.append(round(cap / (1024**3)))
        t = _MEMORY_TYPE_NAMES.get(m.get("SMBIOSMemoryType"))
        if t:
            types.add(t)
        spd = m.get("ConfiguredClockSpeed") or m.get("Speed")
        try:
            spd = int(spd)
        except (TypeError, ValueError):
            spd = 0
        if spd > 0:
            speeds.add(spd)
    if not sizes:
        return None
    from collections import Counter

    size_part = " + ".join(
        f"{size}GB×{count}" for size, count in sorted(Counter(sizes).items(), reverse=True)
    )
    parts = []
    if types:
        parts.append("/".join(sorted(types)))
    parts.append(size_part)
    if speeds:
        parts.append(f"{max(speeds)}MHz")
    return " ".join(parts)


def collect_inventory() -> dict[str, Any]:
    script = r"""
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed
$cs = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, LastBootUpTime
$dimms = @(Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
  [PSCustomObject]@{
    Capacity = [int64]$_.Capacity
    Speed = $_.Speed
    ConfiguredClockSpeed = $_.ConfiguredClockSpeed
    SMBIOSMemoryType = $_.SMBIOSMemoryType
  }
})
[PSCustomObject]@{
  CpuName = $cpu.Name
  Cores = $cpu.NumberOfCores
  LogicalProcessors = $cpu.NumberOfLogicalProcessors
  MaxClockMHz = $cpu.MaxClockSpeed
  Manufacturer = $cs.Manufacturer
  Model = $cs.Model
  TotalMemoryBytes = [int64]$cs.TotalPhysicalMemory
  MemoryModules = $dimms
  OsCaption = $os.Caption
  OsVersion = $os.Version
} | ConvertTo-Json -Compress -Depth 4
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
        "memory_summary": _memory_summary(data.get("MemoryModules")),
        "os_caption": data.get("OsCaption"),
        "os_version": data.get("OsVersion"),
    }
