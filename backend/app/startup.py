from __future__ import annotations

import sys
from pathlib import Path

from app.config import APP_NAME, PROJECT_ROOT, ROOT_DIR


def _startup_command() -> str:
    python = Path(sys.executable).resolve()
    main = ROOT_DIR / "app" / "main.py"
    pythonw = python.with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else python
    return f'"{exe}" "{main}"'


def startup_shortcut_path() -> Path:
    startup = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )
    return startup / f"{APP_NAME}.lnk"


def is_startup_enabled() -> bool:
    return startup_shortcut_path().exists()


def set_startup(enabled: bool) -> bool:
    """Create or remove a Startup folder shortcut to run_app.vbs (no console)."""
    path = startup_shortcut_path()
    if not enabled:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                return False
        return True

    try:
        import os
        import subprocess

        launcher = str((PROJECT_ROOT / "run_app.vbs").resolve())
        workdir = str(PROJECT_ROOT.resolve())
        wscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe")
        script = f"""
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut('{path}')
$sc.TargetPath = '{wscript}'
$sc.Arguments = '//nologo \"{launcher}\"'
$sc.WorkingDirectory = '{workdir}'
$sc.WindowStyle = 7
$sc.Description = '{APP_NAME}'
$sc.Save()
"""
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return path.exists()
    except Exception:
        return False
