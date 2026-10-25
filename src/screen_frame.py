"""Escolhe a imagem da telinha conforme o app em foco."""

import time

from active_app import foreground_matches, matching_pid, programming_app
from claude_quota import fetch_claude_usage
from discord_status import discord_snapshot
from i18n import current, t
from lol_match import league_champion
from spotify_now import spotify_now
from stats_render import (
    collect_stats, render, render_discord, render_league, render_spotify, render_usage,
    render_weather,
)
from usage_quota import fetch_period_usage, load_screen_config
from weather import turn_seconds, weather_now


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
    art = "art" if track.get("cover") else "plain"
    return img, text, f"spotify:{mode_state}:{art}:{lang}:{title}"


def _league_frame(match: dict, lang: str) -> tuple:
    img = render_league(match)
    name = match["champion"]
    text = t("log_league", name=name)
    return img, text, f"league:{lang}:{name}:{match.get('level')}"


# Tempo de cada cartaz quando a chamada divide a tela com outra prioridade.
_TURN_SECONDS = 10.0


def _turn(frames: list[tuple], seconds: float = _TURN_SECONDS) -> tuple:
    pace = max(_TURN_SECONDS, float(seconds))
    slot = int(time.monotonic() // pace) % len(frames)
    return frames[slot]


def _weather_frame(cfg: dict, lang: str) -> tuple | None:
    report = weather_now(cfg.get("weatherCity") or "", lang)
    if not report:
        return None
    condition = t(f"weather_{report['tone']}")
    shown = {**report, "condition": condition}
    img = render_weather(shown)
    text = t("log_weather", temp=report["temp_c"], condition=condition)
    return img, text, f"weather:{lang}:{report['tone']}:{report['temp_c']}"


def _pace(cfg: dict) -> float:
    return turn_seconds(cfg.get("weatherTurnSeconds"))


def _idle_frames(cfg: dict, lang: str) -> list[tuple]:
    stats = collect_stats()
    img = render(stats)
    text = f"cpu {stats['cpu']:.0f}% | ram {stats['ram']:.0f}% | {stats['time']}"
    frames = [(img, text, f"stats:{lang}")]
    weather = _weather_frame(cfg, lang)
    if weather is not None:
        frames.append(weather)
    return frames


def _league_now(cfg: dict, lang: str) -> tuple | None:
    """Campeão da partida aberta. None fora do jogo ou sem resposta.

    Vale com o processo do jogo rodando, não só quando a janela está na frente.
    O cliente fechado não entra: o executável da partida é outro.
    """
    league_apps = cfg.get("leagueApps") or []
    if not league_apps:
        return None
    game_pid = matching_pid(league_apps)
    if game_pid is None:
        return None
    match = league_champion(cfg.get("leagueLiveUrl") or "", game_pid)
    if not match:
        return None
    return _league_frame(match, lang)


def _quota_frame(cfg: dict, lang: str, app: str) -> tuple:
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
    quota = fetch_period_usage()
    img = render_usage(quota, app)
    if quota.get("ok"):
        text = t(
            "log_cursor",
            label=app,
            included=f"{quota['included_pct']:.0f}",
            api=f"{quota['api_pct']:.0f}",
            auto=f"{quota['auto_pct']:.0f}",
        )
    else:
        text = t("log_cursor_miss", label=app)
    return img, text, f"limite:{app}:{lang}"


def _with_playing(frames: list[tuple], cfg: dict, lang: str, track: dict) -> tuple:
    """Com faixa tocando, o cartaz do Spotify entra na mesma troca."""
    if track.get("playing"):
        frames = [*frames, _spotify_frame(track, lang)]
    if len(frames) == 1:
        return frames[0]
    return _turn(frames, _pace(cfg))


def build_frame() -> tuple:
    """Retorna (imagem, texto de log, modo). O idioma entra no modo para reenviar na hora.

    Fora da chamada, o cartaz do Discord só aparece com a janela dele na frente.
    Numa chamada, ele reveza com o relógio e o tempo.
    Com uma faixa tocando, o Spotify entra nessa mesma troca.
    A partida aberta fica no campeão.
    """
    cfg = load_screen_config()
    lang = current()
    spotify_apps = cfg.get("spotifyApps") or []
    track = spotify_now(spotify_apps) if spotify_apps else {
        "playing": False,
        "paused": False,
        "title": "",
        "artist": "",
    }
    spotify_focused = bool(spotify_apps and foreground_matches(spotify_apps))
    app = programming_app(cfg["programmingApps"])
    if app:
        return _with_playing([_quota_frame(cfg, lang, app)], cfg, lang, track)
    league = _league_now(cfg, lang)
    if league is not None:
        return league
    if spotify_focused:
        return _spotify_frame(track, lang)
    discord_apps = cfg.get("discordApps") or []
    discord_frame = None
    focused = False
    in_call = False
    if discord_apps:
        snap = discord_snapshot(discord_apps)
        focused = bool(snap["open"] and foreground_matches(discord_apps))
        in_call = bool(snap["open"] and snap["in_call"])
        if focused or in_call:
            discord_frame = _discord_frame(snap, lang)
    idle = _idle_frames(cfg, lang)
    if discord_frame is not None and focused and not in_call:
        frames = [discord_frame]
    elif discord_frame is not None and in_call:
        frames = [discord_frame, *idle]
    else:
        frames = idle
    return _with_playing(frames, cfg, lang, track)
