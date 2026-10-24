"""
demo_stats.py — Mini-monitor em modo terminal (sem interface grafica).
Para a versao com interface, use:  python src/app.py

Uso:
    python src/demo_stats.py             # atualiza a cada 10 s
    python src/demo_stats.py --once      # envia uma vez e sai
    python src/demo_stats.py 5           # atualiza a cada 5 s

⚠️ Não use intervalos muito curtos até confirmarmos se a imagem vai para
flash ou RAM (docs/protocol.md §7).
"""

import sys
import time
from datetime import datetime

from stats_render import collect_stats, render
from titorion_screen import TitorionScreen


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    once = "--once" in sys.argv
    interval = float(args[0]) if args else 10.0

    print("Conectando ao teclado... (Ctrl+C para parar)")
    with TitorionScreen() as screen:
        while True:
            stats = collect_stats()
            screen.send_image(render(stats))
            print(f"[{datetime.now():%H:%M:%S}] enviado: {stats}")
            if once:
                break
            time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nEncerrado.")
