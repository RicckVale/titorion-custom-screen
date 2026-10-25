"""
app.py — Titorion Screen Studio.

O programa fica na bandeja do Windows. A janela só abre se o ícone for
clicado. O monitor do teclado continua rodando com a janela fechada.

Execute: pythonw src/app.py   (ou duplo clique em "Screen Studio.bat")
"""

import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

# Usa pixels reais em vez da escala de DPI do Windows (janela menor e nitida)
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import pystray
from PIL import Image, ImageTk

from brand_mark import icon as app_mark
from i18n import current, set_language, t
from screen_frame import build_frame
from titorion_screen import (
    TitorionScreen, SCREEN_W, SCREEN_H, gallery_reset_pending,
)

SCALE = 2
PREVIEW = SCREEN_W * SCALE   # 256
_ROOT = Path(__file__).resolve().parents[1]
_ICON_PATH = _ROOT / "assets" / "titorion-screen.ico"

# ---- tema ----
BG_APP = "#0f1117"
BG_CARD = "#1a1d27"
BG_INPUT = "#0a0c12"
FG = "#e5e7eb"
FG_MUTED = "#9ca3af"
ACCENT = "#4f46e5"
ACCENT_HOVER = "#6366f1"
BTN_DISABLED = "#374151"
OK = "#22c55e"
ERR = "#ef4444"
BORDER = "#2d3142"


def _flat_button(parent, text, command, primary=True) -> tk.Button:
    return tk.Button(
        parent, text=text, command=command,
        bg=ACCENT if primary else BTN_DISABLED, fg="#ffffff",
        activebackground=ACCENT_HOVER if primary else "#4b5563",
        activeforeground="#ffffff", relief="flat", bd=0, padx=10, pady=4,
        font=("Segoe UI", 8, "bold"), cursor="hand2",
        disabledforeground="#6b7280",
    )


def _card(parent, title: str) -> tk.Frame:
    card = tk.Frame(parent, bg=BG_CARD, highlightthickness=1,
                    highlightbackground=BORDER)
    title_lbl = tk.Label(card, text=title, bg=BG_CARD, fg=FG_MUTED,
                         font=("Segoe UI", 7, "bold"))
    title_lbl.pack(anchor="w", padx=8, pady=(6, 2))
    card.title_lbl = title_lbl
    return card


