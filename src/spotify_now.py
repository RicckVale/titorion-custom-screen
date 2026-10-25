"""Faixa atual do Spotify.

O nome do executável vem de config/screen.json (spotifyApps). Não há token
nem conta gravada neste projeto. A sessão de mídia do Windows às vezes não
responde, então o nome sai da janela e o "tocando" sai do áudio que o
processo está emitindo. A capa ainda vem da sessão de mídia, quando ela volta.
"""

from __future__ import annotations

import asyncio
import ctypes
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path

# GlobalSystemMediaTransportControlsSessionPlaybackStatus
_PLAYING = 4
_PAUSED = 5
# AudioSessionState.Active
_ACTIVE = 1
# Pico abaixo disso é silêncio. Um trecho baixo não tira o cartaz na hora.
_PEAK = 0.02
_HOLD_S = 3.0
_GENERIC = {"spotify", "spotify premium", "spotify free"}

_user32 = ctypes.windll.user32
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def _tokens(app_names: list[str]) -> list[str]:
    return [Path(name).stem.lower() for name in app_names if Path(name).stem]


def _empty() -> dict:
    return {"playing": False, "paused": False, "title": "", "artist": ""}


def _pids(app_names: list[str]) -> set[int]:
    import psutil

    wanted = {Path(name).name.lower() for name in app_names if name}
    if not wanted:
        return set()
    found: set[int] = set()
    for proc in psutil.process_iter(["name", "pid"]):
        if (proc.info["name"] or "").lower() in wanted:
            pid = proc.info["pid"]
            if isinstance(pid, int):
                found.add(pid)
    return found


def _window_titles(pids: set[int]) -> list[str]:
    found: list[str] = []

    def visit(hwnd: int, _lparam: int) -> bool:
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids or not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if title:
            found.append(title)
        return True

    _user32.EnumWindows(_WNDENUMPROC(visit), 0)
    return found


def _song(titles: list[str]) -> tuple[str, str]:
    """A janela do Spotify no Windows vem como 'artista - faixa'."""
    named = [title for title in titles if title.casefold() not in _GENERIC]
    chosen = ""
    for title in named:
        if " - " in title:
            chosen = title
            break
    if not chosen and named:
        chosen = named[0]
    if not chosen:
        return "", ""
    if " - " not in chosen:
        return chosen, ""
    artist, title = chosen.split(" - ", 1)
    return title.strip(), artist.strip()


_com = threading.local()
_heard_at = 0.0
_meter_type = None


def _peak_meter():
    """Interface do pico da sessão de áudio, criada uma vez."""
    global _meter_type
    if _meter_type is not None:
        return _meter_type
    import comtypes
    from comtypes import GUID, IUnknown
    from ctypes import POINTER, c_float

    class IAudioMeterInformation(IUnknown):
        _iid_ = GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
        _methods_ = [
            comtypes.COMMETHOD(
                [],
                comtypes.HRESULT,
                "GetPeakValue",
                (["out"], POINTER(c_float), "pfPeak"),
            ),
        ]

    _meter_type = IAudioMeterInformation
    return _meter_type


def _audible(pids: set[int]) -> bool:
    """True enquanto o Spotify emite som. A pausa zera a sessão."""
    global _heard_at
    try:
        import comtypes
        from pycaw.api.audiopolicy import IAudioSessionControl2
        from pycaw.pycaw import AudioUtilities

        meter_type = _peak_meter()
        if not getattr(_com, "ok", False):
            comtypes.CoInitialize()
            _com.ok = True
        now = time.monotonic()
        active = False
        loud = False
        for session in AudioUtilities.GetAllSessions():
            proc = session.Process
            if proc is None or proc.pid not in pids:
                continue
            ctl = session._ctl.QueryInterface(IAudioSessionControl2)
            if int(ctl.GetState()) != _ACTIVE:
                continue
            active = True
            meter = ctl.QueryInterface(meter_type)
            if float(meter.GetPeakValue()) >= _PEAK:
                loud = True
        if loud:
            _heard_at = now
            return True
        if active and _heard_at > 0 and now - _heard_at <= _HOLD_S:
            return True
        return False
    except Exception:
        return False


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
            "cover": await _cover(props),
        }
    return _empty()


async def _cover(props: object) -> bytes | None:
    """Bytes da capa na sessão de mídia. None se o player não mandar."""
    thumb = getattr(props, "thumbnail", None)
    if thumb is None:
        return None
    try:
        from winrt.windows.storage.streams import DataReader

        stream = await thumb.open_read_async()
        size = int(stream.size)
        if size <= 0 or size > 1_500_000:
            return None
        reader = DataReader(stream)
        await reader.load_async(size)
        raw = reader.read_bytes(reader.unconsumed_buffer_length)
        reader.close()
    except Exception:
        return None
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return bytes(raw)


_cache = _empty()
_cache_lock = threading.Lock()
_reader: threading.Thread | None = None


def _refresh(tokens: list[str]) -> None:
    global _cache
    try:
        value = asyncio.run(_read(tokens))
    except Exception:
        return
    with _cache_lock:
        _cache = value


