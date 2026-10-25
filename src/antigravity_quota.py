"""Cota da conta do Antigravity aberta neste computador.

O login fica no cofre de credenciais do Windows, no alvo que o próprio
aplicativo grava. O token não é copiado para este projeto.
"""

from __future__ import annotations

import ctypes
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

_CACHE: dict | None = None
_CACHE_AT = 0.0
_CACHE_TTL_S = 60.0
_CRED_TARGET = "gemini:antigravity"


class _FileTime(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FileTime),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_advapi = ctypes.WinDLL("advapi32")
_advapi.CredReadW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.POINTER(ctypes.POINTER(_Credential)),
]
_advapi.CredReadW.restype = wintypes.BOOL
_advapi.CredFree.argtypes = [ctypes.c_void_p]


def _fail() -> dict:
    return {"ok": False, "source": "antigravity", "error": "sem leitura da cota"}


def _reset_label(iso: str) -> str:
    if not iso:
        return "--"
    try:
        reset = datetime.fromisoformat(iso.replace("Z", "+00:00"))
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


def _access_token() -> str:
    out = ctypes.POINTER(_Credential)()
    if not _advapi.CredReadW(_CRED_TARGET, 1, 0, ctypes.byref(out)):
        raise RuntimeError("Antigravity sem sessao")
    try:
        blob = ctypes.string_at(out.contents.CredentialBlob, out.contents.CredentialBlobSize)
    finally:
        _advapi.CredFree(out)
    payload = json.loads(blob.decode("utf-8"))
    token = payload.get("token") if isinstance(payload, dict) else None
    access = token.get("access_token") if isinstance(token, dict) else ""
    if not str(access).strip():
        raise RuntimeError("Antigravity sem sessao")
    return str(access)


def _group_label(name: str) -> str:
    """O grupo da página de uso, não o nome de um modelo."""
    text = name.casefold()
    if "argon" in text:
        return "ARGON"
    if "gemini" in text:
        return "GEMINI"
    if "claude" in text or "gpt" in text:
        return "C+GPT"
    word = name.strip().split(" ", 1)[0]
    return (word or "COTA").upper()[:8]


def _window_kind(bucket: dict) -> str:
    window = str(bucket.get("window") or "").casefold()
    name = str(bucket.get("displayName") or "").casefold()
    if window in {"5h", "five_hour"} or "five hour" in name or "5h" in window:
        return "5h"
    return "weekly"


def _remaining_pct(bucket: dict) -> float | None:
    remaining = bucket.get("remainingFraction")
    if remaining is None and isinstance(bucket.get("remaining"), dict):
        remaining = bucket["remaining"].get("value")
    if not isinstance(remaining, (int, float)):
        return None
    return max(0.0, min(100.0, float(remaining) * 100.0))


def _groups_from(payload: dict) -> list[dict]:
    body = payload.get("response") if isinstance(payload.get("response"), dict) else payload
    groups = body.get("groups") if isinstance(body, dict) else None
    if not isinstance(groups, list):
        return []
    rows: list[dict] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        buckets: list[dict] = []
        for bucket in group.get("buckets") or []:
            if not isinstance(bucket, dict):
                continue
            remaining = _remaining_pct(bucket)
            if remaining is None:
                continue
            buckets.append({
                "window": _window_kind(bucket),
                "remaining_pct": remaining,
                "reset": str(bucket.get("resetTime") or ""),
            })
        if not buckets:
            continue
        order = {"weekly": 0, "5h": 1}
        buckets.sort(key=lambda item: order.get(item["window"], 9))
        rows.append({
            "label": _group_label(str(group.get("displayName") or "")),
            "buckets": buckets[:2],
        })
    return rows


def _soonest_reset(groups: list[dict]) -> str:
    resets = [
        bucket["reset"]
        for group in groups
        for bucket in group["buckets"]
        if bucket.get("reset")
    ]
    if not resets:
        return "--"

    def when(iso: str) -> float:
        try:
            moment = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            return float("inf")
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.timestamp()

    return _reset_label(min(resets, key=when))


