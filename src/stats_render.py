"""
stats_render.py — Coleta de stats do PC e renderizacao da imagem 128x128.

Compartilhado entre demo_stats.py (CLI) e app.py (interface grafica).
Layout otimizado para a telinha fisica: textos grandes e alto contraste.
Para adicionar novas fontes de dados (cota de API, GitHub, Spotify...),
estenda collect_stats() e o layout em render().
"""

import re
from datetime import datetime
from functools import lru_cache

import psutil
from PIL import Image, ImageDraw, ImageFont

from i18n import t
from titorion_screen import SCREEN_W, SCREEN_H

# Neo-brutalismo: bloco chapado, borda preta, sombra dura.
INK = (17, 17, 17)
PAPER = (255, 246, 220)
YELLOW = (255, 214, 10)
GREEN = (130, 230, 70)
RED = (255, 64, 64)
CYAN = (110, 226, 255)
WHITE = (255, 255, 255)
# Laranja amostrado do ícone do app do Claude.
CLAUDE = (219, 112, 76)
# Blurple do cabeçalho do Discord, para o cartaz ser reconhecível.
BLURPLE = (88, 101, 242)
# Verde do Spotify, brilhante o bastante para texto preto.
SPOTIFY = (29, 185, 84)
# Azul do cartaz das magias. Texto branco em cima.
LEAGUE = (47, 80, 180)


@lru_cache(maxsize=8)
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Tenta uma TTF do Windows; cai para a fonte bitmap padrao se nao achar."""
    names = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ]
    for path in names:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def collect_stats() -> dict:
    """Adicione aqui suas fontes: cota de API/nuvem, GitHub, Spotify, etc."""
    return {
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "time": datetime.now().strftime("%H:%M"),
    }


@lru_cache(maxsize=8)
def _display(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Fonte pesada. Impact lê como cartaz; Arial Black/Segoe se não houver."""
    for path in (
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/ariblk.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return _font(size, bold=True)


def _level_color(pct: float) -> tuple:
    """Até 50% verde, até 75% amarelo, daí vermelho."""
    if pct >= 75:
        return RED
    if pct >= 50:
        return YELLOW
    return GREEN


def _block(d: ImageDraw.ImageDraw, box: tuple, fill: tuple, shadow: int = 3) -> None:
    x0, y0, x1, y1 = box
    d.rectangle([x0 + shadow, y0 + shadow, x1 + shadow, y1 + shadow], fill=INK)
    d.rectangle([x0, y0, x1, y1], fill=fill, outline=INK, width=2)


def render_loading() -> Image.Image:
    """Poster fixo. Fica gravado como primeira imagem e aparece no intervalo."""
    image = Image.new("RGB", (SCREEN_W, SCREEN_H), PAPER)
    draw = ImageDraw.Draw(image)
    _block(draw, (8, 22, 112, 106), YELLOW, shadow=4)
    label = t("loading")
    size = 22
    while size > 12 and draw.textlength(label, font=_display(size)) > 90:
        size -= 1
    draw.text((60, 52), label, font=_display(size), fill=INK, anchor="mm")
    for index, fill in enumerate((INK, INK, PAPER)):
        x = 26 + index * 26
        draw.rectangle((x, 74, x + 18, 90), fill=fill, outline=INK, width=2)
    return image


def render(stats: dict) -> Image.Image:
    """Relógio + CPU/RAM no mesmo cartaz das outras telas."""
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), PAPER)
    d = ImageDraw.Draw(img)

    _block(d, (5, 5, 116, 68), YELLOW)
    d.text((60, 36), stats["time"], font=_display(34), fill=INK, anchor="mm")

    cpu = float(stats["cpu"])
    ram = float(stats["ram"])
    _block(d, (5, 76, 58, 120), _level_color(cpu), shadow=2)
    _block(d, (66, 76, 119, 120), _level_color(ram), shadow=2)
    d.text((31, 88), t("cpu"), font=_display(11), fill=INK, anchor="mm")
    d.text((31, 106), f"{cpu:.0f}%", font=_display(18), fill=INK, anchor="mm")
    d.text((92, 88), t("ram"), font=_display(11), fill=INK, anchor="mm")
    d.text((92, 106), f"{ram:.0f}%", font=_display(18), fill=INK, anchor="mm")
    return img


