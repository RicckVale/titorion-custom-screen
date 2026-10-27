"""Idioma da telinha e da janela. A escolha fica em config/screen.json."""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "config" / "screen.json"
_LANG = "pt"

_TEXT = {
    "pt": {
        "week": "SEMANA",
        "session": "SESSAO",
        "no_quota": "SEM COTA",
        "loading": "CARREGANDO",
        "auto": "AUTO",
        "api": "API",
        "included": "INCL",
        "cpu": "CPU",
        "ram": "RAM",
        "discord_name": "Discord",
        "discord_on": "ON",
        "discord_off": "OFF",
        "discord_call": "CONECTADO",
        "discord_idle": "LIVRE",
        "discord_mic_open": "MIC ABERTO",
        "discord_mic_muted": "MIC MUDO",
        "discord_mic_idle": "SEM MIC",
        "log_discord": "Discord {online} | {call} | {mic}",
        "spotify_name": "Spotify",
        "spotify_playing": "TOCANDO",
        "spotify_paused": "PAUSA",
        "spotify_empty": "SEM MUSICA",
        "log_spotify": "Spotify {state} | {title}",
        "weather_name": "TEMPO",
        "weather_clear": "LIMPO",
        "weather_cloud": "NUBLADO",
        "weather_fog": "NEVOEIRO",
        "weather_drizzle": "GAROA",
        "weather_rain": "CHUVA",
        "weather_snow": "NEVE",
        "weather_storm": "TEMPESTADE",
        "log_weather": "Tempo {temp}C | {condition}",
        "league_name": "CAMPEAO",
        "log_league": "Campeao {name}",
        "log_claude": "Claude semana {week}% | sessao {session}%",
        "log_claude_miss": "Claude sem leitura da cota",
        "antigravity_name": "ANTI",
        "antigravity_week": "SEM",
        "antigravity_5h": "5H",
        "usage_label": "USO",
        "log_antigravity": "Antigravity {detail}",
        "log_antigravity_miss": "Antigravity sem leitura da cota",
        "log_cursor": "{label} limite incluido {included}% | API {api}% | auto {auto}%",
        "log_cursor_miss": "{label} sem leitura da cota",
        "language": "IDIOMA",
        "preview_title": "PREVIEW = TELA DO TECLADO",
        "zoom": "🔍 Zoom: {n}x{suffix}",
        "zoom_real": " (real)",
        "connection": "CONEXÃO",
        "reconnect": "Reconectar",
        "monitor_title": "MONITOR DE STATS",
        "interval": "Intervalo (s):",
        "start_monitor": "▶ Iniciar monitor",
        "stop_monitor": "⏹ Parar monitor",
        "stopping": "⏹ Parando…",
        "still_title": "IMAGEM ESTÁTICA",
        "choose_image": "Escolher imagem…",
        "send_image": "Enviar imagem",
        "red_test": "Teste: tela vermelha",
        "reset_screen": "Esvaziar tela",
        "resetting": "Esvaziando as imagens guardadas. O relógio pode aparecer.",
        "reset_done": "Tela esvaziada. O cartaz atual foi gravado de novo.",
        "reset_fail": "❌ não esvaziou a tela: {error}",
        "reset_busy": "Ainda tem um envio em andamento. Espere e tente de novo.",
        "log_title": "LOG",
        "disconnected": "desconectado",
        "connected": "conectado",
        "not_found": "não encontrado",
        "reconnect_status": "erro — reconecte",
        "tray_hint": "Rodando na bandeja. A logo do projeto abre esta janela.",
        "keyboard_connected": "Teclado conectado (Saiph, tela 128x128).",
        "clock_connected": "Relógio conectado (Wi-Fi, tela 240x240).",
        "stopping_log": "Parando monitor...",
        "connect_first": "❌ Conecte o teclado primeiro.",
        "following": "▶ Acompanhando o app em foco.",
        "monitor_stopped": "⏹ Monitor parado.",
        "monitor_error": "❌ erro no monitor: {error}",
        "image_loaded": "Imagem carregada: {name}",
        "image_open_fail": "❌ não abriu a imagem: {error}",
        "sent_ok": "✅ {what} enviada para a tela!",
        "send_fail": "❌ falha ao enviar: {error}",
        "stopped_for_image": "⏹ Monitor parado para enviar a imagem.",
        "sending": "Enviando {what}...",
        "still_word": "imagem",
        "red_screen": "tela vermelha",
        "dialog_title": "Escolha uma imagem",
        "dialog_images": "Imagens",
        "dialog_all": "Todos",
        "tray_open": "Abrir",
        "tray_reset": "Esvaziar tela",
        "tray_quit": "Sair",
        "language_set": "Idioma da tela: português.",
        "sent_line": "enviado: {text}",
    },
    "en": {
        "week": "WEEK",
        "session": "SESSION",
        "no_quota": "NO QUOTA",
        "loading": "LOADING",
        "auto": "AUTO",
        "api": "API",
        "included": "INCL",
        "cpu": "CPU",
        "ram": "RAM",
        "discord_name": "Discord",
        "discord_on": "ON",
        "discord_off": "OFF",
        "discord_call": "IN CALL",
        "discord_idle": "IDLE",
        "discord_mic_open": "MIC OPEN",
        "discord_mic_muted": "MIC MUTED",
        "discord_mic_idle": "NO MIC",
        "log_discord": "Discord {online} | {call} | {mic}",
        "spotify_name": "Spotify",
        "spotify_playing": "PLAYING",
        "spotify_paused": "PAUSED",
        "spotify_empty": "NOTHING",
        "log_spotify": "Spotify {state} | {title}",
        "weather_name": "WEATHER",
        "weather_clear": "CLEAR",
        "weather_cloud": "CLOUDY",
        "weather_fog": "FOG",
        "weather_drizzle": "DRIZZLE",
        "weather_rain": "RAIN",
        "weather_snow": "SNOW",
        "weather_storm": "STORM",
        "log_weather": "Weather {temp}C | {condition}",
        "league_name": "CHAMPION",
        "log_league": "Champion {name}",
        "log_claude": "Claude week {week}% | session {session}%",
        "log_claude_miss": "Claude quota not read",
        "antigravity_name": "ANTI",
        "antigravity_week": "WK",
        "antigravity_5h": "5H",
        "usage_label": "USED",
        "log_antigravity": "Antigravity {detail}",
        "log_antigravity_miss": "Antigravity quota not read",
        "log_cursor": "{label} included {included}% | API {api}% | auto {auto}%",
        "log_cursor_miss": "{label} quota not read",
        "language": "LANGUAGE",
        "preview_title": "PREVIEW = KEYBOARD SCREEN",
        "zoom": "🔍 Zoom: {n}x{suffix}",
        "zoom_real": " (actual)",
        "connection": "CONNECTION",
        "reconnect": "Reconnect",
        "monitor_title": "STATS MONITOR",
        "interval": "Interval (s):",
        "start_monitor": "▶ Start monitor",
        "stop_monitor": "⏹ Stop monitor",
        "stopping": "⏹ Stopping…",
        "still_title": "STILL IMAGE",
        "choose_image": "Choose image…",
        "send_image": "Send image",
        "red_test": "Test: red screen",
        "reset_screen": "Clear screen",
        "resetting": "Clearing stored images. The clock may show up.",
        "reset_done": "Screen cleared. The current card was written again.",
        "reset_fail": "❌ could not clear the screen: {error}",
        "reset_busy": "A send is still running. Wait and try again.",
        "log_title": "LOG",
        "disconnected": "disconnected",
        "connected": "connected",
        "not_found": "not found",
        "reconnect_status": "error — reconnect",
        "tray_hint": "Running in the tray. The project logo opens this window.",
        "keyboard_connected": "Keyboard connected (Saiph, 128x128 screen).",
        "clock_connected": "Clock connected (Wi-Fi, 240x240 screen).",
        "stopping_log": "Stopping monitor...",
        "connect_first": "❌ Connect the keyboard first.",
        "following": "▶ Following the front window.",
        "monitor_stopped": "⏹ Monitor stopped.",
        "monitor_error": "❌ monitor error: {error}",
        "image_loaded": "Image loaded: {name}",
        "image_open_fail": "❌ could not open the image: {error}",
        "sent_ok": "✅ {what} sent to the screen!",
        "send_fail": "❌ send failed: {error}",
        "stopped_for_image": "⏹ Monitor stopped to send the image.",
        "sending": "Sending {what}...",
        "still_word": "image",
        "red_screen": "red screen",
        "dialog_title": "Choose an image",
        "dialog_images": "Images",
        "dialog_all": "All",
        "tray_open": "Open",
        "tray_reset": "Clear screen",
        "tray_quit": "Quit",
        "language_set": "Screen language: English.",
        "sent_line": "sent: {text}",
    },
}


def _normalize(code: str | None) -> str:
    code = (code or "").strip().lower()
    return code if code in _TEXT else "pt"


def current() -> str:
    return _LANG


def t(key: str, **values: object) -> str:
    table = _TEXT[_LANG]
    text = table.get(key) or _TEXT["pt"].get(key) or key
    return text.format(**values) if values else text


def load() -> str:
    """Lê o idioma gravado. Sem a chave, permanece português."""
    global _LANG
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _LANG = "pt"
        return _LANG
    _LANG = _normalize(str(data.get("language") or "pt"))
    return _LANG


def set_language(code: str) -> str:
    """Grava pt ou en em config/screen.json e passa a valer na hora."""
    global _LANG
    _LANG = _normalize(code)
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    data["language"] = _LANG
    _PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return _LANG


load()
