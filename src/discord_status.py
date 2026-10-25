"""Estado ao vivo do Discord desktop: online, chamada e microfone.

Não grava token nem nome de canal. A lista de executáveis vem de
config/screen.json (discordApps). A voz do Discord usa UDP sem endereço
remoto visível, então a chamada sai do último estado no log do app.
"""

from __future__ import annotations

import os
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


def _online(pids: set[int]) -> bool:
    """TCP estabelecido: o app está na rede do Discord."""
    for conn in psutil.net_connections(kind="inet"):
        if conn.pid not in pids or not conn.raddr:
            continue
        if conn.type == socket.SOCK_STREAM and conn.status == psutil.CONN_ESTABLISHED:
            return True
    return False


def _last_voice_state(path: Path) -> bool | None:
    """Último estado decisivo do log. True se a voz terminou em CONNECTED."""
    if not path.is_file():
        return None
    size = path.stat().st_size
    pos = size
    pending = ""
    scanned = 0
    while pos > 0 and scanned < 4_000_000:
        take = min(262_144, pos)
        pos -= take
        scanned += take
        with path.open("rb") as handle:
            handle.seek(pos)
            block = handle.read(take).decode("utf-8", "replace") + pending
        lines = block.splitlines()
        if pos > 0 and lines:
            pending = lines[0]
            lines = lines[1:]
        else:
            pending = ""
        for line in reversed(lines):
            if "Connection state change" not in line and "RTC connection state:" not in line:
                continue
            if "=>" not in line:
                continue
            right = line.rsplit("=>", 1)[-1].strip().upper()
            if "DISCONNECTED" in right:
                return False
            if "CONNECTED" in right:
                return True
    return None


def _in_call(app_names: list[str]) -> bool:
    root = os.environ.get("APPDATA")
    if not root:
        return False
    for name in app_names:
        folder = Path(name).stem.lower()
        state = _last_voice_state(Path(root) / folder / "logs" / "renderer_js.log")
        if state is not None:
            return state
    return False


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
        online = _online(pids)
    except (psutil.Error, OSError):
        online = False
    in_call = _in_call(app_names)
    mic_open = _mic_open(pids) if in_call else None
    return {
        "open": True,
        "online": online,
        "in_call": in_call,
        "mic_open": mic_open,
    }
