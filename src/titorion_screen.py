"""
titorion_screen.py — Biblioteca do protocolo HID da tela do Titorion Saiph.

Implementação do protocolo da tela, documentada em docs/protocol.md.
Funciona em qualquer plataforma com hidapi.

Uso básico:

    from titorion_screen import TitorionScreen
    from PIL import Image

    screen = TitorionScreen()
    screen.connect()
    screen.send_image(Image.open("foto.png"))
    screen.close()
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

import hid

# ---- Identificação (docs/protocol.md §1) ----
VID = 0x379A
PID = 0x0920
USAGE_PAGE = 0xFF87   # 65415 decimal (valor usado no driver)
USAGE = 0x20          # 32
REPORT_ID = 6
REQ_LEN = 63          # payload por relatório (sem report ID)
CHUNK_DATA = REQ_LEN - 7   # 56 bytes de dados por pacote

SCREEN_W = 128
SCREEN_H = 128

# ---- Comandos da tela (docs/protocol.md §3) ----
CMD_INFO = 0x40
CMD_DATA = 0x41
CMD_FINISH = 0x42

# Resposta com byte[6] == 0x0F: tela ocupada (x9t/a9t do driver).
# O driver reenvia o mesmo pacote, até 20 vezes, com 50 ms de intervalo.
SCREEN_STATUS_BUSY = 0x0F
BUSY_RETRIES = 20
BUSY_PAUSE_S = 0.05

# Paginas da tela no componente CUt do driver, fluxo do Saiph (2336 nao esta em `ar`):
# homepage = relogio padrao; picture = imagem enviada; gif = pagina de GIF.
SCREEN_SUB_HOME_PAGE = 0x0B      # payload: A5 5A 0B 00 00 CRC_HI CRC_LO
SCREEN_SUB_PICTURE_PAGE = 0x0D   # payload: A5 5A 0D 00 00 CRC_HI CRC_LO
SCREEN_SUB_DELETE_PICTURE = 0x0E # payload: A5 5A 0E 00 00 CRC_HI CRC_LO (apaga uma imagem)
SCREEN_SUB_GIF_PAGE = 0x0F       # payload: A5 5A 0F 00 00 CRC_HI CRC_LO
# Quantas imagens apagar num reset. O estado estável guarda duas; o extra
# cobre um envio cortado. 0x0E além disso não tem resposta documentada:
# o primeiro timeout encerra a limpeza.
_CLEAR_TRIES = 6


class ScreenBusyError(TimeoutError):
    """A tela respondeu 0x0F no byte 6: ainda não pode receber o pacote."""


def crc16_modbus(data: bytes | list[int]) -> tuple[int, int]:
    """CRC-16/MODBUS, retorna (high, low) — função Lr() do driver.

    Sanity check: crc16_modbus([0x10, 0x00, 0x01]) == (197, 177)
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return (crc >> 8) & 0xFF, crc & 0xFF


def build_report(cmd: int, param_lo: int, param_hi: int, data: bytes) -> bytes:
    """Monta um relatório de 63 bytes — função Ui() do driver.

    [cmd, paramLo, paramHi, len, chkLo, chkHi, 0x00, ...data, padding 0x00]
    Checksum = soma simples de todos os bytes (com chk=0 no cálculo).
    """
    pkt = bytearray(REQ_LEN)
    pkt[0] = cmd
    pkt[1] = param_lo
    pkt[2] = param_hi
    pkt[3] = len(data) & 0xFF
    pkt[7:7 + len(data)] = data[:CHUNK_DATA]
    chk = sum(pkt) & 0xFFFF
    pkt[4] = chk & 0xFF
    pkt[5] = (chk >> 8) & 0xFF
    return bytes(pkt)


def image_to_rgb565be(image, width: int = SCREEN_W, height: int = SCREEN_H) -> bytes:
    """Converte uma PIL.Image para RGB565 big-endian — função ut() do driver."""
    img = image.convert("RGB").resize((width, height))
    src = img.tobytes()
    out = bytearray(width * height * 2)
    j = 0
    for i in range(0, len(src), 3):
        px = ((src[i] >> 3) << 11) | ((src[i + 1] >> 2) << 5) | (src[i + 2] >> 3)
        out[j] = (px >> 8) & 0xFF   # byte alto primeiro (big-endian)
        out[j + 1] = px & 0xFF
        j += 2
    return bytes(out)


