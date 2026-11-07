from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from app.config import APP_NAME, PROJECT_ROOT

log = logging.getLogger("pc-health.startup")


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


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _resolve_launcher() -> tuple[str, str, str] | None:
    """ショートカットの実体。配布版は同梱 exe のみ。開発時だけ存在する vbs を使う。"""
    exe = os.environ.get("PCHC_APP_EXE", "").strip().strip('"')
    args = os.environ.get("PCHC_APP_ARGS", "")
    cwd = os.environ.get("PCHC_APP_CWD", "").strip().strip('"')

    if _is_frozen():
        # run_app.vbs は配布物に入っていないので、ここでは参照しない
        if exe and Path(exe).is_file():
            return exe, args, cwd or str(Path(exe).resolve().parent)
        return None

    vbs = (PROJECT_ROOT / "run_app.vbs").resolve()
    if vbs.is_file():
        windir = os.environ.get("SystemRoot", r"C:\Windows")
        wscript = Path(windir) / "System32" / "wscript.exe"
        if wscript.is_file():
            return str(wscript), f'//nologo "{vbs}"', str(PROJECT_ROOT.resolve())

    if exe and Path(exe).is_file():
        return exe, args, cwd or str(Path(exe).resolve().parent)
    return None


def set_startup(enabled: bool) -> bool:
    """スタートアップフォルダのショートカットを作る、または消す。失敗したら False。"""
    path = startup_shortcut_path()
    if not enabled:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                log.warning("startup shortcut could not be removed: %s", path)
                return False
        return True

    launcher = _resolve_launcher()
    if launcher is None:
        log.warning("startup launcher was not found")
        return False
    target, arguments, workdir = launcher
    if not Path(target).is_file():
        log.warning("startup target does not exist: %s", target)
        return False

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PCHC_SC_PATH"] = str(path)
        env["PCHC_SC_TARGET"] = target
        env["PCHC_SC_ARGS"] = arguments
        env["PCHC_SC_CWD"] = workdir
        env["PCHC_SC_DESC"] = APP_NAME
        script = """
$ErrorActionPreference = 'Stop'
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($env:PCHC_SC_PATH)
$sc.TargetPath = $env:PCHC_SC_TARGET
$sc.Arguments = $env:PCHC_SC_ARGS
$sc.WorkingDirectory = $env:PCHC_SC_CWD
$sc.WindowStyle = 7
$sc.Description = $env:PCHC_SC_DESC
$sc.Save()
"""
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        log.exception("startup shortcut creation failed")
        return False

    if completed.returncode != 0 or not path.is_file():
        log.warning(
            "startup shortcut was not created (code=%s): %s",
            completed.returncode,
            (completed.stderr or completed.stdout or "").strip()[:400],
        )
        return False
    return True
