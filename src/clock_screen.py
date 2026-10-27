"""Tela do relógio Wi-Fi "Smart Weather Clock" (firmware de fábrica SD PRO, 240x240).

O firmware não tem comando para desenhar na tela. O que ele tem é o tema
"Photo", um slideshow de JPGs gravados na memória dele. O relógio fica só no
tema Photo com duas fotos nossas: a base (cartaz "carregando", fixa) e o
cartaz, sempre sobrescrito com o mesmo nome. Nada é apagado durante o uso.

Endpoints (os mesmos que a página do relógio usa):
- GET  /theme/list                     -> {"interval", "themes": [{id, name, enabled}]}
- GET  /theme/toggle?id=N&state=0|1
- GET  /photo/list                     -> {"files": [{name, size, enabled}], "total", "used", "interval"}
- POST /photo/upload                   multipart, campo "file"
- GET  /photo/toggle?name=X&state=0|1
- GET  /photo/delete?name=X
- GET  /photo/interval?val=S           (a página só oferece 5, 10, 15, 30, 60, 180, 300)

Regras do firmware conferidas no aparelho:
- Apagar qualquer foto religa todas as fotos. Apagar a que está no slideshow
  deixa a tela em "No File" até o próximo ciclo.
- Upload com um nome que já existe sobrescreve a foto e mantém as outras como estão.
- Foto nova só existe para /photo/toggle depois de um GET /photo/list (antes dá 404).
- Não deixa desligar a última foto ligada (403 "Keep at least one").
- Nome com espaço precisa ir como %20; "+" dá 404.

O estado original (temas, fotos ligadas, intervalo) fica em config/clock_state.json
até close() devolver tudo. Se o programa cair, o próximo connect() usa esse arquivo
em vez do estado já mexido.
"""

from __future__ import annotations

import io
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

CLOCK_W = 240
CLOCK_H = 240
PHOTO_THEME = 2          # id do tema "Photo" em /theme/list
PHOTO_INTERVAL_S = 5     # menor opção da página do relógio
LIVE_PREFIX = "ts_live_"  # fotos deste programa; o resto é do usuário
BASE_NAME = LIVE_PREFIX + "base.jpg"   # tela padrão, ligada durante a troca
CARD_NAME = LIVE_PREFIX + "card.jpg"   # o cartaz que aparece
JPEG_QUALITY = 90
_RETRIES = 5
_RETRY_PAUSE_S = 0.6


