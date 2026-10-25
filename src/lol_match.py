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
_TTL_S = 1.0
_SEEN_PID: int | None = None
_LAST_GOOD: dict | None = None
_SSL = ssl._create_unverified_context()


def league_champion(live_url: str, game_pid: int | None = None) -> dict | None:
    """Campeão da pessoa na partida, ou None fora dela.

    Um processo novo de partida descarta o campeão anterior. Se a leitura
    piscar com a mesma partida aberta, o último campeão continua valendo
    para a tela não sair no meio do jogo.
    """
    global _CACHE, _CACHE_AT, _SEEN_PID, _LAST_GOOD
    if game_pid != _SEEN_PID:
        _CACHE = None
        _LAST_GOOD = None
        _SEEN_PID = game_pid
    now = time.monotonic()
    if _CACHE is not None and now - _CACHE_AT < _TTL_S:
        return _CACHE.get("match")
    match = _read(live_url)
    if match is None and game_pid and _LAST_GOOD is not None:
        match = _LAST_GOOD
    elif match is not None:
        _LAST_GOOD = match
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
