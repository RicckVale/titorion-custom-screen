"""
check_clock.py — Confere o relógio Wi-Fi. Se o IP em config/screen.json não
responder, procura na rede local e grava o novo.

Uso:
    python src/check_clock.py            # lê temas e fotos (não manda cartaz)
    python src/check_clock.py --send     # manda um cartaz vermelho e um verde, depois devolve o relógio
"""

import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

from clock_screen import ClockScreen, normalize_host, resolve_clock_host

_CONFIG = Path(__file__).resolve().parents[1] / "config" / "screen.json"
_HOLD_S = 12  # slideshow troca a cada 5 s; dá tempo de ver cada cor


def _card(color: tuple, label: str) -> Image.Image:
    img = Image.new("RGB", (128, 128), color)
    ImageDraw.Draw(img).text((8, 56), label, fill=(255, 255, 255))
    return img


def main() -> None:
    before = ""
    try:
        before = normalize_host(
            str(json.loads(_CONFIG.read_text(encoding="utf-8")).get("clockHost") or "")
        )
    except (OSError, json.JSONDecodeError):
        before = ""
    host = resolve_clock_host()
    if not host:
        print("Não achei o relógio na rede. Confira se ele está no Wi-Fi.")
        sys.exit(1)
    if host != before:
        print(f"IP anterior não respondeu. Relógio em {host} (gravado em config/screen.json).")

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
