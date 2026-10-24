"""
Marca do projeto: o nome TITORION CUSTOM SCREEN em pixel 8-bit.

A faixa larga abre o README. O quadrado e o monograma TC vão na bandeja,
onde o nome inteiro não cabe.
"""

from pathlib import Path

from PIL import Image, ImageDraw

INK = (17, 17, 17)
PAPER = (255, 246, 220)
YELLOW = (255, 214, 10)

# Fonte 5×7. Cada string é uma linha; 1 é tinta.
_FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10001", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    " ": ("000", "000", "000", "000", "000", "000", "000"),
}

_ROWS = 7
_TRACK = 2
_ROOT = Path(__file__).resolve().parents[1]


def _width(text: str) -> int:
    return sum(len(_FONT[ch][0]) for ch in text) + _TRACK * (len(text) - 1)


def _block(lines: list[str], line_gap: int) -> tuple[int, int]:
    width = max(_width(line) for line in lines)
    height = _ROWS * len(lines) + line_gap * (len(lines) - 1)
    return width, height


def _stamp(draw: ImageDraw.ImageDraw, lines: list[str], origin: tuple[int, int],
           scale: int, line_gap: int, color: tuple[int, int, int]) -> None:
    block_w, _ = _block(lines, line_gap)
    y = origin[1]
    for line in lines:
        x = origin[0] + (block_w - _width(line)) * scale // 2
        for ch in line:
            glyph = _FONT[ch]
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit != "1":
                        continue
                    x0 = x + col * scale
                    y0 = y + row * scale
                    draw.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), fill=color)
            x += (len(glyph[0]) + _TRACK) * scale
        y += (_ROWS + line_gap) * scale


def _plate(size: int, lines: list[str], line_gap: int) -> Image.Image:
    """Cartaz quadrado. A escala inteira cabe no tamanho pedido."""
    border = max(1, size // 32)
    cols, rows = _block(lines, line_gap)
    margin = max(border + 1, size // 10)
    room = size - margin * 2 - border * 2
    scale = max(1, min(room // cols, room // (rows + 1)))
    img = Image.new("RGB", (size, size), PAPER)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, size - 1, size - 1), outline=INK, width=border)
    text_w = cols * scale
    text_h = rows * scale
    inner = size - border * 2
    x = border + (inner - text_w - scale) // 2
    y = border + (inner - text_h - scale) // 2
    _stamp(draw, lines, (x + scale, y + scale), scale, line_gap, YELLOW)
    _stamp(draw, lines, (x, y), scale, line_gap, INK)
    return img


def banner() -> Image.Image:
    """Faixa com o nome inteiro, para o topo do README."""
    lines = ["TITORION", "CUSTOM SCREEN"]
    line_gap = 3
    scale = 10
    border = 8
    pad = 56
    cols, rows = _block(lines, line_gap)
    width = cols * scale + scale + pad * 2 + border * 2
    height = rows * scale + scale + pad * 2 + border * 2
    img = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, width - 1, height - 1), outline=INK, width=border)
    text_w = cols * scale
    text_h = rows * scale
    inner_w = width - border * 2
    inner_h = height - border * 2
    x = border + (inner_w - text_w - scale) // 2
    y = border + (inner_h - text_h - scale) // 2
    _stamp(draw, lines, (x + scale, y + scale), scale, line_gap, YELLOW)
    _stamp(draw, lines, (x, y), scale, line_gap, INK)
    return img


def icon(size: int = 64) -> Image.Image:
    """Ícone da bandeja. O nome inteiro entra a partir de 96 px; abaixo, TC."""
    if size >= 96:
        return _plate(size, ["TITORION", "CUSTOM", "SCREEN"], line_gap=2)
    return _plate(size, ["TC"], line_gap=1)


def write_assets() -> None:
    folder = _ROOT / "assets"
    folder.mkdir(parents=True, exist_ok=True)
    banner().save(folder / "titorion-custom-screen.png")
    icon(512).save(folder / "logo.png")


if __name__ == "__main__":
    write_assets()
