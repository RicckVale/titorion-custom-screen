"""Estado ao vivo do Discord desktop: online, chamada e microfone.

Não grava token nem nome de canal. A lista de executáveis vem de
config/screen.json (discordApps).
"""

from __future__ import annotations

import socket
from pathlib import Path

import psutil

_ACTIVE = 1


def _pids(app_names: list[str]) -> set[int]:
    wanted = {Path(name).name.lower() for name in app_names if name}
    if not wanted:
        return set()
    found: set[int] = set()
    for proc in psutil.process_iter(["name"]):
        if (proc.info["name"] or "").lower() in wanted:
            found.add(proc.pid)
    return found


def _network(pids: set[int]) -> tuple[bool, bool]:
    """TCP estabelecido = online. UDP com outro lado = conversa de voz."""
    online = False
    in_call = False
    for conn in psutil.net_connections(kind="inet"):
        if conn.pid not in pids or not conn.raddr:
            continue
        if conn.type == socket.SOCK_STREAM and conn.status == psutil.CONN_ESTABLISHED:
            online = True
        elif conn.type == socket.SOCK_DGRAM:
            in_call = True
    return online or in_call, in_call


def _mic_open(pids: set[int]) -> bool | None:
    """Mute da sessão de captura do Discord. None se o Windows não contar."""
    try:
        import comtypes
        from pycaw.api.audiopolicy import IAudioSessionControl2, ISimpleAudioVolume
        from pycaw.pycaw import AudioUtilities

        comtypes.CoInitialize()
        mic = AudioUtilities.CreateDevice(AudioUtilities.GetMicrophone())
        if mic is None:
            return None
        enum = mic.AudioSessionManager.GetSessionEnumerator()
        seen = False
        open_mic = False
        for index in range(enum.GetCount()):
            ctl = enum.GetSession(index)
            if ctl is None:
                continue
            session = ctl.QueryInterface(IAudioSessionControl2)
            if session.GetProcessId() not in pids:
                continue
            seen = True
            muted = bool(session.QueryInterface(ISimpleAudioVolume).GetMute())
            if session.GetState() == _ACTIVE and not muted:
                open_mic = True
        if not seen:
            return False
        return open_mic
    except Exception:
        return None


def discord_snapshot(app_names: list[str]) -> dict:
    """open, online, in_call e mic_open (True, False ou None fora de chamada)."""
    pids = _pids(app_names)
    if not pids:
        return {"open": False, "online": False, "in_call": False, "mic_open": None}
    try:
        online, in_call = _network(pids)
    except (psutil.Error, OSError):
        online, in_call = False, False
    mic_open = _mic_open(pids) if in_call else None
    return {
        "open": True,
        "online": online,
        "in_call": in_call,
        "mic_open": mic_open,
    }
