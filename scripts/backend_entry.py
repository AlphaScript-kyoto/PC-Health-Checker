"""Frozen / CLI entry for PC Health backend."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import main


if __name__ == "__main__":
    # Always headless when launched as packaged backend
    headless = "--headless" in sys.argv or getattr(sys, "frozen", False)
    main(headless=headless)