def _file_version(path: Path) -> str:
    if not path.is_file():
        return ""
    size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return ""
    buf = ctypes.create_string_buffer(size)
    if not ctypes.windll.version.GetFileVersionInfoW(str(path), 0, size, buf):
        return ""

    class _Fixed(ctypes.Structure):
        _fields_ = [
            ("dwSignature", wintypes.DWORD),
            ("dwStrucVersion", wintypes.DWORD),
            ("dwFileVersionMS", wintypes.DWORD),
            ("dwFileVersionLS", wintypes.DWORD),
            ("dwProductVersionMS", wintypes.DWORD),
            ("dwProductVersionLS", wintypes.DWORD),
            ("dwFileFlagsMask", wintypes.DWORD),
            ("dwFileFlags", wintypes.DWORD),
            ("dwFileOS", wintypes.DWORD),
            ("dwFileType", wintypes.DWORD),
            ("dwFileSubtype", wintypes.DWORD),
            ("dwFileDateMS", wintypes.DWORD),
            ("dwFileDateLS", wintypes.DWORD),
        ]

    pointer = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not ctypes.windll.version.VerQueryValueW(buf, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        return ""
    info = ctypes.cast(pointer, ctypes.POINTER(_Fixed)).contents
    major = (info.dwFileVersionMS >> 16) & 0xFFFF
    minor = info.dwFileVersionMS & 0xFFFF
    patch = (info.dwFileVersionLS >> 16) & 0xFFFF
    return f"{major}.{minor}.{patch}"


def _user_agent() -> str:
    """A versão instalada entra no agente. Sem ela a resposta omite o grupo Gemini."""
    version = _file_version(
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "antigravity" / "Antigravity.exe"
    )
    return f"antigravity/{version}" if version else "antigravity"


def _language_server() -> tuple[str, list[int]]:
    """Portas locais do Antigravity aberto. O segredo do processo não sai daqui."""
    import psutil

    for proc in psutil.process_iter(["name", "cmdline"]):
        if (proc.info["name"] or "").lower() != "language_server.exe":
            continue
        token = ""
        parts = proc.info["cmdline"] or []
        for index, part in enumerate(parts):
            if part == "--csrf_token" and index + 1 < len(parts):
                token = parts[index + 1]
            elif part.startswith("--csrf_token="):
                token = part.split("=", 1)[1]
        ports: list[int] = []
        try:
            for conn in proc.net_connections(kind="tcp"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr:
                    ports.append(int(conn.laddr.port))
        except (psutil.AccessDenied, OSError):
            ports = []
        return token, ports
    return "", []


def _from_language_server() -> dict | None:
    """A mesma leitura da página Models & Usage, no servidor local do app aberto."""
    token, ports = _language_server()
    if not token or not ports:
        return None
    body = json.dumps({"forceRefresh": False}).encode("utf-8")
    context = ssl._create_unverified_context()
    path = "/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
    for port in ports:
        for scheme in ("http", "https"):
            request = urllib.request.Request(
                f"{scheme}://127.0.0.1:{port}{path}",
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Connect-Protocol-Version": "1",
                    "x-codeium-csrf-token": token,
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=4, context=context) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (OSError, json.JSONDecodeError, urllib.error.URLError):
                continue
            if _groups_from(payload):
                return payload
    return None


def _from_cloud() -> dict:
    from usage_quota import load_screen_config

    url = (load_screen_config().get("antigravityUsageUrl") or "").strip()
    if not url:
        raise RuntimeError("config/screen.json sem url do Antigravity")
    request = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {_access_token()}",
            "Content-Type": "application/json",
            "User-Agent": _user_agent(),
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_antigravity_usage(force: bool = False) -> dict:
    """O que ainda resta em cada grupo, como na página de uso do Antigravity."""
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if not force and _CACHE is not None and now - _CACHE_AT < _CACHE_TTL_S:
        return _CACHE

    groups: list[dict] = []
    try:
        payload = _from_language_server()
        if payload is None:
            payload = _from_cloud()
        groups = _groups_from(payload)
        if not groups:
            raise RuntimeError("cota sem grupos")
    except Exception:
        result = _fail()
        _CACHE, _CACHE_AT = result, now
        return result

    result = {
        "ok": True,
        "source": "antigravity",
        "groups": groups,
        "reset_label": _soonest_reset(groups),
    }
    _CACHE, _CACHE_AT = result, now
    return result
