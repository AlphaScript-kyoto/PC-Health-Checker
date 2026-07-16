"""
Trackable PC parts catalog.

CATALOG_VERSION を上げると「現行世代ウィンドウ」が更新される。
ウィンドウ外になった選択パーツは orphan になり、ユーザーが残す/外すを選ぶ。

Updated 2026-07: AMD GPU は実在の RX 9000 (RDNA4) に修正。
旧カタログの架空 RX 8000 SKU は orphan 扱いになる。
"""

from __future__ import annotations

from typing import Any

# Bump when generation window changes
CATALOG_VERSION = "2026.07.3"

# generation_rank: higher = newer within brand/family
CATALOG: list[dict[str, Any]] = [
    # ---- CPU Intel (Core Ultra 200S / Plus / 14th / 13th) ----
    {"id": "cpu-intel-ultra9-285k", "category": "cpu", "brand": "Intel", "name": "Core Ultra 9 285K", "generation": "Core Ultra 200S", "gen_rank": 4, "tier": "high", "query": "Core Ultra 9 285K"},
    {"id": "cpu-intel-ultra7-270k-plus", "category": "cpu", "brand": "Intel", "name": "Core Ultra 7 270K Plus", "generation": "Core Ultra 200S Plus", "gen_rank": 4, "tier": "high", "query": "Core Ultra 7 270K Plus"},
    {"id": "cpu-intel-ultra7-265k", "category": "cpu", "brand": "Intel", "name": "Core Ultra 7 265K", "generation": "Core Ultra 200S", "gen_rank": 3, "tier": "high", "query": "Core Ultra 7 265K"},
    {"id": "cpu-intel-ultra5-250k-plus", "category": "cpu", "brand": "Intel", "name": "Core Ultra 5 250K Plus", "generation": "Core Ultra 200S Plus", "gen_rank": 4, "tier": "mid", "query": "Core Ultra 5 250K Plus"},
    {"id": "cpu-intel-ultra5-245k", "category": "cpu", "brand": "Intel", "name": "Core Ultra 5 245K", "generation": "Core Ultra 200S", "gen_rank": 3, "tier": "mid", "query": "Core Ultra 5 245K"},
    {"id": "cpu-intel-14900k", "category": "cpu", "brand": "Intel", "name": "Core i9-14900K", "generation": "第14世代", "gen_rank": 2, "tier": "high", "query": "Core i9-14900K"},
    {"id": "cpu-intel-14700k", "category": "cpu", "brand": "Intel", "name": "Core i7-14700K", "generation": "第14世代", "gen_rank": 2, "tier": "high", "query": "Core i7-14700K"},
    {"id": "cpu-intel-14600k", "category": "cpu", "brand": "Intel", "name": "Core i5-14600K", "generation": "第14世代", "gen_rank": 2, "tier": "mid", "query": "Core i5-14600K"},
    {"id": "cpu-intel-13900k", "category": "cpu", "brand": "Intel", "name": "Core i9-13900K", "generation": "第13世代", "gen_rank": 1, "tier": "high", "query": "Core i9-13900K"},
    {"id": "cpu-intel-13700k", "category": "cpu", "brand": "Intel", "name": "Core i7-13700K", "generation": "第13世代", "gen_rank": 1, "tier": "high", "query": "Core i7-13700K"},
    {"id": "cpu-intel-13600k", "category": "cpu", "brand": "Intel", "name": "Core i5-13600K", "generation": "第13世代", "gen_rank": 1, "tier": "mid", "query": "Core i5-13600K"},
    # ---- CPU AMD (Ryzen 9000 / 7000 / 5000 + X3D) ----
    {"id": "cpu-amd-9950x", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 9950X", "generation": "Ryzen 9000", "gen_rank": 3, "tier": "high", "query": "Ryzen 9 9950X"},
    {"id": "cpu-amd-9950x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 9950X3D", "generation": "Ryzen 9000", "gen_rank": 3, "tier": "high", "query": "Ryzen 9 9950X3D"},
    {"id": "cpu-amd-9900x", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 9900X", "generation": "Ryzen 9000", "gen_rank": 3, "tier": "high", "query": "Ryzen 9 9900X"},
    {"id": "cpu-amd-9900x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 9900X3D", "generation": "Ryzen 9000", "gen_rank": 3, "tier": "high", "query": "Ryzen 9 9900X3D"},
    {"id": "cpu-amd-9850x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 7 9850X3D", "generation": "Ryzen 9000", "gen_rank": 3, "tier": "high", "query": "Ryzen 7 9850X3D"},
    {"id": "cpu-amd-9800x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 7 9800X3D", "generation": "Ryzen 9000", "gen_rank": 3, "tier": "high", "query": "Ryzen 7 9800X3D"},
    {"id": "cpu-amd-9700x", "category": "cpu", "brand": "AMD", "name": "Ryzen 7 9700X", "generation": "Ryzen 9000", "gen_rank": 3, "tier": "high", "query": "Ryzen 7 9700X"},
    {"id": "cpu-amd-9600x", "category": "cpu", "brand": "AMD", "name": "Ryzen 5 9600X", "generation": "Ryzen 9000", "gen_rank": 3, "tier": "mid", "query": "Ryzen 5 9600X"},
    {"id": "cpu-amd-7950x", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 7950X", "generation": "Ryzen 7000", "gen_rank": 2, "tier": "high", "query": "Ryzen 9 7950X"},
    {"id": "cpu-amd-7950x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 7950X3D", "generation": "Ryzen 7000", "gen_rank": 2, "tier": "high", "query": "Ryzen 9 7950X3D"},
    {"id": "cpu-amd-7900x", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 7900X", "generation": "Ryzen 7000", "gen_rank": 2, "tier": "high", "query": "Ryzen 9 7900X"},
    {"id": "cpu-amd-7900x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 7900X3D", "generation": "Ryzen 7000", "gen_rank": 2, "tier": "high", "query": "Ryzen 9 7900X3D"},
    {"id": "cpu-amd-7800x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 7 7800X3D", "generation": "Ryzen 7000", "gen_rank": 2, "tier": "high", "query": "Ryzen 7 7800X3D"},
    {"id": "cpu-amd-7700x", "category": "cpu", "brand": "AMD", "name": "Ryzen 7 7700X", "generation": "Ryzen 7000", "gen_rank": 2, "tier": "high", "query": "Ryzen 7 7700X"},
    {"id": "cpu-amd-7600x", "category": "cpu", "brand": "AMD", "name": "Ryzen 5 7600X", "generation": "Ryzen 7000", "gen_rank": 2, "tier": "mid", "query": "Ryzen 5 7600X"},
    {"id": "cpu-amd-7600", "category": "cpu", "brand": "AMD", "name": "Ryzen 5 7600", "generation": "Ryzen 7000", "gen_rank": 2, "tier": "mid", "query": "Ryzen 5 7600"},
    {"id": "cpu-amd-5950x", "category": "cpu", "brand": "AMD", "name": "Ryzen 9 5950X", "generation": "Ryzen 5000", "gen_rank": 1, "tier": "high", "query": "Ryzen 9 5950X"},
    {"id": "cpu-amd-5800x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 7 5800X3D", "generation": "Ryzen 5000", "gen_rank": 1, "tier": "high", "query": "Ryzen 7 5800X3D"},
    {"id": "cpu-amd-5700x", "category": "cpu", "brand": "AMD", "name": "Ryzen 7 5700X", "generation": "Ryzen 5000", "gen_rank": 1, "tier": "mid", "query": "Ryzen 7 5700X"},
    {"id": "cpu-amd-5700x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 7 5700X3D", "generation": "Ryzen 5000", "gen_rank": 1, "tier": "mid", "query": "Ryzen 7 5700X3D"},
    {"id": "cpu-amd-5600x", "category": "cpu", "brand": "AMD", "name": "Ryzen 5 5600X", "generation": "Ryzen 5000", "gen_rank": 1, "tier": "mid", "query": "Ryzen 5 5600X"},
    {"id": "cpu-amd-5600x3d", "category": "cpu", "brand": "AMD", "name": "Ryzen 5 5600X3D", "generation": "Ryzen 5000", "gen_rank": 1, "tier": "mid", "query": "Ryzen 5 5600X3D"},
    # ---- GPU NVIDIA (RTX 50 / 40 / 30) ----
    {"id": "gpu-nv-5090", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 5090", "generation": "RTX 50", "gen_rank": 3, "tier": "high", "query": "RTX 5090"},
    {"id": "gpu-nv-5080", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 5080", "generation": "RTX 50", "gen_rank": 3, "tier": "high", "query": "RTX 5080"},
    {"id": "gpu-nv-5070ti", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 5070 Ti", "generation": "RTX 50", "gen_rank": 3, "tier": "high", "query": "RTX 5070 Ti"},
    {"id": "gpu-nv-5070", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 5070", "generation": "RTX 50", "gen_rank": 3, "tier": "mid", "query": "RTX 5070"},
    {"id": "gpu-nv-5060ti", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 5060 Ti", "generation": "RTX 50", "gen_rank": 3, "tier": "mid", "query": "RTX 5060 Ti"},
    {"id": "gpu-nv-5060", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 5060", "generation": "RTX 50", "gen_rank": 3, "tier": "mid", "query": "RTX 5060"},
    {"id": "gpu-nv-5050", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 5050", "generation": "RTX 50", "gen_rank": 3, "tier": "entry", "query": "RTX 5050"},
    {"id": "gpu-nv-4090", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 4090", "generation": "RTX 40", "gen_rank": 2, "tier": "high", "query": "RTX 4090"},
    {"id": "gpu-nv-4080s", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 4080 SUPER", "generation": "RTX 40", "gen_rank": 2, "tier": "high", "query": "RTX 4080 SUPER"},
    {"id": "gpu-nv-4070tis", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 4070 Ti SUPER", "generation": "RTX 40", "gen_rank": 2, "tier": "high", "query": "RTX 4070 Ti SUPER"},
    {"id": "gpu-nv-4070s", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 4070 SUPER", "generation": "RTX 40", "gen_rank": 2, "tier": "mid", "query": "RTX 4070 SUPER"},
    {"id": "gpu-nv-4060ti", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 4060 Ti", "generation": "RTX 40", "gen_rank": 2, "tier": "mid", "query": "RTX 4060 Ti"},
    {"id": "gpu-nv-4060", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 4060", "generation": "RTX 40", "gen_rank": 2, "tier": "entry", "query": "RTX 4060"},
    {"id": "gpu-nv-3090", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 3090", "generation": "RTX 30", "gen_rank": 1, "tier": "high", "query": "RTX 3090"},
    {"id": "gpu-nv-3080", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 3080", "generation": "RTX 30", "gen_rank": 1, "tier": "high", "query": "RTX 3080"},
    {"id": "gpu-nv-3070", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 3070", "generation": "RTX 30", "gen_rank": 1, "tier": "mid", "query": "RTX 3070"},
    {"id": "gpu-nv-3060", "category": "gpu", "brand": "NVIDIA", "name": "GeForce RTX 3060", "generation": "RTX 30", "gen_rank": 1, "tier": "mid", "query": "RTX 3060"},
    # ---- GPU AMD (RX 9000 RDNA4 / 7000 / 6000) ----
    # ※ RDNA4 の正式名は RX 9000。架空の「RX 8000」は削除済み。
    {"id": "gpu-amd-9070xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 9070 XT", "generation": "RX 9000", "gen_rank": 3, "tier": "high", "query": "RX 9070 XT"},
    {"id": "gpu-amd-9070", "category": "gpu", "brand": "AMD", "name": "Radeon RX 9070", "generation": "RX 9000", "gen_rank": 3, "tier": "high", "query": "RX 9070"},
    {"id": "gpu-amd-9070gre", "category": "gpu", "brand": "AMD", "name": "Radeon RX 9070 GRE", "generation": "RX 9000", "gen_rank": 3, "tier": "mid", "query": "RX 9070 GRE"},
    {"id": "gpu-amd-9060xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 9060 XT", "generation": "RX 9000", "gen_rank": 3, "tier": "mid", "query": "RX 9060 XT"},
    {"id": "gpu-amd-9060", "category": "gpu", "brand": "AMD", "name": "Radeon RX 9060", "generation": "RX 9000", "gen_rank": 3, "tier": "entry", "query": "RX 9060"},
    {"id": "gpu-amd-7900xtx", "category": "gpu", "brand": "AMD", "name": "Radeon RX 7900 XTX", "generation": "RX 7000", "gen_rank": 2, "tier": "high", "query": "RX 7900 XTX"},
    {"id": "gpu-amd-7900xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 7900 XT", "generation": "RX 7000", "gen_rank": 2, "tier": "high", "query": "RX 7900 XT"},
    {"id": "gpu-amd-7900gre", "category": "gpu", "brand": "AMD", "name": "Radeon RX 7900 GRE", "generation": "RX 7000", "gen_rank": 2, "tier": "mid", "query": "RX 7900 GRE"},
    {"id": "gpu-amd-7800xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 7800 XT", "generation": "RX 7000", "gen_rank": 2, "tier": "high", "query": "RX 7800 XT"},
    {"id": "gpu-amd-7700xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 7700 XT", "generation": "RX 7000", "gen_rank": 2, "tier": "mid", "query": "RX 7700 XT"},
    {"id": "gpu-amd-7600xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 7600 XT", "generation": "RX 7000", "gen_rank": 2, "tier": "mid", "query": "RX 7600 XT"},
    {"id": "gpu-amd-7600", "category": "gpu", "brand": "AMD", "name": "Radeon RX 7600", "generation": "RX 7000", "gen_rank": 2, "tier": "mid", "query": "RX 7600"},
    {"id": "gpu-amd-6900xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 6900 XT", "generation": "RX 6000", "gen_rank": 1, "tier": "high", "query": "RX 6900 XT"},
    {"id": "gpu-amd-6800xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 6800 XT", "generation": "RX 6000", "gen_rank": 1, "tier": "high", "query": "RX 6800 XT"},
    {"id": "gpu-amd-6700xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 6700 XT", "generation": "RX 6000", "gen_rank": 1, "tier": "mid", "query": "RX 6700 XT"},
    {"id": "gpu-amd-6600xt", "category": "gpu", "brand": "AMD", "name": "Radeon RX 6600 XT", "generation": "RX 6000", "gen_rank": 1, "tier": "mid", "query": "RX 6600 XT"},
    {"id": "gpu-amd-6600", "category": "gpu", "brand": "AMD", "name": "Radeon RX 6600", "generation": "RX 6000", "gen_rank": 1, "tier": "mid", "query": "RX 6600"},
    # ---- HDD ----
    {"id": "hdd-1tb", "category": "hdd", "brand": "Generic", "name": "HDD 1TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 1TB"},
    {"id": "hdd-2tb", "category": "hdd", "brand": "Generic", "name": "HDD 2TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 2TB"},
    {"id": "hdd-4tb", "category": "hdd", "brand": "Generic", "name": "HDD 4TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 4TB"},
    {"id": "hdd-6tb", "category": "hdd", "brand": "Generic", "name": "HDD 6TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 6TB"},
    {"id": "hdd-8tb", "category": "hdd", "brand": "Generic", "name": "HDD 8TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 8TB"},
    {"id": "hdd-10tb", "category": "hdd", "brand": "Generic", "name": "HDD 10TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 10TB"},
    {"id": "hdd-12tb", "category": "hdd", "brand": "Generic", "name": "HDD 12TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 12TB"},
    {"id": "hdd-16tb", "category": "hdd", "brand": "Generic", "name": "HDD 16TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 16TB"},
    {"id": "hdd-20tb", "category": "hdd", "brand": "Generic", "name": "HDD 20TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 20TB"},
    {"id": "hdd-22tb", "category": "hdd", "brand": "Generic", "name": "HDD 22TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "HDD 22TB"},
    # ---- SATA SSD ----
    {"id": "sata-500gb", "category": "sata_ssd", "brand": "Generic", "name": "SATA SSD 500GB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "SSD 2.5インチ 500GB SATA"},
    {"id": "sata-1tb", "category": "sata_ssd", "brand": "Generic", "name": "SATA SSD 1TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "SSD 2.5インチ 1TB SATA"},
    {"id": "sata-2tb", "category": "sata_ssd", "brand": "Generic", "name": "SATA SSD 2TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "SSD 2.5インチ 2TB SATA"},
    {"id": "sata-4tb", "category": "sata_ssd", "brand": "Generic", "name": "SATA SSD 4TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "SSD 2.5インチ 4TB SATA"},
    {"id": "sata-8tb", "category": "sata_ssd", "brand": "Generic", "name": "SATA SSD 8TB", "generation": "capacity", "gen_rank": 1, "tier": "storage", "query": "SSD 2.5インチ 8TB SATA"},
    # ---- M.2 SSD (NVMe / PCIe 世代別) ----
    {"id": "m2-pcie5-1tb", "category": "m2_ssd", "brand": "PCIe 5.0", "name": "M.2 PCIe5 1TB", "generation": "PCIe 5.0", "gen_rank": 3, "tier": "storage", "query": "M.2 SSD 1TB PCIe 5.0"},
    {"id": "m2-pcie5-2tb", "category": "m2_ssd", "brand": "PCIe 5.0", "name": "M.2 PCIe5 2TB", "generation": "PCIe 5.0", "gen_rank": 3, "tier": "storage", "query": "M.2 SSD 2TB PCIe 5.0"},
    {"id": "m2-pcie5-4tb", "category": "m2_ssd", "brand": "PCIe 5.0", "name": "M.2 PCIe5 4TB", "generation": "PCIe 5.0", "gen_rank": 3, "tier": "storage", "query": "M.2 SSD 4TB PCIe 5.0"},
    {"id": "m2-pcie4-1tb", "category": "m2_ssd", "brand": "PCIe 4.0", "name": "M.2 PCIe4 1TB", "generation": "PCIe 4.0", "gen_rank": 2, "tier": "storage", "query": "M.2 SSD 1TB PCIe 4.0"},
    {"id": "m2-pcie4-2tb", "category": "m2_ssd", "brand": "PCIe 4.0", "name": "M.2 PCIe4 2TB", "generation": "PCIe 4.0", "gen_rank": 2, "tier": "storage", "query": "M.2 SSD 2TB PCIe 4.0"},
    {"id": "m2-pcie4-4tb", "category": "m2_ssd", "brand": "PCIe 4.0", "name": "M.2 PCIe4 4TB", "generation": "PCIe 4.0", "gen_rank": 2, "tier": "storage", "query": "M.2 SSD 4TB PCIe 4.0"},
    {"id": "m2-pcie4-8tb", "category": "m2_ssd", "brand": "PCIe 4.0", "name": "M.2 PCIe4 8TB", "generation": "PCIe 4.0", "gen_rank": 2, "tier": "storage", "query": "M.2 SSD 8TB PCIe 4.0"},
    {"id": "m2-pcie3-1tb", "category": "m2_ssd", "brand": "PCIe 3.0", "name": "M.2 PCIe3 1TB", "generation": "PCIe 3.0", "gen_rank": 1, "tier": "storage", "query": "M.2 SSD 1TB PCIe 3.0"},
    {"id": "m2-pcie3-2tb", "category": "m2_ssd", "brand": "PCIe 3.0", "name": "M.2 PCIe3 2TB", "generation": "PCIe 3.0", "gen_rank": 1, "tier": "storage", "query": "M.2 SSD 2TB PCIe 3.0"},
    # ---- Memory ----
    {"id": "mem-ddr5-16", "category": "memory", "brand": "DDR5", "name": "DDR5 16GB (8x2)", "generation": "DDR5", "gen_rank": 2, "tier": "memory", "query": "DDR5 16GB 8GBx2"},
    {"id": "mem-ddr5-32", "category": "memory", "brand": "DDR5", "name": "DDR5 32GB (16x2)", "generation": "DDR5", "gen_rank": 2, "tier": "memory", "query": "DDR5 32GB 16GBx2"},
    {"id": "mem-ddr5-64", "category": "memory", "brand": "DDR5", "name": "DDR5 64GB (32x2)", "generation": "DDR5", "gen_rank": 2, "tier": "memory", "query": "DDR5 64GB 32GBx2"},
    {"id": "mem-ddr5-96", "category": "memory", "brand": "DDR5", "name": "DDR5 96GB (48x2)", "generation": "DDR5", "gen_rank": 2, "tier": "memory", "query": "DDR5 96GB 48GBx2"},
    {"id": "mem-ddr5-128", "category": "memory", "brand": "DDR5", "name": "DDR5 128GB (32x4)", "generation": "DDR5", "gen_rank": 2, "tier": "memory", "query": "DDR5 128GB 32GBx4"},
    {"id": "mem-ddr4-16", "category": "memory", "brand": "DDR4", "name": "DDR4 16GB (8x2)", "generation": "DDR4", "gen_rank": 1, "tier": "memory", "query": "DDR4 16GB 8GBx2"},
    {"id": "mem-ddr4-32", "category": "memory", "brand": "DDR4", "name": "DDR4 32GB (16x2)", "generation": "DDR4", "gen_rank": 1, "tier": "memory", "query": "DDR4 32GB 16GBx2"},
    {"id": "mem-ddr4-64", "category": "memory", "brand": "DDR4", "name": "DDR4 64GB (32x2)", "generation": "DDR4", "gen_rank": 1, "tier": "memory", "query": "DDR4 64GB 32GBx2"},
    # ---- Motherboard Intel (LGA1851 / LGA1700) ----
    {"id": "mb-intel-z890", "category": "motherboard", "brand": "Intel", "name": "Z890 マザーボード", "generation": "800シリーズ", "gen_rank": 3, "tier": "chipset", "query": "Z890 マザーボード"},
    {"id": "mb-intel-b860", "category": "motherboard", "brand": "Intel", "name": "B860 マザーボード", "generation": "800シリーズ", "gen_rank": 3, "tier": "chipset", "query": "B860 マザーボード"},
    {"id": "mb-intel-h810", "category": "motherboard", "brand": "Intel", "name": "H810 マザーボード", "generation": "800シリーズ", "gen_rank": 3, "tier": "chipset", "query": "H810 マザーボード"},
    {"id": "mb-intel-z790", "category": "motherboard", "brand": "Intel", "name": "Z790 マザーボード", "generation": "700シリーズ", "gen_rank": 2, "tier": "chipset", "query": "Z790 マザーボード"},
    {"id": "mb-intel-b760", "category": "motherboard", "brand": "Intel", "name": "B760 マザーボード", "generation": "700シリーズ", "gen_rank": 2, "tier": "chipset", "query": "B760 マザーボード"},
    {"id": "mb-intel-z690", "category": "motherboard", "brand": "Intel", "name": "Z690 マザーボード", "generation": "600シリーズ", "gen_rank": 1, "tier": "chipset", "query": "Z690 マザーボード"},
    {"id": "mb-intel-b660", "category": "motherboard", "brand": "Intel", "name": "B660 マザーボード", "generation": "600シリーズ", "gen_rank": 1, "tier": "chipset", "query": "B660 マザーボード"},
    # ---- Motherboard AMD (AM5 / AM4) ----
    {"id": "mb-amd-x870e", "category": "motherboard", "brand": "AMD", "name": "X870E マザーボード", "generation": "800シリーズ", "gen_rank": 3, "tier": "chipset", "query": "X870E マザーボード"},
    {"id": "mb-amd-x870", "category": "motherboard", "brand": "AMD", "name": "X870 マザーボード", "generation": "800シリーズ", "gen_rank": 3, "tier": "chipset", "query": "X870 マザーボード"},
    {"id": "mb-amd-b850", "category": "motherboard", "brand": "AMD", "name": "B850 マザーボード", "generation": "800シリーズ", "gen_rank": 3, "tier": "chipset", "query": "B850 マザーボード"},
    {"id": "mb-amd-b840", "category": "motherboard", "brand": "AMD", "name": "B840 マザーボード", "generation": "800シリーズ", "gen_rank": 3, "tier": "chipset", "query": "B840 マザーボード"},
    {"id": "mb-amd-x670e", "category": "motherboard", "brand": "AMD", "name": "X670E マザーボード", "generation": "600シリーズ", "gen_rank": 2, "tier": "chipset", "query": "X670E マザーボード"},
    {"id": "mb-amd-x670", "category": "motherboard", "brand": "AMD", "name": "X670 マザーボード", "generation": "600シリーズ", "gen_rank": 2, "tier": "chipset", "query": "X670 マザーボード"},
    {"id": "mb-amd-b650", "category": "motherboard", "brand": "AMD", "name": "B650 マザーボード", "generation": "600シリーズ", "gen_rank": 2, "tier": "chipset", "query": "B650 マザーボード"},
    {"id": "mb-amd-a620", "category": "motherboard", "brand": "AMD", "name": "A620 マザーボード", "generation": "600シリーズ", "gen_rank": 2, "tier": "chipset", "query": "A620 マザーボード"},
    {"id": "mb-amd-x570", "category": "motherboard", "brand": "AMD", "name": "X570 マザーボード", "generation": "500シリーズ", "gen_rank": 1, "tier": "chipset", "query": "X570 マザーボード"},
    {"id": "mb-amd-b550", "category": "motherboard", "brand": "AMD", "name": "B550 マザーボード", "generation": "500シリーズ", "gen_rank": 1, "tier": "chipset", "query": "B550 マザーボード"},
]

CATEGORY_LABELS = {
    "cpu": "CPU",
    "gpu": "GPU",
    "hdd": "HDD",
    "sata_ssd": "SATA SSD",
    "m2_ssd": "M.2 SSD",
    "memory": "メモリ",
    "motherboard": "マザーボード",
}

# Preferred brand order inside each category
BRAND_ORDER = [
    "Intel",
    "NVIDIA",
    "AMD",
    "PCIe 5.0",
    "PCIe 4.0",
    "PCIe 3.0",
    "DDR5",
    "DDR4",
    "Generic",
]


def catalog_by_id() -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in CATALOG}


def active_catalog_ids() -> set[str]:
    return {p["id"] for p in CATALOG}


BRAND_LABELS = {
    "Generic": "容量別",
    "DDR5": "DDR5",
    "DDR4": "DDR4",
    "Intel": "Intel",
    "AMD": "AMD",
    "NVIDIA": "NVIDIA",
    "PCIe 5.0": "PCIe 5.0",
    "PCIe 4.0": "PCIe 4.0",
    "PCIe 3.0": "PCIe 3.0",
}


def get_catalog_grouped() -> list[dict[str, Any]]:
    """Category -> brand subgroups for clearer UI."""
    order = list(CATEGORY_LABELS.keys())
    cat_map: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for p in CATALOG:
        cat = p["category"]
        brand = p.get("brand") or "Other"
        cat_map.setdefault(cat, {}).setdefault(brand, []).append(p)

    result = []
    for cat in order:
        brands = cat_map.get(cat) or {}
        brand_keys = sorted(
            brands.keys(),
            key=lambda b: (
                BRAND_ORDER.index(b) if b in BRAND_ORDER else 99,
                b,
            ),
        )
        brand_blocks = []
        for brand in brand_keys:
            items = brands[brand]
            brand_blocks.append(
                {
                    "brand": brand,
                    "label": BRAND_LABELS.get(brand, brand),
                    "items": items,
                }
            )
        result.append(
            {
                "category": cat,
                "label": CATEGORY_LABELS.get(cat, cat),
                "brands": brand_blocks,
                "items": [i for b in brand_blocks for i in b["items"]],
            }
        )
    return result
