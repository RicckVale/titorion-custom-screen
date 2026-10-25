"""Campeão da partida local do League.

A URL vem de config/screen.json (leagueLiveUrl). O jogo só responde com a
partida aberta. A resposta traz o nome do campeão e o nível, e não diz se
uma skill está pronta.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.request

_CACHE: dict | None = None
_CACHE_AT = 0.0
_MISS_TTL_S = 4.0
_HIT_TTL_S = 5.0
_SSL = ssl._create_unverified_context()


def league_champion(live_url: str) -> dict | None:
    """Campeão da pessoa na partida, ou None fora dela."""
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if _CACHE is not None and now - _CACHE_AT < (_HIT_TTL_S if _CACHE.get("ok") else _MISS_TTL_S):
        return _CACHE.get("match")
    match = _read(live_url)
    _CACHE = {"ok": match is not None, "match": match}
    _CACHE_AT = now
    return match


def _read(live_url: str) -> dict | None:
    base = live_url.rstrip("/")
    if not base:
        return None
    try:
        active = _get(f"{base}/activeplayer")
        players = _get(f"{base}/playerlist")
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(active, dict) or not isinstance(players, list):
        return None
    riot_id = str(active.get("riotId") or active.get("summonerName") or "").strip()
    player = _own_player(players, riot_id)
    if player is None:
        return None
    champion = _pretty(str(player.get("championName") or "").strip())
    if not champion:
        return None
    level = player.get("level")
    if not isinstance(level, int):
        level = active.get("level") if isinstance(active.get("level"), int) else None
    return {"champion": champion, "level": level}


def _own_player(players: list, riot_id: str) -> dict | None:
    wanted = riot_id.casefold()
    for player in players:
        if not isinstance(player, dict):
            continue
        names = (
            str(player.get("riotId") or ""),
            str(player.get("riotIdGameName") or ""),
            str(player.get("summonerName") or ""),
        )
        if wanted and any(name.casefold() == wanted for name in names if name):
            return player
    return None


def _pretty(name: str) -> str:
    if " " in name:
        return name
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).strip()


def _get(url: str) -> object:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=0.4, context=_SSL) as response:
        return json.loads(response.read().decode("utf-8"))