def _champion_name(mode: str) -> str:
    """Nome no modo league:idioma:nome:nível. Vazio fora do cartaz do campeão."""
    if not mode.startswith("league:"):
        return ""
    parts = mode.split(":")
    if len(parts) < 4:
        return ""
    return ":".join(parts[2:-1])


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Titorion Screen Studio")
        self.configure(bg=BG_APP)
        self.resizable(False, False)

        self.screen: TitorionScreen | None = None
        self.monitor_on = False
        self.monitor_thread: threading.Thread | None = None
        self.static_img: Image.Image | None = None
        self._tk_img = None  # manter referencia viva do PhotoImage
        self._last_img: Image.Image | None = None  # ultimo frame no preview
        self.zoom = 2        # zoom do preview (1 = tamanho real da telinha)
        self._icon_image = app_mark(64)
        self.tray: pystray.Icon | None = None
        self._status_key = "disconnected"
        self._status_ok = False
        self._force_frame = False
        self._resetting = False

        self._build_ui()
        self._apply_window_icon()
        self.protocol("WM_DELETE_WINDOW", self._hide)
        self.log(t("tray_hint"))
        self.withdraw()
        self._start_tray()
        self.after(100, self.connect)

    def _apply_window_icon(self) -> None:
        _ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
        sizes = [app_mark(side) for side in (16, 32, 48, 64)]
        sizes[0].save(
            _ICON_PATH,
            format="ICO",
            sizes=[(side, side) for side in (16, 32, 48, 64)],
            append_images=sizes[1:],
        )
        self._window_icon = ImageTk.PhotoImage(self._icon_image)
        self.iconphoto(True, self._window_icon)

    def _start_tray(self) -> None:
        menu = self._tray_menu()
        self.tray = pystray.Icon(
            "titorion-screen",
            self._icon_image,
            "Titorion Screen",
            menu,
        )
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _tray_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(t("tray_open"), self._show_from_tray, default=True),
            pystray.MenuItem(t("tray_reset"), self._reset_from_tray),
            pystray.MenuItem(t("tray_quit"), self._quit_from_tray),
        )

    def _show_from_tray(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.after(0, self._show)

    def _quit_from_tray(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.after(0, self._quit)

    def _reset_from_tray(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.after(0, self.reset_screen)

    def _show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _hide(self) -> None:
        """Fecha a janela sem parar o teclado. O ícone fica na bandeja."""
        self.withdraw()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=BG_APP)
        header.pack(fill="x", padx=10, pady=(8, 4))
        self._header_logo = ImageTk.PhotoImage(app_mark(28))
        tk.Label(header, image=self._header_logo, bg=BG_APP).pack(side="left")
        tk.Label(header, text="Titorion Screen Studio",
                 bg=BG_APP, fg=FG, font=("Segoe UI", 11, "bold")).pack(side="left", padx=(8, 0))
        self.status_lbl = tk.Label(header, text="", bg=BG_APP,
                                   fg=ERR, font=("Segoe UI", 8))
        self.status_lbl.pack(side="right")

        main = tk.Frame(self, bg=BG_APP)
        main.pack(padx=10, pady=4)

        # Preview
        preview_card = _card(main, "")
        self.preview_card = preview_card
        preview_card.pack(side="left", padx=(0, 8))
        self.preview = tk.Label(preview_card, bg="#000000")
        self.preview.pack(padx=8, pady=(0, 4))
        # Label sem imagem mede em "caracteres" (fica gigante);
        # com imagem, mede em pixels. Inicializa com tela preta.
        self.show_preview(Image.new("RGB", (SCREEN_W, SCREEN_H)))
        self.btn_zoom = _flat_button(preview_card, "",
                                     self.toggle_zoom, primary=False)
        self.btn_zoom.pack(padx=8, pady=(0, 8), fill="x")

        # Controles
        right = tk.Frame(main, bg=BG_APP)
        right.pack(side="left", fill="y")

        lang_card = _card(right, "")
        self.lang_card = lang_card
        lang_card.pack(fill="x", pady=(0, 6))
        lang_row = tk.Frame(lang_card, bg=BG_CARD)
        lang_row.pack(fill="x", padx=8, pady=(0, 8))
        self.btn_lang_pt = _flat_button(lang_row, "PT", lambda: self.choose_language("pt"))
        self.btn_lang_pt.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_lang_en = _flat_button(lang_row, "EN", lambda: self.choose_language("en"),
                                        primary=False)
        self.btn_lang_en.pack(side="left", expand=True, fill="x")

        conn_card = _card(right, "")
        self.conn_card = conn_card
        conn_card.pack(fill="x", pady=(0, 6))
        self.btn_connect = _flat_button(conn_card, "", self.connect)
        self.btn_connect.pack(padx=8, pady=(0, 8), fill="x")

        mon_card = _card(right, "")
        self.mon_card = mon_card
        mon_card.pack(fill="x", pady=(0, 6))
        row = tk.Frame(mon_card, bg=BG_CARD)
        row.pack(fill="x", padx=8, pady=(0, 4))
        self.interval_lbl = tk.Label(row, text="", bg=BG_CARD, fg=FG,
                                      font=("Segoe UI", 8))
        self.interval_lbl.pack(side="left")
        self.interval_var = tk.StringVar(value="10")
        tk.Spinbox(row, from_=5, to=300, width=4, textvariable=self.interval_var,
                   bg=BG_INPUT, fg=FG, buttonbackground=BTN_DISABLED,
                   relief="flat", insertbackground=FG,
                   font=("Segoe UI", 8)).pack(side="right")
        self.btn_monitor = _flat_button(mon_card, "", self.toggle_monitor)
        self.btn_monitor.pack(padx=8, pady=(0, 4), fill="x")
        self.btn_reset = _flat_button(mon_card, "", self.reset_screen, primary=False)
        self.btn_reset.pack(padx=8, pady=(0, 8), fill="x")

        img_card = _card(right, "")
        self.img_card = img_card
        img_card.pack(fill="x")
        self.btn_pick = _flat_button(img_card, "", self.pick_image, primary=False)
        self.btn_pick.pack(padx=8, fill="x")
        self.btn_send_img = _flat_button(img_card, "", self.send_static)
        self.btn_send_img.pack(padx=8, pady=(4, 4), fill="x")
        self.btn_send_img.configure(state="disabled")
        self.btn_red = _flat_button(img_card, "", self.send_red, primary=False)
        self.btn_red.pack(padx=8, pady=(0, 8), fill="x")

        # Log
        log_card = _card(self, "")
        self.log_card = log_card
        log_card.pack(fill="both", padx=10, pady=(2, 8))
        self.log_txt = tk.Text(log_card, height=4, bg=BG_INPUT, fg=FG_MUTED,
                               relief="flat", font=("Consolas", 8),
                               state="disabled", wrap="word")
        self.log_txt.pack(fill="both", padx=8, pady=(0, 6))
        self._apply_copy()

    def _apply_copy(self) -> None:
        """Reescreve a janela e o menu da bandeja no idioma atual."""
        self.preview_card.title_lbl.configure(text=t("preview_title"))
        self.lang_card.title_lbl.configure(text=t("language"))
        self.conn_card.title_lbl.configure(text=t("connection"))
        self.mon_card.title_lbl.configure(text=t("monitor_title"))
        self.img_card.title_lbl.configure(text=t("still_title"))
        self.log_card.title_lbl.configure(text=t("log_title"))
        self.interval_lbl.configure(text=t("interval"))
        self.btn_connect.configure(text=t("reconnect"))
        self.btn_pick.configure(text=t("choose_image"))
        self.btn_send_img.configure(text=t("send_image"))
        self.btn_red.configure(text=t("red_test"))
        self.btn_reset.configure(text=t("reset_screen"))
        suffix = t("zoom_real") if self.zoom == 1 else ""
        self.btn_zoom.configure(text=t("zoom", n=self.zoom, suffix=suffix))
        if not self.monitor_on:
            monitor_text = t("start_monitor")
        elif str(self.btn_monitor["state"]) == "disabled":
            monitor_text = t("stopping")
        else:
            monitor_text = t("stop_monitor")
        self.btn_monitor.configure(text=monitor_text)
        self.set_status(self._status_ok, self._status_key)
        self._paint_lang_buttons()
        if self.tray is not None:
            self.tray.menu = self._tray_menu()
            self.tray.update_menu()

    def _paint_lang_buttons(self) -> None:
        selected = current()
        for code, button in (("pt", self.btn_lang_pt), ("en", self.btn_lang_en)):
            on = code == selected
            button.configure(
                bg=ACCENT if on else BTN_DISABLED,
                activebackground=ACCENT_HOVER if on else "#4b5563",
            )

    def choose_language(self, code: str) -> None:
        if code == current():
            return
        set_language(code)
        self._apply_copy()
        self.log(t("language_set"))
        self._force_frame = True
        threading.Thread(target=self._refresh_language, daemon=True).start()

    def _refresh_language(self) -> None:
        """Atualiza o preview. Sem o monitor, também manda o cartaz ao teclado."""
        try:
            img, text, _mode = build_frame()
        except Exception as e:
            self.after(0, self.log, t("monitor_error", error=e))
            return
        self.after(0, self.show_preview, img)
        if self.monitor_on or self.screen is None:
            return
        try:
            self.screen.send_image(img)
        except Exception as e:
            self.after(0, self.log, t("send_fail", error=e))
            return
        self._force_frame = False
        self.after(0, self.log, t("sent_line", text=text))

    # ---------------- helpers (thread da UI) ----------------

    def log(self, msg: str) -> None:
        self.log_txt.configure(state="normal")
        self.log_txt.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")

    def set_status(self, ok: bool, key: str) -> None:
        self._status_ok = ok
        self._status_key = key
        self.status_lbl.configure(text=f"● {t(key)}", fg=OK if ok else ERR)

    def show_preview(self, img: Image.Image) -> None:
        self._last_img = img
        size = SCREEN_W * self.zoom
        big = img.resize((size, size), Image.NEAREST)
        self._tk_img = ImageTk.PhotoImage(big)
        self.preview.configure(image=self._tk_img)

    def toggle_zoom(self) -> None:
        self.zoom = 1 if self.zoom == 2 else 2
        suffix = t("zoom_real") if self.zoom == 1 else ""
        self.btn_zoom.configure(text=t("zoom", n=self.zoom, suffix=suffix))
        if self._last_img is not None:
            self.show_preview(self._last_img)

    # ---------------- acoes ----------------

    def connect(self) -> None:
        try:
            if self.screen:
                self.screen.close()
            self.screen = TitorionScreen()
            self.screen.connect()
            self.set_status(True, "connected")
            self.log(t("keyboard_connected"))
            self.after(400, self._boot_screen)
        except Exception as e:
            self.screen = None
            self.set_status(False, "not_found")
            self.log(f"❌ {e}")

    def _boot_screen(self) -> None:
        """Se a memória da tela ficou para trás, esvazia antes de acompanhar."""
        if gallery_reset_pending():
            self.reset_screen(restart_monitor=True)
            return
        self._autostart_monitor()

    def reset_screen(self, restart_monitor: bool = False) -> None:
        """Apaga as imagens guardadas e grava o cartaz atual de novo."""
        if self._resetting:
            return
        if not self.screen:
            self.log(t("connect_first"))
            return
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_on = False
            self.monitor_thread.join(timeout=20)
            if self.monitor_thread.is_alive():
                self.log(t("reset_busy"))
                return
        self._resetting = True
        self.btn_reset.configure(state="disabled")
        self.log(t("resetting"))
        threading.Thread(
            target=self._reset_worker, args=(restart_monitor,), daemon=True,
        ).start()

    def _reset_worker(self, restart_monitor: bool) -> None:
        try:
            img, _text, _mode = build_frame()
            assert self.screen is not None
            self.screen.reset_gallery(img)
        except Exception as e:
            self._resetting = False
            self.after(0, self.btn_reset.configure, {"state": "normal"})
            self.after(0, self.log, t("reset_fail", error=e))
            self.after(0, self.set_status, False, "reconnect_status")
            return
        self._resetting = False
        self._force_frame = True
        self.after(0, self.btn_reset.configure, {"state": "normal"})
        self.after(0, self.show_preview, img)
        self.after(0, self.log, t("reset_done"))
        if restart_monitor:
            self.after(0, self._autostart_monitor)

    def _autostart_monitor(self) -> None:
        """Acompanha o app em foco: limite no Cursor/Claude, stats no resto."""
        if self.screen and not self.monitor_on:
            self.toggle_monitor()

    def toggle_monitor(self) -> None:
        if self.monitor_on:
            self.monitor_on = False
            self.btn_monitor.configure(text=t("stopping"), state="disabled")
            self.log(t("stopping_log"))
        else:
            if not self.screen:
                self.log(t("connect_first"))
                return
            try:
                interval = max(5.0, float(self.interval_var.get().replace(",", ".")))
            except ValueError:
                interval = 10.0
            interval = max(10.0, interval)
            self.interval_var.set(str(int(interval)))
            self.monitor_on = True
            self.btn_monitor.configure(text=t("stop_monitor"))
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop, args=(interval,), daemon=True)
            self.monitor_thread.start()
            self.log(t("following"))

    def _monitor_loop(self, interval: float) -> None:
        last_bytes: bytes | None = None
        last_sent = 0.0
        last_mode = ""
        last_champion = ""
        while self.monitor_on:
            try:
                img, text, mode = build_frame()
                digest = img.tobytes()
                now = time.monotonic()
                switched = mode != last_mode or self._force_frame
                # Troca de janela ou de idioma sai na hora. O mesmo cartaz espera o intervalo.
                due = switched or now - last_sent >= interval
                champion = _champion_name(mode)
                champion_changed = bool(champion) and champion != last_champion
                # Sem a limpeza, a imagem do campeão continua na tela depois que o jogo fecha.
                leaving_champion = bool(last_champion) and not champion
                if digest != last_bytes and due and now - last_sent >= 2:
                    assert self.screen is not None
                    if champion_changed or leaving_champion:
                        self.after(0, self.log, t("resetting"))
                        self.screen.reset_gallery(img)
                        last_champion = champion
                    else:
                        self.screen.send_image(img)
                    last_bytes = digest
                    last_sent = time.monotonic()
                    last_mode = mode
                    self._force_frame = False
                    self.after(0, self.show_preview, img)
                    self.after(0, self.log, t("sent_line", text=text))
            except Exception as e:
                self.after(0, self.log, t("monitor_error", error=e))
                time.sleep(2)
                continue
            for _ in range(10):
                if not self.monitor_on:
                    break
                time.sleep(0.1)
        self.after(0, self._monitor_stopped)

    def _monitor_stopped(self) -> None:
        self.monitor_on = False
        self.btn_monitor.configure(text=t("start_monitor"), state="normal")
        self.log(t("monitor_stopped"))

    def pick_image(self) -> None:
        path = filedialog.askopenfilename(
            title=t("dialog_title"),
            filetypes=[(t("dialog_images"), "*.png *.jpg *.jpeg *.bmp *.webp"),
                       (t("dialog_all"), "*.*")])
        if not path:
            return
        try:
            self.static_img = Image.open(path)
            preview_img = self.static_img.convert("RGB").resize(
                (SCREEN_W, SCREEN_H))
            self.show_preview(preview_img)
            self.btn_send_img.configure(state="normal")
            self.log(t("image_loaded", name=Path(path).name))
            self.send_static()  # envia na hora: teclado = preview
        except Exception as e:
            self.log(t("image_open_fail", error=e))

    def _send_worker(self, img: Image.Image, what: str) -> None:
        try:
            assert self.screen is not None
            self.screen.send_image(img)
            self.after(0, self.log, t("sent_ok", what=what))
        except Exception as e:
            self.after(0, self.log, t("send_fail", error=e))
            self.after(0, self.set_status, False, "reconnect_status")

    def _send(self, img: Image.Image, what: str) -> None:
        if not self.screen:
            self.log(t("connect_first"))
            return
        if self.monitor_on:
            # Para o monitor para a imagem estatica nao ser sobrescrita
            self.monitor_on = False
            self.btn_monitor.configure(text=t("start_monitor"), state="normal")
            self.log(t("stopped_for_image"))
        self.show_preview(img.convert("RGB").resize((SCREEN_W, SCREEN_H)))
        self.log(t("sending", what=what))
        threading.Thread(target=self._send_worker, args=(img, what),
                         daemon=True).start()

    def send_static(self) -> None:
        if self.static_img:
            self._send(self.static_img, t("still_word"))

    def send_red(self) -> None:
        self._send(Image.new("RGB", (128, 128), (255, 0, 0)), t("red_screen"))

    def _quit(self) -> None:
        self.monitor_on = False
        # Espera o envio em andamento terminar antes de fechar o HID:
        # fechar no meio de um frame trava o controlador da tela.
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=6)
        if self.screen:
            self.screen.close()
        if self.tray is not None:
            self.tray.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
