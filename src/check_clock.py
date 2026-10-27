"""
check_clock.py — Confere o relógio Wi-Fi configurado em config/screen.json (clockHost).

Uso:
    python src/check_clock.py            # só lê temas e fotos (não muda nada)
    python src/check_clock.py --send     # manda um cartaz vermelho e um verde, depois devolve o relógio
"""

import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

from clock_screen import ClockScreen

_CONFIG = Path(__file__).resolve().parents[1] / "config" / "screen.json"
_HOLD_S = 12  # slideshow troca a cada 5 s; dá tempo de ver cada cor


def _card(color: tuple, label: str) -> Image.Image:
    img = Image.new("RGB", (128, 128), color)
    ImageDraw.Draw(img).text((8, 56), label, fill=(255, 255, 255))
    return img


def main() -> None:
    host = json.loads(_CONFIG.read_text(encoding="utf-8")).get("clockHost") or ""
    if not host:
        print("config/screen.json sem clockHost (ex.: \"192.168.25.62\").")
        sys.exit(1)

    clock = ClockScreen(host)
    themes = clock._get_json("/theme/list")
    photos = clock._get_json("/photo/list")
    print(f"Relógio em {clock.base}")
    print("Temas ligados:", [t["name"] for t in themes["themes"] if t.get("enabled")])
    print("Fotos:", [(f["name"], f.get("enabled")) for f in photos["files"]])
    print(f"Memória: {photos['used']} / {photos['total']} bytes")

    if "--send" not in sys.argv:
        return

    print("Deixando o relógio só no tema Photo...")
    with clock:
        for color, label in (((200, 0, 0), "TESTE VERMELHO"), ((0, 160, 0), "TESTE VERDE")):
            print(f"Enviando {label.lower()}... (olhe o relógio)")
            clock.send_image(_card(color, label))
            time.sleep(_HOLD_S)
        print("Devolvendo temas e fotos como estavam...")
    print("Pronto.")


if __name__ == "__main__":
    main()
