"""
test_freeze.py — Teste de limite da tela: envia frames numerados (1..N)
em intervalo fixo para descobrir apos quantos uploads ela congela.

Uso:
    python src/test_freeze.py            # 30 frames, 1 a cada 5 s
    python src/test_freeze.py 40 10      # 40 frames, 1 a cada 10 s

Instrucoes: observe a telinha do teclado e anote o ULTIMO numero exibido
antes de ela parar de mudar. Compare com o log no terminal.
"""

import sys
import time
from datetime import datetime

from PIL import Image, ImageDraw

from stats_render import _font
from titorion_screen import TitorionScreen, SCREEN_W, SCREEN_H

FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 30
INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0


def render_number(n: int, total: int) -> Image.Image:
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), (12, 12, 20))
    d = ImageDraw.Draw(img)
    d.text((SCREEN_W // 2, 52), str(n), font=_font(64, bold=True),
           fill=(255, 255, 255), anchor="mm")
    d.text((SCREEN_W // 2, 106), f"de {total} · {datetime.now():%H:%M:%S}",
           font=_font(11), fill=(150, 150, 170), anchor="mm")
    return img


def main() -> None:
    print(f"Enviando {FRAMES} frames, 1 a cada {INTERVAL}s.")
    print(">>> OLHE A TELA DO TECLADO e anote o ultimo numero que mudar. <<<\n")
    with TitorionScreen() as screen:
        for n in range(1, FRAMES + 1):
            t0 = time.monotonic()
            screen.send_image(render_number(n, FRAMES))
            print(f"[{datetime.now():%H:%M:%S}] frame {n}/{FRAMES} enviado",
                  flush=True)
            elapsed = time.monotonic() - t0
            time.sleep(max(0.5, INTERVAL - elapsed))
    print("\nFim do teste. Qual foi o ultimo numero exibido na telinha?")


if __name__ == "__main__":
    main()