@lru_cache(maxsize=4)
def _cursor_mark(size: int) -> Image.Image:
    """Marca do Cursor (o ponteiro de duas faces do cursor_mini.svg), em branco."""
    canvas = size * 8
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def pt(x: float, y: float) -> tuple[float, float]:
        return (x / 28 * canvas, y / 28 * canvas)

    tip = pt(21.88, 4.47)
    notch = pt(14.79, 16.75)
    draw.polygon([pt(5.23, 15.47), tip, notch], fill=(255, 255, 255, 255))
    draw.polygon([tip, notch, pt(20.69, 24.39)], fill=(255, 255, 255, 150))
    return img.resize((size, size), Image.Resampling.LANCZOS)


# Marca do Claude (simple-icons, CC0), viewBox 24. Só retas.
_CLAUDE_PATH = (
    "m4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486"
    "-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522"
    ".4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886"
    "l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714"
    "-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686"
    " 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733"
    "-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674"
    "-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282"
    " 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947"
    ".2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433"
    "-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053"
    " 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657"
    "-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183"
    " 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857"
    "-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621"
    "l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107"
    "-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768"
    "-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496"
    " 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246"
    "L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793"
    "-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314"
    "-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164"
    "-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062"
    "-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429"
    " 1.9064-1.3114Z"
)


def _claude_points() -> list[tuple[float, float]]:
    tokens = re.findall(r"[MmLlHhVvZz]|-?\d*\.?\d+(?:e[-+]?\d+)?", _CLAUDE_PATH)
    points: list[tuple[float, float]] = []
    index = 0
    x = y = 0.0
    start = (0.0, 0.0)
    command = ""
    while index < len(tokens):
        token = tokens[index]
        if token in "MmLlHhVvZz":
            command = token
            index += 1
            if command in "Zz":
                points.append(start)
            continue
        if command in "Mm":
            dx, dy = float(token), float(tokens[index + 1])
            if command == "m":
                x += dx
                y += dy
            else:
                x, y = dx, dy
            start = (x, y)
            points.append(start)
            command = "l" if command == "m" else "L"
            index += 2
        elif command in "Ll":
            dx, dy = float(token), float(tokens[index + 1])
            if command == "l":
                x += dx
                y += dy
            else:
                x, y = dx, dy
            points.append((x, y))
            index += 2
        elif command in "Hh":
            dx = float(token)
            x = x + dx if command == "h" else dx
            points.append((x, y))
            index += 1
        elif command in "Vv":
            dy = float(token)
            y = y + dy if command == "v" else dy
            points.append((x, y))
            index += 1
        else:
            break
    return points


