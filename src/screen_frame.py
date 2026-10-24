"""Escolhe a imagem da telinha conforme o app em foco."""

from active_app import foreground_matches, programming_app
from claude_quota import fetch_claude_usage
from discord_status import discord_snapshot
from i18n import current, t
from stats_render import collect_stats, render, render_discord, render_usage
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


def build_frame() -> tuple:
    """Retorna (imagem, texto de log, modo). O idioma entra no modo para reenviar na hora.

    Chamada de voz do Discord passa na frente do relógio e das outras telas.
    Fora da chamada, o cartaz do Discord só aparece com a janela dele na frente.
    """
    cfg = load_screen_config()
    lang = current()
    discord_apps = cfg.get("discordApps") or []
    if discord_apps:
        snap = discord_snapshot(discord_apps)
        if snap["open"] and (snap["in_call"] or foreground_matches(discord_apps)):
            return _discord_frame(snap, lang)
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
    stats = collect_stats()
    img = render(stats)
    text = (
        f"cpu {stats['cpu']:.0f}% | ram {stats['ram']:.0f}% | {stats['time']}"
    )
    return img, text, f"stats:{lang}"