class ClockScreen:
    """Conexão com o relógio pela API HTTP do firmware de fábrica."""

    def __init__(self, host: str, timeout_s: float = 8.0):
        host = host.strip().rstrip("/")
        if not host.startswith("http"):
            host = "http://" + host
        self.base = host
        self.timeout_s = timeout_s
        self._lock = threading.RLock()
        self._live: str | None = None
        self._connected = False
        self._themes: list[dict] = []
        self._themed = False

    # ---- HTTP ----

    def _get(self, path: str, **params: object) -> bytes:
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        for attempt in range(_RETRIES):
            try:
                with urllib.request.urlopen(url, timeout=self.timeout_s) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                # 4xx é recusa do firmware, não falha de rede: repetir não adianta.
                raise RuntimeError(f"relógio recusou {path} {params}: {e}") from e
            except OSError as e:
                if attempt == _RETRIES - 1:
                    raise RuntimeError(f"relógio não respondeu em {path}: {e}") from e
                time.sleep(_RETRY_PAUSE_S)
        raise AssertionError("inalcançável")

    def _get_json(self, path: str) -> dict:
        return json.loads(self._get(path).decode("utf-8"))

    def _upload(self, name: str, data: bytes) -> None:
        boundary = "----ts" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            self.base + "/photo/upload", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s * 2) as resp:
            resp.read()
        # Sem ler a lista, /photo/toggle responde 404 para a foto nova.
        self._get("/photo/list")

    def _user_photos(self) -> list[str]:
        files = self._get_json("/photo/list").get("files") or []
        return [f["name"] for f in files if not f["name"].startswith(LIVE_PREFIX)]

    def _hide_user_photos(self) -> None:
        """Desliga as fotos do usuário. Só funciona com a nossa já ligada."""
        for name in self._user_photos():
            self._get("/photo/toggle", name=name, state=0)

    # ---- conexão ----

    def connect(self) -> None:
        """Guarda o estado original. A troca de tema espera o primeiro cartaz."""
        with self._lock:
            try:
                themes = self._get_json("/theme/list").get("themes") or []
                photos = self._get_json("/photo/list")
            except RuntimeError as e:
                raise RuntimeError(f"Relógio não respondeu em {self.base}: {e}") from e

            if not _read_state():
                _write_state({
                    "themes": {str(t["id"]): bool(t.get("enabled")) for t in themes},
                    "photos": {
                        f["name"]: f.get("enabled") is not False
                        for f in photos.get("files") or []
                        if not f["name"].startswith(LIVE_PREFIX)
                    },
                    "photoInterval": photos.get("interval") or 10,
                })

            # Sobras de versões antigas. A base e o cartaz são sobrescritos.
            for f in photos.get("files") or []:
                if f["name"].startswith(LIVE_PREFIX) and f["name"] not in (BASE_NAME, CARD_NAME):
                    self._get("/photo/delete", name=f["name"])
            self._upload(BASE_NAME, image_to_jpeg(_loading_image()))
            self._get("/photo/toggle", name=BASE_NAME, state=1)
            self._get("/photo/interval", val=PHOTO_INTERVAL_S)
            self._themes = themes
            self._themed = False
            self._live = CARD_NAME if CARD_NAME in {f["name"] for f in photos.get("files") or []} else None
            self._connected = True

    def _photo_theme_only(self) -> None:
        # Liga o Photo antes de desligar os outros: nunca fica sem tema.
        self._get("/theme/toggle", id=PHOTO_THEME, state=1)
        for t in self._themes:
            if t["id"] != PHOTO_THEME and t.get("enabled"):
                self._get("/theme/toggle", id=t["id"], state=0)
        self._themed = True

    def close(self) -> None:
        """Devolve temas, fotos e intervalo como estavam e apaga a foto viva."""
        with self._lock:
            if not self._connected:
                return
            self._connected = False
            saved = _read_state()
            if not saved:
                return
            themes = {int(k): v for k, v in (saved.get("themes") or {}).items()}
            # Liga os originais primeiro, depois desliga o Photo se não era dele.
            for tid, on in themes.items():
                if on and tid != PHOTO_THEME:
                    self._get("/theme/toggle", id=tid, state=1)
            if not themes.get(PHOTO_THEME, False) and any(themes.values()):
                self._get("/theme/toggle", id=PHOTO_THEME, state=0)
            # Apagar uma foto religa todas; depois desliga as que estavam desligadas.
            for f in self._get_json("/photo/list").get("files") or []:
                if f["name"].startswith(LIVE_PREFIX):
                    self._get("/photo/delete", name=f["name"])
            present = self._user_photos()
            for name, on in (saved.get("photos") or {}).items():
                if not on and name in present:
                    self._get("/photo/toggle", name=name, state=0)
            self._get("/photo/interval", val=saved.get("photoInterval") or 10)
            self._live = None
            _state_path().unlink(missing_ok=True)

    def __enter__(self) -> "ClockScreen":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- imagem ----

    def send_image(self, image, replace: bool = True) -> None:
        """Sobrescreve o cartaz com a base ligada, depois deixa só o cartaz.

        Mesma ideia do teclado: a base cobre o intervalo da gravação, então o
        slideshow nunca cai num arquivo pela metade ou num que sumiu.
        O cartaz novo aparece no próximo ciclo (até 5 s).
        """
        with self._lock:
            self._get("/photo/toggle", name=BASE_NAME, state=1)
            if self._live:
                self._get("/photo/toggle", name=CARD_NAME, state=0)
            self._upload(CARD_NAME, image_to_jpeg(image))
            self._get("/photo/toggle", name=CARD_NAME, state=1)
            self._live = CARD_NAME
            if not self._themed:
                self._hide_user_photos()
                self._photo_theme_only()
            self._get("/photo/toggle", name=BASE_NAME, state=0)

    def reset_gallery(self, image) -> None:
        """No relógio não há galeria para esvaziar: só troca a foto."""
        self.send_image(image)


def image_to_jpeg(image) -> bytes:
    """Amplia o cartaz 128x128 para 240x240 e codifica em JPG."""
    img = image.convert("RGB")
    if img.size != (CLOCK_W, CLOCK_H):
        img = img.resize((CLOCK_W, CLOCK_H), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def _loading_image():
    from stats_render import render_loading

    return render_loading()


def _state_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "clock_state.json"


def _read_state() -> dict:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(data: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
