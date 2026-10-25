"""Escolhe a imagem da telinha conforme o app em foco."""

import time

from active_app import foreground_matches, programming_app
from claude_quota import fetch_claude_usage
from discord_status import discord_snapshot
from i18n import current, t
from lol_match import league_champion
from spotify_now import spotify_now
from stats_render import collect_stats, render, render_discord, render_league, render_spotify, render_usage
from usage_quota import fetch_period_usage, load_screen_config


def _discord_frame(snap: dict, lang: str) -> tuple:
    img = render_discord(snap)
    online = t("discord_on") if snap["online"] else t("discord_off")
    call = t("discord_call") if snap["in_call"] else t("discord_idle")
    if not snap["in_call"] or snap["mic_open"] is None:
        mic = t("discord_mic_idle")
        mic_mode = "na"
    elif snap["mic_open"]:
        mic = t("discord_mic_open")
        mic_mode = "open"
    else:
        mic = t("discord_mic_muted")
        mic_mode = "muted"
    text = t("log_discord", online=online, call=call, mic=mic)
    call_mode = "call" if snap["in_call"] else "idle"
    net = "on" if snap["online"] else "off"
    return img, text, f"discord:{net}:{call_mode}:{mic_mode}:{lang}"


def _spotify_frame(track: dict, lang: str) -> tuple:
    img = render_spotify(track)
    if track.get("playing"):
        state = t("spotify_playing")
        mode_state = "play"
    elif track.get("title"):
        state = t("spotify_paused")
        mode_state = "pause"
    else:
        state = t("spotify_empty")
        mode_state = "empty"
    title = track.get("title") or state
    text = t("log_spotify", state=state, title=title)
    return img, text, f"spotify:{mode_state}:{lang}:{title}"


def _league_frame(match: dict, lang: str) -> tuple:
    img = render_league(match)
    name = match["champion"]
    text = t("log_league", name=name)
    return img, text, f"league:{lang}:{name}"


# Tempo de cada cartaz quando a chamada divide a tela com outra prioridade.
_TURN_SECONDS = 10.0


def _turn(frames: list[tuple]) -> tuple:
    slot = int(time.monotonic() // _TURN_SECONDS) % len(frames)
    return frames[slot]


def _league_now(cfg: dict, lang: str) -> tuple | None:
    """Campeão quando a partida está na frente. None fora do jogo ou sem resposta."""
    league_apps = cfg.get("leagueApps") or []
    if not league_apps or not foreground_matches(league_apps):
        return None
    match = league_champion(cfg.get("leagueLiveUrl") or "")
    if not match:
        return None
    return _league_frame(match, lang)


def _other_frame(cfg: dict, lang: str) -> tuple:
    """Cartaz de quem está na frente, do Spotify tocando, ou do relógio."""
    app = programming_app(cfg["programmingApps"])
    if app == "Claude":
        quota = fetch_claude_usage()
        img = render_usage(quota, app)
        if quota.get("ok"):
            text = t(
                "log_claude",
                week=f"{quota['week_pct']:.0f}",
                session=f"{quota['session_pct']:.0f}",
            )
        else:
            text = t("log_claude_miss")
        return img, text, f"limite:Claude:{lang}"
    if app:
        quota = fetch_period_usage()
        label = app
        img = render_usage(quota, label)
        if quota.get("ok"):
            text = t(
                "log_cursor",
                label=label,
                included=f"{quota['included_pct']:.0f}",
                api=f"{quota['api_pct']:.0f}",
                auto=f"{quota['auto_pct']:.0f}",
            )
        else:
            text = t("log_cursor_miss", label=label)
        return img, text, f"limite:{app}:{lang}"
    league = _league_now(cfg, lang)
    if league is not None:
        return league
    spotify_apps = cfg.get("spotifyApps") or []
    if spotify_apps:
        track = spotify_now(spotify_apps)
        # Tocando, o cartaz troca o relógio. Cursor e Claude ficam na frente.
        if track["playing"] or foreground_matches(spotify_apps):
            return _spotify_frame(track, lang)
    stats = collect_stats()
    img = render(stats)
    text = (
        f"cpu {stats['cpu']:.0f}% | ram {stats['ram']:.0f}% | {stats['time']}"
    )
    return img, text, f"stats:{lang}"


def build_frame() -> tuple:
    """Retorna (imagem, texto de log, modo). O idioma entra no modo para reenviar na hora.

    Fora da chamada, o cartaz do Discord só aparece com a janela dele na frente.
    Numa chamada, ele reveza com o cartaz que as outras regras escolheriam.
    """
    cfg = load_screen_config()
    lang = current()
    # Partida na frente fica no campeão. A chamada do Discord não cobre o jogo.
    league = _league_now(cfg, lang)
    if league is not None:
        return league
    discord_apps = cfg.get("discordApps") or []
    discord_frame = None
    in_call = False
    if discord_apps:
        snap = discord_snapshot(discord_apps)
        focused = bool(snap["open"] and foreground_matches(discord_apps))
        in_call = bool(snap["open"] and snap["in_call"])
        if focused or in_call:
            discord_frame = _discord_frame(snap, lang)
        if focused and not in_call:
            return discord_frame
    other = _other_frame(cfg, lang)
    if in_call and discord_frame is not None:
        return _turn([discord_frame, other])
    return other
