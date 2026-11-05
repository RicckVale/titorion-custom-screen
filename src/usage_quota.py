"""Uso do ciclo da conta do Cursor, lido da sessao local do editor.

O token fica no state.vscdb do proprio Cursor. Nas versoes recentes ele vem
cifrado (cursor-safe-storage). A leitura decifra na memoria e nao grava o
token neste projeto.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import sqlite3
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ROOT = Path(__file__).resolve().parents[1]
_CACHE: dict | None = None
_CACHE_AT = 0.0
_CACHE_TTL_S = 60.0
_SAFE_PREFIX = "cursor-safe-storage:v1:"

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


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


def _storage_key(cursor_root: Path) -> bytes:
    state_path = cursor_root / "Local State"
    if not state_path.is_file():
        raise RuntimeError("chave da sessao do Cursor nao encontrada")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    raw_key = base64.b64decode((state.get("os_crypt") or {}).get("encrypted_key") or "")
    if not raw_key.startswith(b"DPAPI"):
        raise RuntimeError("chave da sessao do Cursor ilegivel")
    return _dpapi(raw_key[5:])


def _open_session(value: str, cursor_root: Path) -> str:
    token = value.strip()
    if not token.startswith("cursor-safe-storage:"):
        return token
    if not token.startswith(_SAFE_PREFIX):
        raise RuntimeError("sessao do Cursor cifrada numa versao desconhecida")
    blob = base64.b64decode(token[len(_SAFE_PREFIX):])
    if blob[:3] in (b"v10", b"v11"):
        plain = AESGCM(_storage_key(cursor_root)).decrypt(blob[3:15], blob[15:], None)
    else:
        plain = _dpapi(blob)
    text = plain.decode("utf-8").strip("\x00").strip()
    if not text:
        raise RuntimeError("Cursor sem sessao")
    return text


def load_screen_config() -> dict:
    path = _ROOT / "config" / "screen.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    apps = data.get("programmingApps") or []
    url = (data.get("usageUrl") or "").strip()
    if not apps or not url:
        raise RuntimeError(f"config/screen.json incompleto: {path}")
    claude_url = (data.get("claudeUsageUrl") or "").strip()
    if "{org}" not in claude_url:
        raise RuntimeError(f"config/screen.json sem url do Claude: {path}")
    antigravity_url = (data.get("antigravityUsageUrl") or "").strip()
    if not antigravity_url:
        raise RuntimeError(f"config/screen.json sem url do Antigravity: {path}")
    discord_apps = data.get("discordApps") or []
    spotify_apps = data.get("spotifyApps") or []
    league_apps = data.get("leagueApps") or []
    return {
        "programmingApps": list(apps),
        "usageUrl": url,
        "claudeUsageUrl": claude_url,
        "antigravityUsageUrl": antigravity_url,
        "discordApps": [str(name) for name in discord_apps if str(name).strip()],
        "spotifyApps": [str(name) for name in spotify_apps if str(name).strip()],
        "leagueApps": [str(name) for name in league_apps if str(name).strip()],
        "leagueLiveUrl": str(data.get("leagueLiveUrl") or "").strip(),
        "weatherCity": str(data.get("weatherCity") or "").strip(),
        "weatherTurnSeconds": data.get("weatherTurnSeconds"),
    }


def _cursor_token() -> str:
    root = os.environ.get("APPDATA")
    if not root:
        raise RuntimeError("APPDATA nao definido")
    cursor_root = Path(root) / "Cursor"
    db_path = cursor_root / "User" / "globalStorage" / "state.vscdb"
    if not db_path.is_file():
        raise RuntimeError("sessao do Cursor nao encontrada")
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT value FROM ItemTable WHERE key = 'cursorAuth/accessToken'"
        ).fetchone()
    finally:
        con.close()
    token = (row[0] if row else "") or ""
    if not str(token).strip():
        raise RuntimeError("Cursor sem sessao")
    return _open_session(str(token), cursor_root)


def _pct(value) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def fetch_period_usage(force: bool = False) -> dict:
    """Cota do ciclo de cobranca. Campos em porcentagem, nao em token cru.

    A API do Cursor devolve o uso incluido do plano (ciclo mensal nas contas
    legadas) e os percentuais de API e Auto. Nao ha um contador de tokens
    nesse endpoint.
    """
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if not force and _CACHE is not None and now - _CACHE_AT < _CACHE_TTL_S:
        return _CACHE

    cfg = load_screen_config()
    token = _cursor_token()
    req = urllib.request.Request(
        cfg["usageUrl"],
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        result = {"ok": False, "error": "sem leitura da cota"}
        _CACHE, _CACHE_AT = result, now
        return result

    plan = payload.get("planUsage") or {}
    limit = _pct(plan.get("limit"))
    included = _pct(plan.get("includedSpend"))
    included_pct = min(100.0, included / limit * 100.0) if limit else 0.0
    end_ms = _pct(payload.get("billingCycleEnd"))
    days_left = 0
    if end_ms:
        days_left = max(0, int((end_ms / 1000 - time.time()) / 86400))

    result = {
        "ok": True,
        "included_pct": included_pct,
        "api_pct": _pct(plan.get("apiPercentUsed")),
        "auto_pct": _pct(plan.get("autoPercentUsed")),
        "days_left": days_left,
    }
    _CACHE, _CACHE_AT = result, now
    return result
