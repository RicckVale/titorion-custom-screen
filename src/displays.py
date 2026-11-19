"""Manda o mesmo cartaz para todas as telas ligadas em config/screen.json.

"displays": ["keyboard", "clock"] escolhe as telas. "clockHost" é o último IP
em que o relógio respondeu: se esse IP calar, a rede local é varrida.
Sem "displays", só o teclado. O relógio que cai sai da lista até o próximo
connect(). O teclado permanece: a porta USB pode voltar no envio seguinte.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from clock_screen import ClockScreen, resolve_clock_host
from titorion_screen import TitorionScreen

_CONFIG = Path(__file__).resolve().parents[1] / "config" / "screen.json"
_LABEL = {"keyboard": "teclado", "clock": "relógio"}


def _config() -> dict:
    try:
        return json.loads(_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


class Displays:
    """Mesma interface do TitorionScreen, repassada para cada tela."""

    def __init__(self, on_error: Callable[[str], None] | None = None):
        self.on_error = on_error or (lambda _msg: None)
        self._screens: dict[str, object] = {}
        self.keyboard_down = False

    def endpoint(self, kind: str) -> str:
        screen = self._screens.get(kind)
        return str(getattr(screen, "base", "") or "")

    @property
    def names(self) -> list[str]:
        return list(self._screens)

    def connect(self) -> None:
        cfg = _config()
        wanted = cfg.get("displays") or ["keyboard"]
        errors = []
        for kind in wanted:
            if kind == "keyboard":
                screen = TitorionScreen()
            elif kind == "clock":
                host = resolve_clock_host()
                if not host:
                    errors.append("relógio: não encontrado na rede")
                    continue
                screen = ClockScreen(host)
            else:
                errors.append(f"{kind}: tela desconhecida")
                continue
            try:
                screen.connect()
            except Exception as e:
                errors.append(f"{_LABEL.get(kind, kind)}: {e}")
                continue
            self._screens[kind] = screen
        if not self._screens:
            raise RuntimeError("; ".join(errors) or "nenhuma tela em config/screen.json")
        if "keyboard" in wanted and "keyboard" not in self._screens:
            self.keyboard_down = True
        for msg in errors:
            self.on_error(msg)

    def _ensure_keyboard(self) -> None:
        """Abre o teclado se ele entrou depois, numa porta USB nova."""
        wanted = _config().get("displays") or ["keyboard"]
        if "keyboard" not in wanted or "keyboard" in self._screens:
            return
        screen = TitorionScreen()
        try:
            screen.connect()
        except Exception:
            self.keyboard_down = True
            return
        self._screens = {"keyboard": screen, **self._screens}
        self.keyboard_down = False

    def close(self) -> None:
        for kind, screen in list(self._screens.items()):
            try:
                screen.close()
            except Exception as e:
                self.on_error(f"{_LABEL.get(kind, kind)}: {e}")
        self._screens.clear()

    def _each(self, method: str, image, only: set[str] | None = None) -> None:
        if (only is None or "keyboard" in only) and "keyboard" not in self._screens:
            self._ensure_keyboard()
        for kind, screen in list(self._screens.items()):
            if only and kind not in only:
                continue
            try:
                getattr(screen, method)(image)
            except Exception as e:
                if kind == "keyboard":
                    # Não tira o teclado da lista: a porta USB pode voltar já.
                    self.keyboard_down = True
                    if list(self._screens) == ["keyboard"]:
                        raise
                    self.on_error(f"teclado: {e}")
                    continue
                if len(self._screens) == 1:
                    raise
                del self._screens[kind]
                self.on_error(f"{_LABEL.get(kind, kind)} saiu: {e}")
                continue
            if kind == "keyboard":
                self.keyboard_down = False

    def send_image(self, image, only: set[str] | None = None) -> None:
        self._each("send_image", image, only)

    def reset_gallery(self, image) -> None:
        self._each("reset_gallery", image)