class TitorionScreen:
    """Conexão com a tela do teclado via a interface HID vendor-defined."""

    def __init__(self, timeout_s: float = 2.0, retries: int = 3):
        self.timeout_s = timeout_s
        self.retries = retries
        self._dev: Optional[hid.device] = None
        # Serializa uploads: dois uploads concorrentes intercalam pacotes e
        # deixam o controlador da tela travado ate o teclado ser reconectado.
        self._lock = threading.RLock()
        self._loading_ready = False
        self._seeded_now = False

    # ---- conexão ----

    @staticmethod
    def find_interface() -> Optional[bytes]:
        """Procura a interface vendor-defined (usagePage 0xFFC7 / usage 0x20)."""
        for info in hid.enumerate(VID, PID):
            if info.get("usage_page") == USAGE_PAGE and info.get("usage") == USAGE:
                return info["path"]
        return None

    def connect(self) -> None:
        path = self.find_interface()
        if path is None:
            raise RuntimeError(
                "Teclado Titorion não encontrado (VID 0x%04X / PID 0x%04X, "
                "usagePage 0x%04X). Está conectado por cabo? Outro programa "
                "está usando o teclado?" % (VID, PID, USAGE_PAGE)
            )
        self._dev = hid.device()
        self._dev.open_path(path)

    def close(self) -> None:
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    def __enter__(self) -> "TitorionScreen":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- camada de envio (equivalente a sendData/Tb do driver) ----

    def _send_and_wait(self, report: bytes) -> bytes:
        assert self._dev is not None, "chame connect() antes"
        self._dev.write(bytes([REPORT_ID]) + report)
        deadline = time.monotonic() + self.timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"timeout aguardando resposta de cmd 0x{report[0]:02X}"
                )
            resp = self._dev.read(REQ_LEN + 1, timeout_ms=int(remaining * 1000))
            if not resp:
                continue
            # hidapi prefixa o report ID; o driver espera o eco de cmd e paramLo
            payload = bytes(resp[1:]) if resp[0] == REPORT_ID else bytes(resp)
            if payload[0] == report[0] and payload[1] == report[1]:
                if len(payload) > 6 and payload[6] == SCREEN_STATUS_BUSY:
                    raise ScreenBusyError(
                        f"tela ocupada no cmd 0x{report[0]:02X}"
                    )
                return payload

    def _send_with_retry(self, report: bytes) -> bytes:
        timeouts = 0
        busy = 0
        while True:
            try:
                return self._send_and_wait(report)
            except ScreenBusyError:
                busy += 1
                if busy >= BUSY_RETRIES:
                    raise
                time.sleep(BUSY_PAUSE_S)
            except (TimeoutError, OSError):
                timeouts += 1
                if timeouts >= self.retries:
                    raise
                time.sleep(0.12)

    def _send_buffer(self, cmd: int, data: bytes) -> None:
        """Fragmenta em pacotes de 56 bytes com offset — funções h9t/g9t do driver."""
        num_chunks = max(1, -(-len(data) // CHUNK_DATA))
        for p in range(num_chunks):
            offset = p * CHUNK_DATA
            chunk = data[offset:offset + CHUNK_DATA]
            report = build_report(cmd, offset & 0xFF, (offset >> 8) & 0xFF, chunk)
            self._send_with_retry(report)

    # ---- API da tela (docs/protocol.md §4) ----

    def _send_screen_subcmd(self, subcmd: int) -> None:
        """Troca a pagina visivel da tela (payload A5 5A via cmd 0x40 + finish 0x42).

        Igual ao driver para dispositivos fora da lista `ar`: CRC16 de
        [subcmd, 0x00, 0x00], sem o byte extra de argumento.
        """
        crc = crc16_modbus([subcmd, 0x00, 0x00])
        payload = bytes([0xA5, 0x5A, subcmd, 0x00, 0x00, *crc])
        self._send_buffer(CMD_INFO, payload)
        self._send_with_retry(build_report(CMD_FINISH, 0, 0, b""))

    def switch_to_home_page(self) -> None:
        """Volta para a homepage do firmware (relogio / tela padrao)."""
        self._send_screen_subcmd(SCREEN_SUB_HOME_PAGE)

    def switch_to_picture_page(self) -> None:
        """Mostra a imagem enviada por upload_pixels (picture page)."""
        self._send_screen_subcmd(SCREEN_SUB_PICTURE_PAGE)

    def delete_picture(self) -> None:
        """Apaga uma imagem guardada. Botão "Delete the picture" do driver.

        Cada upload entra como imagem nova. Sem este comando a memória enche
        e a tela para de trocar o que está visível.
        """
        self._send_screen_subcmd(SCREEN_SUB_DELETE_PICTURE)

    def upload_pixels(self, pixel_bytes: bytes) -> None:
        """Envia um framebuffer RGB565 big-endian completo (32768 bytes).

        Atomico entre threads: a trava impede que dois uploads se intercalem
        (o que corrompe o frame e trava a tela ate reconectar o teclado).

        Não apaga a imagem anterior. Para trocar a imagem viva, use
        send_image(): sobe a nova, mostra ela, e só então apaga a anterior.
        """
        total = len(pixel_bytes)
        expected = SCREEN_W * SCREEN_H * 2
        if total != expected:
            raise ValueError(f"framebuffer deve ter {expected} bytes, veio {total}")

        with self._lock:
            # 1) handshake
            crc = crc16_modbus([0x10, 0x00, 0x01])
            self._send_buffer(
                CMD_INFO, bytes([0xA5, 0x5A, 0x10, 0x00, 0x01, *crc, 0x01]))
            time.sleep(0.3)

            # 2) header com tamanho total + CRC
            len_hi, len_lo = (total >> 8) & 0xFF, total & 0xFF
            crc = crc16_modbus([0x0C, len_hi, len_lo])
            self._send_buffer(
                CMD_DATA, bytes([0xA5, 0x5A, 0x0C, len_hi, len_lo, *crc]))

            # 3) dados
            self._send_buffer(CMD_DATA, pixel_bytes)

            # 4) finish
            self._send_with_retry(build_report(CMD_FINISH, 0, 0, b""))

    def send_image(self, image, replace: bool = True) -> None:
        """Sobe a imagem nova, mostra ela, e só então apaga a anterior.

        Apagar a imagem que está na tela, ou ficar sem nenhuma, faz o firmware
        cair no relógio. Por isso a ordem é: gravar a terceira, trocar para
        ela, apagar a que ficou para trás. Durante o envio a imagem atual
        continua visível.
        """
        with self._lock:
            self._ensure_loading_base()
            # Sem uma imagem viva já gravada, apagar deixaria a tela vazia.
            drop_previous = (
                replace
                and not self._seeded_now
                and _read_state().get("contentReady")
            )
            self._seeded_now = False
            self.upload_pixels(image_to_rgb565be(image))
            self.switch_to_picture_page()
            if drop_previous:
                self.delete_picture()
                self.switch_to_picture_page()
            _write_state({"loadingReady": True, "contentReady": True})

    def reset_gallery(self, image) -> None:
        """Esvazia as imagens guardadas e grava de novo a que deve aparecer.

        Só usa comando já conferido: picture page 0x0D e apagar uma 0x0E, depois
        o upload normal. O relógio roxo pode aparecer no meio. O timeout curto
        de antes desistia do apagamento e a imagem velha continuava na tela.
        """
        with self._lock:
            self._loading_ready = False
            self._seeded_now = False
            _write_state({})
            self.switch_to_picture_page()
            saved_timeout = self.timeout_s
            saved_retries = self.retries
            self.timeout_s = 2.0
            self.retries = 2
            try:
                for _ in range(_CLEAR_TRIES):
                    try:
                        self.delete_picture()
                    except (TimeoutError, OSError, ScreenBusyError):
                        break
            finally:
                self.timeout_s = saved_timeout
                self.retries = saved_retries
            self.upload_pixels(_loading_frame())
            self.upload_pixels(image_to_rgb565be(image))
            self.switch_to_picture_page()
            self._loading_ready = True
            _write_state({"loadingReady": True, "contentReady": True})

    def _ensure_loading_base(self) -> None:
        """Garante o poster como primeira imagem, sem esvaziar a tela.

        Não apaga nada aqui. Apagar a imagem em exibição (ou a última que
        resta) faz o firmware voltar para o relógio.
        """
        if self._loading_ready:
            return
        state = _read_state()
        if not state.get("loadingReady"):
            self.upload_pixels(_loading_frame())
            _write_state({"loadingReady": True, "contentReady": False})
            self._seeded_now = True
        elif not state.get("contentReady"):
            self._seeded_now = True
        self._loading_ready = True


def _state_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "screen_state.json"


def _read_state() -> dict:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def gallery_reset_pending() -> bool:
    return bool(_read_state().get("recover"))


def request_gallery_reset() -> None:
    data = _read_state()
    data["recover"] = True
    _write_state(data)


def _write_state(data: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _loading_frame() -> bytes:
    from stats_render import render_loading

    return image_to_rgb565be(render_loading())
