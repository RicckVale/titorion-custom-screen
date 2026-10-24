"""
demo_static.py — Envia uma imagem fixa para a tela do Titorion Saiph.

Uso:
    python src/demo_static.py imagem.png
    python src/demo_static.py --red        # teste rápido: tela toda vermelha
"""

import sys

from PIL import Image

from titorion_screen import TitorionScreen


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--red":
        img = Image.new("RGB", (128, 128), (255, 0, 0))
    else:
        img = Image.open(sys.argv[1])

    print("Conectando ao teclado...")
    with TitorionScreen() as screen:
        print("Enviando imagem (586 pacotes, ~alguns segundos)...")
        screen.send_image(img)
    print("Pronto! Confira a tela do teclado.")


if __name__ == "__main__":
    main()
