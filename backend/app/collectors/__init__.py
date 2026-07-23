from __future__ import annotations

from app.collectors.capacity import collect_volumes
from app.collectors.disks import collect_disks, is_elevated, smartctl_available
from app.collectors.inventory import collect_inventory


def collect_all() -> dict:
    disks = collect_disks()
    volumes = collect_volumes()
    inventory = collect_inventory()
    elevated = is_elevated()

    # Attach volume free-space summary onto matching disks when possible
    vol_by_disk = {}
    for v in volumes:
        for did in v.get("physical_disk_ids") or []:
            vol_by_disk.setdefault(did, []).append(v)

    for d in disks:
        related = vol_by_disk.get(d["device_id"], [])
        if related:
            # Worst (lowest free %) among related volumes
            worst = min(related, key=lambda x: x.get("free_pct", 100))
            d["free_pct"] = worst.get("free_pct")
            d["volumes"] = [
                {
                    "letter": x.get("letter"),
                    "free_pct": x.get("free_pct"),
                    "free_gb": x.get("free_gb"),
                    "size_gb": x.get("size_gb"),
                }
                for x in related
            ]
        else:
            d["free_pct"] = None
            d["volumes"] = []

    return {
        "inventory": inventory,
        "disks": disks,
        "volumes": volumes,
        "elevated": elevated,
        "smartctl_available": smartctl_available(),
    }
