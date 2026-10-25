"""Faixa atual do Spotify, lida da sessão de mídia do Windows.

O nome do executável vem de config/screen.json (spotifyApps). Não há token
nem conta gravada neste projeto.
"""

from __future__ import annotations

import asyncio
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


def spotify_now(app_names: list[str]) -> dict:
    """Título, artista e se está tocando. Vazio se o Spotify não tiver faixa."""
    tokens = _tokens(app_names)
    if not tokens:
        return _empty()
    try:
        return asyncio.run(_read(tokens))
    except Exception:
        return _empty()