@lru_cache(maxsize=4)
def _claude_mark(size: int) -> Image.Image:
    """Estrela do Claude, em branco, para sentar no bloco laranja."""
    canvas = size * 8
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    points = [
        (px / 24 * canvas, py / 24 * canvas)
        for px, py in _claude_points()
    ]
    draw.polygon(points, fill=(255, 255, 255, 255))
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _render_claude(quota: dict, app_name: str) -> Image.Image:
    """Semana em destaque, sessao embaixo. O adesivo e o tempo ate zerar a semana."""
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), PAPER)
    draw = ImageDraw.Draw(img)
    _block(draw, (4, 4, 84, 26), CLAUDE, shadow=2)
    mark = _claude_mark(14)
    img.paste(mark, (8, 8), mark)
    draw.text((26, 15), app_name[:8], font=_display(13), fill=INK, anchor="lm")
    if not quota.get("ok"):
        _block(draw, (4, 34, 120, 120), RED)
        draw.text((62, 78), t("no_quota"), font=_display(18), fill=INK, anchor="mm")
        return img

    week = float(quota["week_pct"])
    session = float(quota["session_pct"])
    _block(draw, (90, 4, 122, 26), PAPER, shadow=2)
    draw.text((106, 15), str(quota.get("reset_label") or "--"), font=_display(13), fill=INK, anchor="mm")
    _block(draw, (4, 34, 120, 82), _level_color(week))
    draw.text((10, 38), t("week"), font=_display(12), fill=INK, anchor="lt")
    draw.text((62, 62), f"{week:.0f}%", font=_display(30), fill=INK, anchor="mm")
    _block(draw, (4, 90, 120, 121), _level_color(session), shadow=2)
    draw.text((16, 105), t("session"), font=_display(12), fill=INK, anchor="lm")
    draw.text((104, 105), f"{session:.0f}%", font=_display(16), fill=INK, anchor="rm")
    return img


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_size: int, max_width: int) -> int:
    size = max_size
    while size > 11 and draw.textlength(text, font=_display(size)) > max_width:
        size -= 1
    return size


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, size: int,
                max_width: int, max_lines: int) -> list[str]:
    words = [part for part in text.split() if part]
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=_display(size)) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    used = " ".join(lines)
    if used != " ".join(words) and lines:
        last = lines[-1]
        while last and draw.textlength(last + "..", font=_display(size)) > max_width:
            last = last[:-1]
        lines[-1] = (last + "..") if last else ".."
    return lines


def render_spotify(track: dict) -> Image.Image:
    """Nome da faixa em destaque, artista embaixo, estado no topo do cartaz."""
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), PAPER)
    draw = ImageDraw.Draw(img)
    playing = bool(track.get("playing"))
    title = (track.get("title") or "").strip()
    artist = (track.get("artist") or "").strip()
    has_track = bool(title)

    _block(draw, (4, 4, 120, 26), SPOTIFY, shadow=2)
    draw.text((62, 15), t("spotify_name"), font=_display(14), fill=INK, anchor="mm")

    if not has_track:
        _block(draw, (4, 34, 120, 120), YELLOW)
        label = t("spotify_empty")
        draw.text(
            (62, 78), label,
            font=_display(_fit_text(draw, label, 18, 100)),
            fill=INK, anchor="mm",
        )
        return img

    _block(draw, (4, 34, 120, 96), GREEN if playing else YELLOW)
    state = t("spotify_playing") if playing else t("spotify_paused")
    draw.text((62, 40), state, font=_display(11), fill=INK, anchor="mt")
    lines = _wrap_lines(draw, title, 16, 104, 2)
    if not lines:
        lines = _wrap_lines(draw, title, 12, 104, 2)
    top = 58 if len(lines) > 1 else 66
    for index, line in enumerate(lines):
        draw.text((62, top + index * 18), line, font=_display(16), fill=INK, anchor="mt")

    _block(draw, (4, 102, 120, 121), PAPER, shadow=2)
    who = artist or state
    draw.text(
        (62, 111), who,
        font=_display(_fit_text(draw, who, 13, 104)),
        fill=INK, anchor="mm",
    )
    return img


def render_league(match: dict) -> Image.Image:
    """Nome do campeão em destaque. O nível fica no adesivo quando a partida manda."""
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), PAPER)
    draw = ImageDraw.Draw(img)
    name = (match.get("champion") or "").strip()
    level = match.get("level")
    if isinstance(level, int):
        _block(draw, (4, 4, 84, 26), LEAGUE, shadow=2)
        draw.text((44, 15), t("league_name"), font=_display(13), fill=WHITE, anchor="mm")
        _block(draw, (90, 4, 122, 26), YELLOW, shadow=2)
        draw.text((106, 15), str(level), font=_display(14), fill=INK, anchor="mm")
    else:
        _block(draw, (4, 4, 120, 26), LEAGUE, shadow=2)
        draw.text((62, 15), t("league_name"), font=_display(14), fill=WHITE, anchor="mm")
    _block(draw, (4, 34, 120, 120), YELLOW)
    lines = _wrap_lines(draw, name, 22, 104, 3)
    if not lines:
        lines = [name]
    top = 78 - (len(lines) - 1) * 14
    for index, line in enumerate(lines):
        draw.text((62, top + index * 28), line, font=_display(22), fill=INK, anchor="mm")
    return img


