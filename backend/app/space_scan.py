"""フォルダ容量スキャン（Drive Glance 相当）と安全性ラベル。"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


Safety = str  # safe | caution | danger | neutral

# Windows: ジャンクション / マウントポイント / クラウドプレースホルダ
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
_FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000

SKIP_NAMES = {
    "System Volume Information",
    "Documents and Settings",
    "All Users",
    "Default User",
    "Application Data",
    "Local Settings",
    "Cookies",
    "NetHood",
    "PrintHood",
    "Recent",
    "SendTo",
    "Templates",
    "Start Menu",
}

# 容量マップの実用上、再帰すると極端に遅い／ループしやすい場所
SKIP_SCAN_NAMES = {
    "WinSxS",  # ハードリンクだらけで HDD だと何時間もかかることがある
    "CSC",  # オフラインファイルキャッシュ
}

RULES: list[tuple[re.Pattern[str], Safety, str, bool]] = [
    (re.compile(r"\\\$Recycle\.Bin(\\|$)", re.I), "safe", "ごみ箱の中身です。不要なら空にしても通常は問題ありません。", True),
    (re.compile(r"\\Windows\\Temp(\\|$)", re.I), "safe", "Windows の一時ファイルです。消しても多くの場合は再生成されます。", True),
    (re.compile(r"\\AppData\\Local\\Temp(\\|$)", re.I), "safe", "ユーザーの一時ファイルです。消しても通常は再生成されます。", True),
    (re.compile(r"\\Temp(\\|$)", re.I), "safe", "一時ファイル置き場です。消しても通常は再生成されます。", True),
    (re.compile(r"\\AppData\\Local\\(Google\\Chrome|Microsoft\\Edge|Mozilla\\Firefox)\\.*\\Cache", re.I), "safe", "ブラウザのキャッシュです。消すと再ダウンロードが増える程度です。", True),
    (re.compile(r"\\npm-cache(\\|$)|\\AppData\\Local\\npm-cache(\\|$)", re.I), "safe", "npm のキャッシュです。消しても次のインストールで再取得されます。", True),
    (re.compile(r"\\AppData\\Local\\pip\\Cache(\\|$)", re.I), "safe", "pip のキャッシュです。消しても再インストール時に再取得されます。", True),
    (re.compile(r"\\Windows\.old(\\|$)", re.I), "caution", "以前の Windows のバックアップです。問題なければ削除候補ですが、復元には使えなくなります。", True),
    (re.compile(r"\\Downloads(\\|$)", re.I), "caution", "ダウンロードフォルダです。中身を確認してから不要なものだけ消しましょう。", True),
    (re.compile(r"\\AppData\\Local\\(CrashDumps|D3DSCache|Package Cache)(\\|$)", re.I), "caution", "アプリのキャッシュやクラッシュダンプです。容量が大きいなら見直し候補です。", True),
    (re.compile(r"\\AppData\\Local(\\|$)", re.I), "caution", "アプリのデータが混在します。フォルダ単位で中身を確認してから判断してください。", False),
    (re.compile(r"\\Windows(\\|$)", re.I), "danger", "OS 本体です。削除すると Windows が起動しなくなる恐れがあります。", False),
    (re.compile(r"\\Program Files( \(x86\))?(\\|$)", re.I), "danger", "インストール済みアプリ本体です。アンインストーラ以外での削除は危険です。", False),
    (re.compile(r"\\System32(\\|$)|\\SysWOW64(\\|$)", re.I), "danger", "システム必須フォルダです。絶対に触らないでください。", False),
    (re.compile(r"\\Boot(\\|$)|\\Recovery(\\|$)|\\PerfLogs(\\|$)", re.I), "danger", "起動・復旧関連です。削除すると深刻な不具合の原因になります。", False),
    (re.compile(r"\\Users\\[^\\]+\\(Documents|Desktop|Pictures|Videos|Music)(\\|$)", re.I), "caution", "個人ファイルの保管場所です。必要なものまで消さないよう注意してください。", False),
    (re.compile(r"\\Users\\[^\\]+(\\|$)", re.I), "caution", "ユーザープロファイルです。中の重要ファイルを消さないよう注意してください。", False),
]

DEFAULT_REASON = "特に危険とも安全とも断定できない場所です。中身を確認してから判断してください。"


def classify_path(target_path: str) -> tuple[Safety, str, bool]:
    normalized = target_path.replace("/", "\\")
    for pattern, safety, reason, candidate in RULES:
        if pattern.search(normalized):
            return safety, reason, candidate
    return "neutral", DEFAULT_REASON, False


def annotate_node(node: dict[str, Any]) -> dict[str, Any]:
    safety, reason, _ = classify_path(node["path"])
    children = node.get("children")
    return {
        **node,
        "safety": safety,
        "reason": reason,
        "children": [annotate_node(c) for c in children] if children else None,
    }


def collect_candidates(root: dict[str, Any], min_bytes: int = 50 * 1024 * 1024) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(node: dict[str, Any]) -> None:
        _, reason, candidate = classify_path(node["path"])
        safety, _, _ = classify_path(node["path"])
        if candidate and int(node.get("size") or 0) >= min_bytes:
            found.append(
                {
                    "name": node["name"],
                    "path": node["path"],
                    "size": node["size"],
                    "safety": safety,
                    "reason": reason,
                }
            )
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    found.sort(key=lambda n: int(n["size"]), reverse=True)
    return found[:30]


@dataclass
class SpaceScanState:
    cancelled: bool = False
    running: bool = False
    paused: bool = False
    root_path: str | None = None
    progress: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    resume_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)


_state = SpaceScanState()
_results_by_root: dict[str, dict[str, Any]] = {}
_scan_thread: threading.Thread | None = None


def _normalize_root(root_path: str) -> str:
    return str(root_path or "").rstrip("\\/").upper() + "\\"


def get_progress() -> dict[str, Any] | None:
    with _state.lock:
        return dict(_state.progress) if _state.progress else None


def get_result(root_path: str | None = None) -> dict[str, Any] | None:
    with _state.lock:
        if root_path:
            normalized = _normalize_root(root_path)
            if _state.running and normalized == _normalize_root(_state.root_path or ""):
                return None
            return _results_by_root.get(normalized)
        return _state.result


def cancel_scan() -> None:
    with _state.lock:
        _state.cancelled = True
        _state.paused = False
        _state.resume_event.set()


def pause_scan() -> dict[str, Any]:
    with _state.lock:
        if not _state.running:
            return {"ok": False, "message": "実行中のスキャンがありません"}
        if _state.paused:
            return {"ok": True, "paused": True}
        _state.paused = True
        _state.resume_event.clear()
        if _state.progress:
            _state.progress["phase"] = "paused"
        return {"ok": True, "paused": True}


def resume_scan() -> dict[str, Any]:
    with _state.lock:
        if not _state.running:
            return {"ok": False, "message": "再開できるスキャンがありません"}
        _state.paused = False
        _state.resume_event.set()
        if _state.progress:
            _state.progress["phase"] = "scanning"
        return {"ok": True, "paused": False}


def _checkpoint() -> bool:
    """中断中は待機し、キャンセルされたら True を返す。"""
    while True:
        with _state.lock:
            if _state.cancelled:
                return True
            paused = _state.paused
        if not paused:
            return False
        _state.resume_event.wait(0.2)


def list_drives() -> list[dict[str, Any]]:
    import ctypes
    import string

    drives: list[dict[str, Any]] = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not (bitmask & (1 << i)):
            continue
        root = f"{letter}:\\"
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)
        # 2 removable, 3 fixed
        if drive_type not in (2, 3):
            continue
        try:
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(root),
                None,
                ctypes.byref(total_bytes),
                ctypes.byref(free_bytes),
            )
            total = int(total_bytes.value)
            free = int(free_bytes.value)
            if total <= 0:
                continue
            label = ""
            try:
                vol = ctypes.create_unicode_buffer(261)
                ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(root),
                    vol,
                    261,
                    None,
                    None,
                    None,
                    None,
                    0,
                )
                label = vol.value or ""
            except Exception:
                label = ""
            drives.append(
                {
                    "letter": letter,
                    "rootPath": root,
                    "label": label or "ローカルディスク",
                    "totalBytes": total,
                    "freeBytes": free,
                    "usedBytes": max(0, total - free),
                }
            )
        except Exception:
            continue
    return drives


def _disk_usage(root_path: str) -> dict[str, int]:
    import ctypes

    free_bytes = ctypes.c_ulonglong(0)
    total_bytes = ctypes.c_ulonglong(0)
    ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(root_path),
        None,
        ctypes.byref(total_bytes),
        ctypes.byref(free_bytes),
    )
    if not ok:
        return {"totalBytes": 0, "freeBytes": 0, "usedBytes": 0}
    total = int(total_bytes.value)
    free = int(free_bytes.value)
    return {"totalBytes": total, "freeBytes": free, "usedBytes": max(0, total - free)}


def _dir_size_shallow(dir_path: str) -> int:
    """再帰せず、直下のファイルサイズ合計だけ返す。"""
    total = 0
    try:
        with os.scandir(dir_path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def _dir_size_depth1(dir_path: str) -> int:
    """直下ファイル + その1段下のファイルまで（WinSxS などの概算用）。"""
    total = _dir_size_shallow(dir_path)
    try:
        with os.scandir(dir_path) as it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        total += _dir_size_shallow(entry.path)
                except OSError:
                    continue
    except OSError:
        pass
    return total


def _is_skipped_entry(entry: os.DirEntry) -> bool:
    """シンボリックリンク・ジャンクション・クラウド想起ファイルなどは走査しない。"""
    name = entry.name
    if name in SKIP_NAMES:
        return True
    if name.startswith("$") and name != "$Recycle.Bin":
        return True
    try:
        if entry.is_symlink():
            return True
    except OSError:
        return True
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    attrs = int(getattr(st, "st_file_attributes", 0) or 0)
    if attrs & _FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    # OneDrive などのプレースホルダを触るとダウンロード待ちで止まることがある
    if attrs & (_FILE_ATTRIBUTE_RECALL_ON_OPEN | _FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS):
        return True
    return False


def _scan_dir(dir_path: str, depth: int, stats: dict[str, Any], emit: Callable[[], None]) -> dict[str, Any] | None:
    if _checkpoint():
        return None

    stats["currentPath"] = dir_path
    emit()

    try:
        entry_iter = os.scandir(dir_path)
    except OSError:
        stats["skippedCount"] += 1
        return None

    stats["scannedDirs"] += 1
    children: list[dict[str, Any]] = []
    size = 0

    try:
        for entry in entry_iter:
            if _checkpoint():
                break
            full = os.path.join(dir_path, entry.name)

            # WinSxS などは中身を全部辿らず、浅い概算サイズだけ載せる
            if entry.name in SKIP_SCAN_NAMES:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stats["currentPath"] = full
                        emit()
                        approx = _dir_size_depth1(full)
                        children.append(
                            {
                                "name": entry.name,
                                "path": full,
                                "size": approx,
                                "safety": "danger",
                                "reason": "巨大なシステム領域のため詳細走査を省略しています（概算）。",
                                "children": None,
                            }
                        )
                        size += approx
                        stats["bytesSeen"] += approx
                        stats["skippedCount"] += 1
                except OSError:
                    stats["skippedCount"] += 1
                stats["ops"] += 1
                emit()
                continue

            if _is_skipped_entry(entry):
                stats["skippedCount"] += 1
                continue

            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError:
                stats["skippedCount"] += 1
                continue

            if is_dir:
                child = _scan_dir(full, depth + 1, stats, emit)
                if child:
                    children.append(child)
                    size += int(child["size"])
            elif is_file:
                try:
                    st = entry.stat(follow_symlinks=False)
                    size += st.st_size
                    stats["bytesSeen"] += st.st_size
                    stats["scannedFiles"] += 1
                except OSError:
                    stats["skippedCount"] += 1
            stats["ops"] += 1
            if stats["ops"] % 40 == 0:
                stats["currentPath"] = full
                emit()
    finally:
        try:
            entry_iter.close()
        except Exception:
            pass

    children.sort(key=lambda c: int(c["size"]), reverse=True)
    max_children = 40 if depth == 0 else 18
    display = children
    if len(children) > max_children:
        kept = children[: max_children - 1]
        rest = children[max_children - 1 :]
        rest_size = sum(int(c["size"]) for c in rest)
        if rest_size > 0:
            kept.append(
                {
                    "name": f"その他 ({len(rest)}件)",
                    "path": os.path.join(dir_path, "__other__"),
                    "size": rest_size,
                    "safety": "neutral",
                    "reason": "小さめの項目をまとめた表示です。",
                }
            )
        display = kept
    if depth >= 2:
        display = [c for c in display if int(c["size"]) >= 1024 * 1024 or c.get("children")]

    base = os.path.basename(dir_path.rstrip("\\/")) or dir_path
    return {
        "name": base,
        "path": dir_path,
        "size": size,
        "safety": "neutral",
        "reason": "",
        "children": display or None,
    }


def _run_scan(
    root_path: str,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    started = time.time()
    stats = {
        "scannedFiles": 0,
        "scannedDirs": 0,
        "bytesSeen": 0,
        "skippedCount": 0,
        "ops": 0,
        "currentPath": root_path,
    }
    last_emit = 0.0

    def emit(force: bool = False) -> None:
        nonlocal last_emit
        now = time.time()
        if not force and now - last_emit < 0.12:
            return
        last_emit = now
        with _state.lock:
            snapshot = {
                "scannedFiles": stats["scannedFiles"],
                "scannedDirs": stats["scannedDirs"],
                "currentPath": stats["currentPath"],
                "bytesSeen": stats["bytesSeen"],
                "phase": "paused" if _state.paused else "scanning",
            }
            _state.progress = dict(snapshot)
        # ロック外で通知（呼び出し側が別ロックを取る場合のデッドロック回避）
        if on_progress is not None:
            try:
                on_progress(snapshot)
            except Exception:
                pass

    heartbeat_stop = threading.Event()

    def _heartbeat() -> None:
        # scandir が長いときも「生きている」ことと現在パスを UI に流す
        while not heartbeat_stop.wait(2.0):
            with _state.lock:
                if not _state.running or _state.cancelled:
                    return
            emit(True)

    heartbeat = threading.Thread(target=_heartbeat, name="pchc-space-heartbeat", daemon=True)
    heartbeat.start()

    try:
        emit(True)
        raw = _scan_dir(root_path, 0, stats, emit)
        if _state.cancelled:
            with _state.lock:
                _state.running = False
                _state.paused = False
                _state.progress = None
                _state.error = None
            return
        if not raw:
            raise RuntimeError(f"{root_path} を読み取れませんでした。")
        root = annotate_node(raw)
        candidates = collect_candidates(root)
        disk = _disk_usage(root_path)
        result = {
            "root": root,
            "disk": disk,
            "candidates": candidates,
            "skippedCount": stats["skippedCount"],
            "durationMs": int((time.time() - started) * 1000),
            "rootPath": root_path,
        }
        with _state.lock:
            _state.result = result
            _results_by_root[_normalize_root(root_path)] = result
            _state.progress = None
            _state.running = False
            _state.paused = False
            _state.error = None
    except Exception as exc:
        with _state.lock:
            _state.running = False
            _state.paused = False
            _state.error = str(exc)
            _state.progress = None
    finally:
        heartbeat_stop.set()
        heartbeat.join(timeout=1.0)


def start_scan(root_path: str) -> dict[str, Any]:
    global _scan_thread
    with _state.lock:
        if _state.running:
            return {"ok": False, "message": "すでにスキャン中です"}
        _state.running = True
        _state.cancelled = False
        _state.paused = False
        _state.root_path = root_path
        _state.resume_event.set()
        _state.error = None
        _state.result = None
        _results_by_root.pop(_normalize_root(root_path), None)
        _state.progress = {
            "scannedFiles": 0,
            "scannedDirs": 0,
            "currentPath": root_path,
            "bytesSeen": 0,
            "phase": "scanning",
        }
    _scan_thread = threading.Thread(target=_run_scan, args=(root_path,), daemon=True)
    _scan_thread.start()
    return {"ok": True}


def restart_scan(root_path: str) -> dict[str, Any]:
    """実行中の走査を安全に止め、同じドライブを先頭から走査する。"""
    with _state.lock:
        thread = _scan_thread
        running = _state.running
    if running:
        cancel_scan()
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        with _state.lock:
            if _state.running:
                return {"ok": False, "message": "前のスキャンを停止しています。少し待ってから再度お試しください"}
    return start_scan(root_path)


def run_scan_blocking(
    root_path: str,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """健康診断スキャンから同期的に1ドライブ分のマップを作る。"""
    with _state.lock:
        if _state.running:
            return {"ok": False, "message": "すでにスキャン中です"}
        _state.running = True
        _state.cancelled = False
        _state.paused = False
        _state.root_path = root_path
        _state.resume_event.set()
        _state.error = None
        _state.progress = {
            "scannedFiles": 0,
            "scannedDirs": 0,
            "currentPath": root_path,
            "bytesSeen": 0,
            "phase": "scanning",
        }
    _run_scan(root_path, on_progress=on_progress)
    with _state.lock:
        if _state.cancelled:
            return {"ok": False, "message": "CANCELLED"}
        if _state.error:
            return {"ok": False, "message": _state.error}
        return {"ok": True, "rootPath": root_path}


def get_error() -> str | None:
    with _state.lock:
        return _state.error
