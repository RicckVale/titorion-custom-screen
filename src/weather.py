"""Tempo atual para o cartaz que reveza com o relógio.

A cidade vem de config/screen.json (weatherCity). Vazia, a rede informa o
lugar. A previsão é a do Open-Meteo, sem token. O intervalo da troca é
weatherTurnSeconds, nunca abaixo de 10 s.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

_TTL_S = 600.0
_FAIL_TTL_S = 60.0
_CACHE: dict | None = None
_CACHE_AT = 0.0
_PLACE: dict | None = None

# Códigos WMO do Open-Meteo, agrupados no texto curto do cartaz.
_TONES = (
    ((0, 1), "clear"),
    ((2, 3), "cloud"),
    ((45, 48), "fog"),
    ((51, 57), "drizzle"),
    ((61, 67), "rain"),
    ((80, 82), "rain"),
    ((71, 77), "snow"),
    ((85, 86), "snow"),
    ((95, 99), "storm"),
)


def turn_seconds(raw: object) -> float:
    """Segundos de cada cartaz. Abaixo de 10 s vira 10, para não gastar a tela."""
    try:
        seconds = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        seconds = 10.0
    return max(10.0, seconds)


def weather_now(city: str, lang: str) -> dict | None:
    """Temperatura, tom e cidade. None se a previsão não responder."""
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if _CACHE is not None and now - _CACHE_AT < (_TTL_S if _CACHE.get("ok") else _FAIL_TTL_S):
        return _CACHE.get("report")
    report = _read(city, lang)
    if report is None and _CACHE and _CACHE.get("report"):
        _CACHE = {"ok": False, "report": _CACHE["report"]}
        _CACHE_AT = now
        return _CACHE["report"]
    _CACHE = {"ok": report is not None, "report": report}
    _CACHE_AT = now
    return report


def _read(city: str, lang: str) -> dict | None:
    place = _place(city, lang)
    if place is None:
        return None
    query = urllib.parse.urlencode({
        "latitude": f"{place['lat']:.4f}",
        "longitude": f"{place['lon']:.4f}",
        "current": "temperature_2m,weather_code",
        "timezone": "auto",
    })
    payload = _get(f"https://api.open-meteo.com/v1/forecast?{query}")
    current = payload.get("current") if isinstance(payload, dict) else None
    if not isinstance(current, dict):
        return None
    temp = current.get("temperature_2m")
    code = current.get("weather_code")
    if isinstance(code, float) and code.is_integer():
        code = int(code)
    if not isinstance(temp, (int, float)) or not isinstance(code, int):
        return None
    tone = _tone(code)
    return {
        "temp_c": int(round(temp)),
        "tone": tone,
        "code": code,
        "city": place["city"],
    }


def _tone(code: int) -> str:
    for bounds, name in _TONES:
        if bounds[0] <= code <= bounds[1]:
            return name
    return "cloud"


def _place(city: str, lang: str) -> dict | None:
    global _PLACE
    key = city.casefold().strip()
    if _PLACE is not None and _PLACE.get("key") == key:
        return _PLACE
    found = _geocode(key, lang) if key else _by_network()
    if found is None:
        return None
    found["key"] = key
    _PLACE = found
    return found


def _geocode(city: str, lang: str) -> dict | None:
    query = urllib.parse.urlencode({
        "name": city,
        "count": 1,
        "language": "en" if lang == "en" else "pt",
    })
    payload = _get(f"https://geocoding-api.open-meteo.com/v1/search?{query}")
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results:
        return None
    row = results[0]
    if not isinstance(row, dict):
        return None
    lat, lon = row.get("latitude"), row.get("longitude")
    name = str(row.get("name") or city).strip()
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not name:
        return None
    return {"lat": float(lat), "lon": float(lon), "city": name}


def _by_network() -> dict | None:
    payload = _get("https://ipwho.is/")
    if not isinstance(payload, dict) or not payload.get("success"):
        return None
    lat, lon = payload.get("latitude"), payload.get("longitude")
    name = str(payload.get("city") or "").strip()
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not name:
        return None
    return {"lat": float(lat), "lon": float(lon), "city": name}


def _get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError, ValueError, TimeoutError):
        return {}
    return data if isinstance(data, dict) else {}
