"""Cota da conta do Claude aberta no app desktop.

A sessao fica no banco do proprio Claude. Nao e gravada neste projeto.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import sqlite3
import tempfile
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

import psutil
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from curl_cffi import requests as curl

_CACHE: dict | None = None
_CACHE_AT = 0.0
_CACHE_TTL_S = 60.0

_ntdll = ctypes.WinDLL("ntdll")
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_crypt32 = ctypes.WinDLL("crypt32")

_STATUS_MISMATCH = 0xC0000004
_PROCESS_DUP_HANDLE = 0x0040
_DUPLICATE_SAME_ACCESS = 0x0002
_FILE_TYPE_DISK = 0x0001

_ntdll.NtQuerySystemInformation.argtypes = [
    wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG),
]
_ntdll.NtQuerySystemInformation.restype = wintypes.ULONG
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.DuplicateHandle.argtypes = [
    wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
    ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
]
_kernel32.DuplicateHandle.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.GetFileType.argtypes = [wintypes.HANDLE]
_kernel32.GetFileType.restype = wintypes.DWORD
_kernel32.GetFinalPathNameByHandleW.argtypes = [
    wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
]
_kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
_kernel32.GetFileSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
_kernel32.GetFileSizeEx.restype = wintypes.BOOL
_kernel32.ReadFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_kernel32.ReadFile.restype = wintypes.BOOL
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE


class _HandleEntry(ctypes.Structure):
    _fields_ = [
        ("Object", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_size_t),
        ("HandleValue", ctypes.c_size_t),
        ("GrantedAccess", wintypes.ULONG),
        ("CreatorBackTraceIndex", wintypes.USHORT),
        ("ObjectTypeIndex", wintypes.USHORT),
        ("HandleAttributes", wintypes.ULONG),
        ("Reserved", wintypes.ULONG),
    ]


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


def _fail() -> dict:
    return {"ok": False, "source": "claude", "error": "sem leitura da cota"}


def _num(value) -> float | None:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _reset_label(iso: str | None) -> str:
    if not iso:
        return "--"
    try:
        reset = datetime.fromisoformat(iso)
    except ValueError:
        return "--"
    if reset.tzinfo is None:
        reset = reset.replace(tzinfo=timezone.utc)
    seconds = (reset - datetime.now(timezone.utc)).total_seconds()
    if seconds < 60:
        return "1m"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 48 * 3600:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def _dpapi(data: bytes) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DataBlob()
    if not _crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError(ctypes.get_last_error())
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        _kernel32.LocalFree(blob_out.pbData)


def _profile() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        raise RuntimeError("LOCALAPPDATA nao definido")
    base = Path(root) / "Claude-Data"
    found = [
        path for path in base.iterdir()
        if (path / "Network" / "Cookies").is_file() and (path / "Local State").is_file()
    ] if base.is_dir() else []
    if not found:
        raise RuntimeError("sessao do Claude nao encontrada")
    return max(found, key=lambda path: (path / "Network" / "Cookies").stat().st_mtime)


def _decrypt(key: bytes, encrypted: bytes) -> str:
    if encrypted[:3] in (b"v10", b"v11"):
        plain = AESGCM(key).decrypt(encrypted[3:15], encrypted[15:], None)
    else:
        plain = _dpapi(encrypted)
    for start in (0, 32):
        try:
            return plain[start:].decode("utf-8")
        except UnicodeDecodeError:
            continue
    marker = plain.find(b"sk-ant-")
    if marker >= 0:
        return plain[marker:].split(b"\x00", 1)[0].decode("ascii")
    raise UnicodeDecodeError("utf-8", plain, 0, 1, "cookie ilegivel")


def _system_handles():
    size = 1 << 20
    while size <= 64 << 20:
        buf = ctypes.create_string_buffer(size)
        needed = wintypes.ULONG(0)
        status = _ntdll.NtQuerySystemInformation(
            64, buf, size, ctypes.byref(needed)
        )
        if status == _STATUS_MISMATCH:
            size = max(size * 2, int(needed.value or 0))
            continue
        if status != 0:
            raise OSError(f"leitura de handles falhou ({status:#x})")
        count = ctypes.c_size_t.from_buffer(buf).value
        entry_size = ctypes.sizeof(_HandleEntry)
        base = ctypes.sizeof(ctypes.c_size_t) * 2
        for index in range(count):
            yield _HandleEntry.from_buffer_copy(buf, base + index * entry_size)
        return
    raise OSError("lista de handles grande demais")


def _read_locked(target: Path) -> bytes:
    wanted = str(target).lower().replace("/", "\\")
    pids = {
        proc.pid for proc in psutil.process_iter(["name"])
        if (proc.info["name"] or "").lower() == "claude.exe"
    }
    current = _kernel32.GetCurrentProcess()
    by_pid: dict[int, list[int]] = {pid: [] for pid in pids}
    for entry in _system_handles():
        pid = int(entry.UniqueProcessId)
        if pid in by_pid:
            by_pid[pid].append(int(entry.HandleValue))
    for pid, values in by_pid.items():
        proc = _kernel32.OpenProcess(_PROCESS_DUP_HANDLE, False, pid)
        if not proc:
            continue
        try:
            for value in values:
                dup = wintypes.HANDLE()
                if not _kernel32.DuplicateHandle(
                    proc, wintypes.HANDLE(value), current, ctypes.byref(dup),
                    0, False, _DUPLICATE_SAME_ACCESS,
                ):
                    continue
                try:
                    if _kernel32.GetFileType(dup) != _FILE_TYPE_DISK:
                        continue
                    path_buf = ctypes.create_unicode_buffer(1024)
                    if not _kernel32.GetFinalPathNameByHandleW(dup, path_buf, len(path_buf), 0):
                        continue
                    got = path_buf.value.lower().replace("/", "\\")
                    if got.startswith("\\\\?\\"):
                        got = got[4:]
                    if got != wanted:
                        continue
                    size = ctypes.c_longlong()
                    if not _kernel32.GetFileSizeEx(dup, ctypes.byref(size)) or size.value <= 0:
                        continue
                    raw = ctypes.create_string_buffer(size.value)
                    read = wintypes.DWORD()
                    overlapped = _Overlapped()
                    if not _kernel32.ReadFile(
                        dup, raw, size.value, ctypes.byref(read), ctypes.byref(overlapped)
                    ):
                        continue
                    blob = raw.raw[: read.value]
                    if blob.startswith(b"SQLite format 3"):
                        return blob
                finally:
                    _kernel32.CloseHandle(dup)
        finally:
            _kernel32.CloseHandle(proc)
    raise OSError("banco de sessao do Claude ocupado")


def _cookie_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        return _read_locked(path)


def _claude_cookies(profile: Path) -> dict[str, str]:
    state = json.loads((profile / "Local State").read_text(encoding="utf-8"))
    raw_key = base64.b64decode(state["os_crypt"]["encrypted_key"])
    key = _dpapi(raw_key[5:])
    blob = _cookie_bytes(profile / "Network" / "Cookies")
    with tempfile.TemporaryDirectory() as folder:
        db_path = Path(folder) / "Cookies"
        db_path.write_bytes(blob)
        con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT host_key, name, value, encrypted_value FROM cookies"
            ).fetchall()
        finally:
            con.close()
    found: dict[str, str] = {}
    for host, name, value, encrypted in rows:
        if "claude.ai" not in (host or ""):
            continue
        try:
            text = value if value else _decrypt(key, bytes(encrypted))
        except Exception:
            continue
        text = text.strip()
        if text:
            found[name] = text
    if not found.get("sessionKey", "").startswith("sk-ant-"):
        raise RuntimeError("Claude sem sessao")
    if not found.get("lastActiveOrg"):
        raise RuntimeError("Claude sem organizacao")
    return found


def _usage_url(org: str) -> str:
    from usage_quota import load_screen_config

    template = (load_screen_config().get("claudeUsageUrl") or "").strip()
    if "{org}" not in template:
        raise RuntimeError("config/screen.json sem url do Claude")
    return template.format(org=org)


def fetch_claude_usage(force: bool = False) -> dict:
    """Semana (todos os modelos) e sessao, em porcentagem."""
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if not force and _CACHE is not None and now - _CACHE_AT < _CACHE_TTL_S:
        return _CACHE

    try:
        profile = _profile()
        cookies = _claude_cookies(profile)
        org = cookies["lastActiveOrg"]
        header = "; ".join(f"{name}={value}" for name, value in cookies.items())
        resp = curl.get(
            _usage_url(org),
            headers={"Cookie": header, "Accept": "application/json"},
            impersonate="chrome",
            timeout=20,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"cota respondeu {resp.status_code}")
        payload = resp.json()
    except Exception:
        result = _fail()
        _CACHE, _CACHE_AT = result, now
        return result

    week = session = None
    reset = None
    for item in payload.get("limits") or []:
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "weekly_all":
            week = _num(item.get("percent"))
            reset = item.get("resets_at")
        elif item.get("kind") == "session":
            session = _num(item.get("percent"))
    seven = payload.get("seven_day") if isinstance(payload.get("seven_day"), dict) else {}
    five = payload.get("five_hour") if isinstance(payload.get("five_hour"), dict) else {}
    if week is None:
        week = _num(seven.get("utilization"))
        reset = seven.get("resets_at")
    if session is None:
        session = _num(five.get("utilization"))
    if week is None or session is None:
        result = _fail()
        _CACHE, _CACHE_AT = result, now
        return result

    result = {
        "ok": True,
        "source": "claude",
        "week_pct": week,
        "session_pct": session,
        "reset_label": _reset_label(reset if isinstance(reset, str) else None),
    }
    _CACHE, _CACHE_AT = result, now
    return result
