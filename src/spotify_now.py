"""Faixa atual do Spotify, lida da sessão de mídia do Windows.

O nome do executável vem de config/screen.json (spotifyApps). Não há token
nem conta gravada neste projeto.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

# GlobalSystemMediaTransportControlsSessionPlaybackStatus
_PLAYING = 4
_PAUSED = 5

def _tokens(app_names: list[str]) -> list[str]:
    return [Path(name).stem.lower() for name in app_names if Path(name).stem]


def _empty() -> dict:
    return {"playing": False, "paused": False, "title": "", "artist": ""}


async def _read(tokens: list[str]) -> dict:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager,
    )

    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    for session in manager.get_sessions():
        app_id = (session.source_app_user_model_id or "").lower()
        if not any(token in app_id for token in tokens):
            continue
        props = await session.try_get_media_properties_async()
        status = int(session.get_playback_info().playback_status)
        title = (props.title or "").strip() if props is not None else ""
        artist = (props.artist or "").strip() if props is not None else ""
        return {
            "playing": status == _PLAYING,
            "paused": status == _PAUSED,
            "title": title,
            "artist": artist,
        }
    return _empty()


_cache = _empty()
_cache_lock = threading.Lock()
_reader: threading.Thread | None = None
_reader_started = 0.0
# A sessão de mídia do Windows às vezes não responde. A tela não fica presa nisso.
_WAIT_S = 0.6


def _refresh(tokens: list[str]) -> None:
    global _cache
    try:
        value = asyncio.run(_read(tokens))
    except Exception:
        return
    with _cache_lock:
        _cache = value


def spotify_now(app_names: list[str]) -> dict:
    """Título, artista e se está tocando. Vazio se o Spotify não tiver faixa."""
    global _reader, _reader_started
    tokens = _tokens(app_names)
    if not tokens:
        return _empty()
    with _cache_lock:
        reader = _reader
        if reader is None or not reader.is_alive():
            _reader_started = time.monotonic()
            reader = threading.Thread(target=_refresh, args=(tokens,), daemon=True)
            _reader = reader
            reader.start()
        started = _reader_started
        cached = dict(_cache)
    if reader.is_alive() and time.monotonic() - started >= _WAIT_S:
        return cached
    reader.join(_WAIT_S)
    with _cache_lock:
        return dict(_cache)