def _media_extra(title: str) -> tuple[str, bytes | None]:
    """Artista e capa da sessão de mídia, se forem da mesma faixa.

    A leitura dessa sessão não trava a tela. Se ela não responder, fica o nome da janela.
    """
    with _cache_lock:
        cached_title = str(_cache.get("title") or "")
        cached_artist = str(_cache.get("artist") or "")
        cover = _cache.get("cover")
    if not title or not cached_title or cached_title.casefold() != title.casefold():
        return "", None
    raw = bytes(cover) if isinstance(cover, (bytes, bytearray)) and cover else None
    return cached_artist, raw


def _artist_overlap(wanted: str, got: str) -> bool:
    left = wanted.casefold().strip()
    right = got.casefold().strip()
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    parts = re.split(r"[&,]|\se\s|\sfeat\.?\s|\sft\.?\s", right)
    return any(part.strip() and part.strip() in left for part in parts)


def _same_title(wanted: str, got: str) -> bool:
    return wanted.casefold().strip() == got.casefold().strip() and bool(wanted.strip())


def _pick_art(rows: list[tuple[str, str, str]], title: str, artist: str) -> str:
    """URL da capa quando o título fecha e o artista aparece no resultado."""
    hits = [url for got_title, got_artist, url in rows if url and _same_title(title, got_title)]
    if artist.strip():
        hits = [
            url
            for got_title, got_artist, url in rows
            if url and _same_title(title, got_title) and _artist_overlap(artist, got_artist)
        ]
    if not hits:
        return ""
    return hits[0]


def _itunes_art(title: str, artist: str) -> str:
    query = urllib.parse.urlencode({"term": f"{title} {artist}".strip(), "entity": "song", "limit": "5"})
    payload = _json(f"https://itunes.apple.com/search?{query}")
    rows = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("artworkUrl100") or "")
        rows.append((str(item.get("trackName") or ""), str(item.get("artistName") or ""), url))
    found = _pick_art(rows, title, artist)
    return found.replace("100x100bb", "600x600bb")


def _deezer_art(title: str, artist: str) -> str:
    query = urllib.parse.urlencode({"q": f"{title} {artist}".strip()})
    payload = _json(f"https://api.deezer.com/search?{query}")
    rows = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        album = item.get("album") if isinstance(item.get("album"), dict) else {}
        who = item.get("artist") if isinstance(item.get("artist"), dict) else {}
        rows.append((
            str(item.get("title") or ""),
            str(who.get("name") or ""),
            str(album.get("cover_xl") or ""),
        ))
    return _pick_art(rows, title, artist)


def _json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError, ValueError, TimeoutError):
        return {}
    return data if isinstance(data, dict) else {}


def _download(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"Accept": "image/*"})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            raw = response.read(1_500_001)
    except (OSError, ValueError, TimeoutError):
        return None
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < 32 or len(raw) > 1_500_000:
        return None
    if raw[:3] != b"\xff\xd8\xff" and raw[:8] != b"\x89PNG\r\n\x1a\n" and raw[:4] != b"RIFF":
        return None
    return bytes(raw)


def _download_art(title: str, artist: str) -> bytes | None:
    url = _itunes_art(title, artist) or _deezer_art(title, artist)
    if not url:
        return None
    return _download(url)


_art_lock = threading.Lock()
_art_key = ""
_art_bytes: bytes | None = None
_art_ready = False
_art_at = 0.0
_art_thread: threading.Thread | None = None
_ART_FAIL_S = 60.0


def _load_art(key: str, title: str, artist: str) -> None:
    global _art_bytes, _art_ready, _art_at
    try:
        raw = _download_art(title, artist)
    except Exception:
        raw = None
    with _art_lock:
        if _art_key != key:
            return
        _art_bytes = raw
        _art_ready = True
        _art_at = time.monotonic()


def _catalog_art(title: str, artist: str) -> bytes | None:
    """Capa da faixa no catálogo público. A tela não espera essa leitura."""
    global _art_key, _art_ready, _art_thread, _art_bytes
    if not title.strip():
        return None
    key = f"{title.casefold().strip()}|{artist.casefold().strip()}"
    with _art_lock:
        if key == _art_key and _art_ready:
            if _art_bytes is not None or time.monotonic() - _art_at < _ART_FAIL_S:
                return _art_bytes
        running = _art_thread is not None and _art_thread.is_alive()
        if running:
            return _art_bytes if key == _art_key else None
        _art_key = key
        _art_ready = False
        _art_bytes = None
        thread = threading.Thread(target=_load_art, args=(key, title, artist), daemon=True)
        _art_thread = thread
        thread.start()
    return None


def _kick(tokens: list[str]) -> None:
    global _reader
    if not tokens:
        return
    with _cache_lock:
        reader = _reader
        if reader is not None and reader.is_alive():
            return
        reader = threading.Thread(target=_refresh, args=(tokens,), daemon=True)
        _reader = reader
        reader.start()


def spotify_now(app_names: list[str]) -> dict:
    """Título, artista e se está tocando. Vazio se o Spotify não tiver faixa."""
    tokens = _tokens(app_names)
    if not tokens:
        return _empty()
    pids = _pids(app_names)
    if not pids:
        return _empty()
    title, artist = _song(_window_titles(pids))
    playing = _audible(pids)
    _kick(tokens)
    extra_artist, media_cover = _media_extra(title)
    if extra_artist:
        artist = extra_artist
    cover = media_cover or _catalog_art(title, artist)
    result = {
        "playing": playing,
        "paused": bool(title) and not playing,
        "title": title,
        "artist": artist,
    }
    if cover is not None:
        result["cover"] = cover
    return result
