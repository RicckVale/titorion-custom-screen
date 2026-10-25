"""Uso do ciclo da conta do Cursor, lido da sessao local do editor.

O token fica no state.vscdb do proprio Cursor. Nao e gravado neste projeto.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CACHE: dict | None = None
_CACHE_AT = 0.0
_CACHE_TTL_S = 60.0


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
    language = str(data.get("language") or "pt").strip().lower()
    if language not in ("pt", "en"):
        language = "pt"
    discord_apps = data.get("discordApps") or []
    spotify_apps = data.get("spotifyApps") or []
    league_apps = data.get("leagueApps") or []
    return {
        "programmingApps": list(apps),
        "usageUrl": url,
        "claudeUsageUrl": claude_url,
        "language": language,
        "discordApps": [str(name) for name in discord_apps if str(name).strip()],
        "spotifyApps": [str(name) for name in spotify_apps if str(name).strip()],
        "leagueApps": [str(name) for name in league_apps if str(name).strip()],
        "leagueLiveUrl": str(data.get("leagueLiveUrl") or "").strip(),
    }


def _cursor_token() -> str:
    root = os.environ.get("APPDATA")
    if not root:
        raise RuntimeError("APPDATA nao definido")
    db_path = Path(root) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
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
    return str(token)


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