def render_discord(state: dict) -> Image.Image:
    """Online no adesivo, conversa em destaque, microfone embaixo."""
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), PAPER)
    draw = ImageDraw.Draw(img)
    online = bool(state.get("online"))
    in_call = bool(state.get("in_call"))
    mic = state.get("mic_open")

    _block(draw, (4, 4, 84, 26), BLURPLE, shadow=2)
    draw.text((10, 15), t("discord_name"), font=_display(13), fill=WHITE, anchor="lm")
    _block(draw, (90, 4, 122, 26), GREEN if online else RED, shadow=2)
    mark = t("discord_on") if online else t("discord_off")
    draw.text((106, 15), mark, font=_display(13), fill=INK, anchor="mm")

    _block(draw, (4, 34, 120, 82), GREEN if in_call else YELLOW)
    hero = t("discord_call") if in_call else t("discord_idle")
    draw.text((62, 58), hero, font=_display(_fit_text(draw, hero, 20, 100)), fill=INK, anchor="mm")

    if not in_call or mic is None:
        fill, label = PAPER, t("discord_mic_idle")
    elif mic:
        fill, label = GREEN, t("discord_mic_open")
    else:
        fill, label = RED, t("discord_mic_muted")
    _block(draw, (4, 90, 120, 121), fill, shadow=2)
    draw.text(
        (62, 105), label,
        font=_display(_fit_text(draw, label, 16, 100)),
        fill=INK, anchor="mm",
    )
    return img


def render_usage(quota: dict, app_name: str) -> Image.Image:
    """Auto em destaque, API em segundo, incluído só no canto.

    O percentual do plano incluído não é o número principal: Auto e API são.
    No Claude, a semana (todos os modelos) e a sessao ocupam esses lugares.
    """
    if quota.get("source") == "claude":
        return _render_claude(quota, app_name)
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), PAPER)
    d = ImageDraw.Draw(img)
    is_cursor = app_name.strip().lower() == "cursor"
    title = "Cursor" if is_cursor else app_name[:8]

    _block(d, (4, 4, 84, 26), INK, shadow=2)
    if is_cursor:
        mark = _cursor_mark(14)
        img.paste(mark, (8, 8), mark)
        d.text((26, 15), title, font=_display(13), fill=WHITE, anchor="lm")
    else:
        d.text((10, 15), title, font=_display(13), fill=WHITE, anchor="lm")

    if not quota.get("ok"):
        _block(d, (4, 34, 120, 120), RED)
        d.text((62, 78), t("no_quota"), font=_display(18), fill=INK, anchor="mm")
        return img

    _block(d, (90, 4, 122, 26), CYAN, shadow=2)
    d.text((106, 15), f"{int(quota['days_left'])}d", font=_display(13), fill=INK, anchor="mm")

    auto = float(quota["auto_pct"])
    api = float(quota["api_pct"])
    included = float(quota["included_pct"])

    _block(d, (4, 34, 120, 82), _level_color(auto))
    d.text((10, 38), t("auto"), font=_display(12), fill=INK, anchor="lt")
    d.text((62, 62), f"{auto:.0f}%", font=_display(30), fill=INK, anchor="mm")

    _block(d, (4, 90, 78, 121), _level_color(api), shadow=2)
    d.text((41, 100), t("api"), font=_display(10), fill=INK, anchor="mm")
    d.text((41, 112), f"{api:.0f}%", font=_display(16), fill=INK, anchor="mm")

    _block(d, (86, 96, 122, 121), _level_color(included), shadow=2)
    d.text((104, 104), t("included"), font=_display(8), fill=INK, anchor="mm")
    d.text((104, 114), f"{included:.0f}", font=_display(12), fill=INK, anchor="mm")
    return img
