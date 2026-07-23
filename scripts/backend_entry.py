"""Frozen / CLI entry for パソコンちぇっ君 backend (PyInstaller)."""
from __future__ import annotations

import sys
from pathlib import Path

# 開発時: リポジトリの backend/ を path に載せる
# 凍結時: PyInstaller が app パッケージを同梱する
if not getattr(sys, "frozen", False):
    backend_root = Path(__file__).resolve().parent.parent / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

from app.main import main


if __name__ == "__main__":
    # パッケージ起動は常にヘッドレス（Electron が UI を持つ）
    headless = "--headless" in sys.argv or getattr(sys, "frozen", False)
    main(headless=headless)
