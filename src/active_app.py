"""Janela em foco no Windows. Sem dependencia extra alem do psutil."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

import psutil

_user32 = ctypes.windll.user32


def _foreground_hwnd() -> int:
    return int(_user32.GetForegroundWindow() or 0)


def foreground_process_name() -> str:
    """Nome do executavel da janela ativa, ex.: Cursor.exe. Vazio se nao der."""
    hwnd = _foreground_hwnd()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    try:
        return psutil.Process(pid.value).name()
    except (psutil.Error, OSError):
        return ""


def foreground_window_title() -> str:
    hwnd = _foreground_hwnd()
    if not hwnd:
        return ""
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def foreground_matches(names: list[str]) -> bool:
    """A janela da frente é um dos executáveis pedidos."""
    stem = Path(foreground_process_name()).stem.lower()
    wanted = {Path(name).stem.lower() for name in names if name}
    return bool(stem) and stem in wanted


def programming_app(watched: list[str]) -> str:
    """Nome amigavel se a janela da frente for Cursor, Claude, ou um site deles.

    Claude aberto atras do Cursor nao conta: a telinha segue quem esta na frente.
    """
    stem = Path(foreground_process_name()).stem.lower()
    title = foreground_window_title().lower()
    watched_stems = {Path(name).stem.lower() for name in watched}
    if stem == "cursor" or (stem in watched_stems and "cursor" in stem):
        return "Cursor"
    if "claude" in stem or "claude" in title:
        return "Claude"
    if stem in watched_stems:
        return stem.title()
    return ""
