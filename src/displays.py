"""Manda o mesmo cartaz para todas as telas ligadas em config/screen.json.

"displays": ["keyboard", "clock"] escolhe as telas; "clockHost" é o IP do relógio.
Sem "displays", só o teclado. Uma tela fora do ar não segura as outras: ela sai
da lista até o próximo connect() e o erro vai para on_error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from clock_screen import ClockScreen
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
            elif kind == "clock" and (cfg.get("clockHost") or "").strip():
                screen = ClockScreen(cfg["clockHost"])
            else:
                errors.append(f"{kind}: tela desconhecida ou sem clockHost")
                continue
            try:
                screen.connect()
            except Exception as e:
                errors.append(f"{_LABEL.get(kind, kind)}: {e}")
                continue
            self._screens[kind] = screen
        if not self._screens:
            raise RuntimeError("; ".join(errors) or "nenhuma tela em config/screen.json")
        for msg in errors:
            self.on_error(msg)

    def close(self) -> None:
        for kind, screen in list(self._screens.items()):
            try:
                screen.close()
            except Exception as e:
                self.on_error(f"{_LABEL.get(kind, kind)}: {e}")
        self._screens.clear()

    def _each(self, method: str, image) -> None:
        for kind, screen in list(self._screens.items()):
            try:
                getattr(screen, method)(image)
            except Exception as e:
                if len(self._screens) == 1:
                    raise
                del self._screens[kind]
                self.on_error(f"{_LABEL.get(kind, kind)} saiu: {e}")

    def send_image(self, image) -> None:
        self._each("send_image", image)

    def reset_gallery(self, image) -> None:
        self._each("reset_gallery", image)
