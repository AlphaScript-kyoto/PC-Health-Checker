from __future__ import annotations

import json
import subprocess
from typing import Any


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
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    out = (result.stdout or "").strip()
    if not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def collect_volumes() -> list[dict[str, Any]]:
    """Collect logical volumes and map to physical disk DeviceIds when possible."""
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$out = @()
Get-Volume | Where-Object { $_.DriveLetter } | ForEach-Object {
  $vol = $_
  $letter = [string]$vol.DriveLetter
  $part = Get-Partition -DriveLetter $letter -ErrorAction SilentlyContinue | Select-Object -First 1
  $diskNums = @()
  if ($part) {
    $diskNums += [string]$part.DiskNumber
  }
  # Map DiskNumber -> PhysicalDisk.DeviceId (often same)
  $physIds = @()
  foreach ($n in $diskNums) {
    $pd = Get-PhysicalDisk | Where-Object { [string]$_.DeviceId -eq $n -or [string]$_.DeviceId -eq ([string]$n) }
    if (-not $pd) {
      $d = Get-Disk -Number ([int]$n) -ErrorAction SilentlyContinue
      if ($d) {
        $pd = Get-PhysicalDisk | Where-Object { $_.FriendlyName -eq $d.FriendlyName } | Select-Object -First 1
      }
    }
    if ($pd) { $physIds += [string]$pd.DeviceId }
    else { $physIds += [string]$n }
  }
  $size = [double]$vol.Size
  $free = [double]$vol.SizeRemaining
  $freePct = if ($size -gt 0) { [math]::Round(($free / $size) * 100, 2) } else { 100 }
  $out += [PSCustomObject]@{
    Letter = $letter + ':'
    Label = $vol.FileSystemLabel
    FileSystem = $vol.FileSystem
    HealthStatus = [string]$vol.HealthStatus
    SizeGB = [math]::Round($size / 1GB, 1)
    FreeGB = [math]::Round($free / 1GB, 1)
    FreePct = $freePct
    PhysicalDiskIds = $physIds
  }
}
$out | ConvertTo-Json -Compress -Depth 5
"""
    data = _run_ps(script)
    if isinstance(data, dict):
        data = [data]
    volumes = []
    for row in data or []:
        volumes.append(
            {
                "letter": row.get("Letter"),
                "label": row.get("Label"),
                "file_system": row.get("FileSystem"),
                "health_status": row.get("HealthStatus"),
                "size_gb": row.get("SizeGB"),
                "free_gb": row.get("FreeGB"),
                "free_pct": row.get("FreePct"),
                "physical_disk_ids": row.get("PhysicalDiskIds") or [],
            }
        )
    return volumes
