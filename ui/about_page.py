"""«О программе» нового окна (задача 15, шаг 7; макет design/mockups/07_about) — вместо ui/about_tab.py.

Сверху карточка программы: значок, название, версия (config.APP_VERSION) и «Beta», слоган, описание и четыре кнопки:
«Проверить обновления» (открывает страницу релизов на GitHub — ваш ответ 7.1), «Папка бота» (папка, откуда запущена программа:
там profile.yml и bot_data/), «Написать автору», «GitHub проекта». Ниже «Автор и лицензия» и «Состояние компонентов»
(ADB и scrcpy ищутся в PATH, как их запускает бот; база шаблонов — assets_db.py или папка assets/; проверка в фоне при каждом показе
страницы). Внизу «Поддержать проект»: кошельки (на экране сокращены, кнопка копирует полный адрес), донат в Telegram
(приложение и браузер), Boosty и ЮMoney. Адреса и ссылки — ui/about_data.py (без Tk).

Страница длиннее окна — прокручивается. Строки и надписи — обычные виджеты Tk на готовых подложках (RoundedBackdrop),
CustomTkinter — только карточки и кнопки: при прокрутке в Windows ничего не дорисовывается с задержкой.
Окно в интернет не ходит: все кнопки открывают ссылки в браузере.
"""
import queue
import threading
import tkinter as tk
import webbrowser

import customtkinter as ctk

from config import APP_VERSION
from i18n import get_text
from ui import about_data, theme
from ui.widgets import (Button, Card, ClickFrame, IconButton, PlainLabel, RoundedBackdrop, Toast, pill_label, plain_icon)

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES
BG = C["bg_surface"]
ELEV = C["bg_elevated"]
POLL_MS = 100
ROW_HEIGHT = 36
BUTTONS_WIDTH = 220


def px(widget, value):
    return round(value * ctk.ScalingTracker.get_widget_scaling(widget))


def icon_label(master, name, color, size, bg, box=None, tint=None, radius=8):
    """Значок обычной надписью Tk (без холста CustomTkinter); ссылку на картинку держит сам."""
    photo = plain_icon(master, name, color, size, box=box, tint=tint, bg=bg, radius=radius)
    label = tk.Label(master, image=photo, bg=bg, bd=0, highlightthickness=0)
    label.photo = photo
    return label


class DonateButton(ClickFrame):
    """Кнопка прямого перевода (макет: цветной квадрат со значком, название, стрелка «открыть»). Наведение — только цвет рамки."""

    def __init__(self, master, color, text, command):
        super().__init__(master, command=command, fg_color=ELEV, border_width=1, border_color=C["border"],
                         corner_radius=8, height=48, width=10)
        self.grid_propagate(False)          # высота 48 — по макету, а не по содержимому
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._look = None
        self.mark = icon_label(self, "heart-filled", C["white"], 16, bg=ELEV, box=32, tint=color)
        self.mark.grid(row=0, column=0, padx=(8, 12))
        self.title = PlainLabel(self, text, font=F["body"], color=C["text"], bg=ELEV, anchor="w")
        self.title.grid(row=0, column=1, sticky="w")
        self.arrow = icon_label(self, "external-link", C["text_muted"], 14, bg=ELEV)
        self.arrow.grid(row=0, column=2, padx=(8, 14))
        for part in (self.mark, self.title, self.arrow):
            part.configure(cursor="hand2")
        self.bind_parts(self.mark, self.title, self.arrow)
        self._paint()

    def _paint(self):
        look = C["border_focus"] if self._hovering else C["border"]
        if look != self._look:
            self._look = look
            self.configure(border_color=look)


class AboutPage(ctk.CTkScrollableFrame):
    full_bleed = True   # без отступов окна: полоса прокрутки у самого края

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent", corner_radius=0,
                         scrollbar_button_color=C["border_strong"], scrollbar_button_hover_color=C["border_focus"])
        self.controller = controller
        self.lang = getattr(controller, "current_lang", "RU")
        self.found = None                 # {"adb": bool, ...} последней проверки или None, пока не проверяли
        self._results = queue.Queue()     # ответ проверки компонентов из фонового потока
        self._checking = False
        self._poll_id = None
        self._texts = []                  # (виджет, ключ надписи): язык меняется на лету
        self._status = {}                 # ключ компонента -> (значок, надпись)
        self.grid_columnconfigure(0, weight=1)
        self._build_hero()
        self._build_info()
        self._build_support()
        self.update_language(self.lang)

    def text(self, key):
        return get_text(self.lang, key)

    def tr(self, widget, key):
        """Надпись, которую update_language() переводит сама."""
        self._texts.append((widget, key))
        return widget

    def open_url(self, url):
        url = about_data.safe_url(url)
        if url:
            webbrowser.open(url)

    # ── Карточка программы ──────────────────────────────────────────────────
    def _build_hero(self):
        card = Card(self, width=10, height=10)
        card.grid(row=0, column=0, sticky="ew", padx=(24, 12), pady=(24, 16))
        card.grid_columnconfigure(1, weight=1)
        pad = 20
        icon_label(card, "shield-check", C["green"], 32, bg=BG, box=64, tint=ELEV, radius=14).grid(
            row=0, column=0, sticky="n", padx=(pad, pad), pady=pad)

        body = tk.Frame(card, bg=BG)
        body.grid(row=0, column=1, sticky="nsew", pady=pad)
        body.grid_columnconfigure(0, weight=1)
        title = tk.Frame(body, bg=BG)
        title.grid(row=0, column=0, sticky="w")
        PlainLabel(title, about_data.PROJECT_NAME, font=F["app_name"], color=C["text"], bg=BG).pack(side="left")
        pill_label(title, f"v{APP_VERSION}", F["mono"], C["text_secondary"], ELEV, BG, height=22).pack(
            side="left", padx=(10, 0))
        pill_label(title, about_data.STAGE, F["label_bold"], C["warning"], T["warning_on_surface"], BG, height=22).pack(
            side="left", padx=(10, 0))
        slogan = self.tr(PlainLabel(body, "", font=F["body"], color=C["text"], bg=BG, anchor="w", justify="left",
                                        width=1), "ab_slogan")
        slogan.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self._wrap(slogan, body, 0)
        plate = tk.Frame(body, bg=BG)
        plate.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        RoundedBackdrop(plate, ELEV, C["border"], BG, radius=8)
        text = self.tr(PlainLabel(plate, "", font=F["text"], color=C["text_secondary"], bg=ELEV, anchor="w",
                                      justify="left", width=1), "ab_text")
        text.pack(fill="x", padx=px(self, 16), pady=px(self, 14))
        self._wrap(text, plate, 2 * 16 + 2)

        buttons = tk.Frame(card, bg=BG)
        buttons.grid(row=0, column=2, sticky="n", padx=(pad, pad), pady=pad)
        buttons.grid_columnconfigure(0, weight=1, minsize=px(self, BUTTONS_WIDTH))
        for i, (key, kind, icon_name, command) in enumerate((
                ("ab_check_updates", "secondary", "refresh-cw", lambda: self.open_url(about_data.RELEASES_URL)),
                ("ab_open_folder", "secondary", "folder", self.open_folder),
                ("about_btn_mail", "blue", "send", lambda: self.open_url(about_data.mail_url())),
                ("about_btn_github", "secondary", "code", lambda: self.open_url(about_data.GITHUB_URL)))):
            button = Button(buttons, "", kind=kind, icon_name=icon_name, icon_size=15, pad_x=12, anchor="w",
                            command=command)
            button.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 8, 0))
            self.tr(button, key)

    def _wrap(self, label, frame, indent):
        """Подгонять перенос строк надписи под ширину рамки (width=1 у надписи: она не раздвигает рамку, а сжимается с ней)."""
        def fit(event):
            width = event.width - px(self, indent)
            if width > 50 and int(float(label.cget("wraplength") or 0)) != width:
                label.configure(wraplength=width)
        label.configure(wraplength=px(self, 560))
        frame.bind("<Configure>", fit, add="+")

    def open_folder(self):
        if not about_data.open_folder(about_data.program_folder()):
            Toast(self, self.text("ab_folder_fail"), kind="error")

    # ── Автор, лицензия, компоненты ─────────────────────────────────────────
    def _info_card(self, column, title_key):
        card = Card(self.pair, width=10, height=10)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
        card.grid_columnconfigure(0, weight=1)
        self.tr(PlainLabel(card, "", font=F["card_title"], color=C["text"], bg=BG, anchor="w"), title_key).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 6))
        return card

    def _info_row(self, card, row, icon_name, label=None, label_key=None):
        """Полоса 36 px (макет 07): значок, подпись слева; справа кладёт вызвавший. Возвращает рамку полосы."""
        line = tk.Frame(card, bg=BG, height=px(self, ROW_HEIGHT))
        line.grid(row=row, column=0, sticky="ew", padx=16, pady=(10 if row > 1 else 0, 0))
        line.grid_propagate(False)
        line.grid_columnconfigure(2, weight=1)
        line.grid_rowconfigure(0, weight=1)
        RoundedBackdrop(line, ELEV, ELEV, BG, radius=6)
        icon_label(line, icon_name, C["text_secondary"], 16, bg=ELEV).grid(row=0, column=0, padx=(12, 10))
        name = PlainLabel(line, label or "", font=F["text"], color=C["text_secondary"], bg=ELEV, anchor="w")
        name.grid(row=0, column=1)
        if label_key:
            self.tr(name, label_key)
        return line

    def _build_info(self):
        self.pair = tk.Frame(self, bg=C["bg_primary"])
        self.pair.grid(row=1, column=0, sticky="ew", padx=(24, 12), pady=(0, 16))
        self.pair.grid_columnconfigure((0, 1), weight=1, uniform="info")

        author = self._info_card(0, "ab_author_license")
        line = self._info_row(author, 1, "user", label_key="ab_author")
        PlainLabel(line, about_data.AUTHOR, font=F["text"], color=C["text"], bg=ELEV).grid(row=0, column=3, padx=(8, 12))
        line = self._info_row(author, 2, "mail", label="Email")
        link = PlainLabel(line, about_data.EMAIL, font=F["text"], color=C["blue_text"], bg=ELEV, cursor="hand2")
        link.grid(row=0, column=3, padx=(8, 12))
        link.bind("<Button-1>", lambda _e: self.open_url(about_data.mail_url()), add="+")
        line = self._info_row(author, 3, "file-text", label_key="ab_license")
        PlainLabel(line, about_data.LICENSE_NAME, font=F["text"], color=C["text"], bg=ELEV).grid(
            row=0, column=3, padx=(8, 12))
        tk.Frame(author, bg=BG, height=px(self, 16)).grid(row=4, column=0)

        components = self._info_card(1, "ab_components")
        for i, (key, label, icon_name) in enumerate(about_data.COMPONENTS, start=1):
            line = self._info_row(components, i, icon_name, label=label, label_key="ab_templates" if not label else None)
            state = tk.Frame(line, bg=ELEV)
            state.grid(row=0, column=3, padx=(8, 12))
            mark = tk.Label(state, bg=ELEV, bd=0, highlightthickness=0)
            name = PlainLabel(state, "", font=F["text"], color=C["text_secondary"], bg=ELEV)
            mark.pack(side="left", padx=(0, 6))
            name.pack(side="left")
            self._status[key] = (mark, name)
        tk.Frame(components, bg=BG, height=px(self, 16)).grid(row=4, column=0)

    # ── Поддержать проект ───────────────────────────────────────────────────
    def _panel(self, parent, column, title_key):
        """Серая панель с рамкой внутри карточки доната; возвращает рамку для содержимого."""
        outer = tk.Frame(parent, bg=BG)
        outer.grid(row=0, column=column, sticky="nsew", padx=(0, 6) if column == 0 else (6, 0))
        RoundedBackdrop(outer, ELEV, C["border"], BG, radius=8)
        inner = tk.Frame(outer, bg=ELEV)
        inner.pack(fill="both", expand=True, padx=px(self, 14), pady=px(self, 14))
        inner.grid_columnconfigure(0, weight=1)
        self.tr(PlainLabel(inner, "", font=F["button_bold"], color=C["text"], bg=ELEV, anchor="w"),
                    title_key).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        return inner

    def _build_support(self):
        card = Card(self, width=10, height=10)
        card.grid(row=2, column=0, sticky="ew", padx=(24, 12), pady=(0, 24))
        card.grid_columnconfigure(0, weight=1)
        head = tk.Frame(card, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 0))
        head.grid_columnconfigure(1, weight=1)
        icon_label(head, "heart", C["gold"], 20, bg=BG, box=40, tint=T["gold_on_surface"], radius=10).grid(
            row=0, column=0, rowspan=2, sticky="n", padx=(0, 14))
        self.tr(PlainLabel(head, "", font=F["dialog_title"], color=C["gold"], bg=BG, anchor="w"),
                    "ab_support_title").grid(row=0, column=1, sticky="w")
        text = self.tr(PlainLabel(head, "", font=F["text"], color=C["text_secondary"], bg=BG, anchor="w",
                                      justify="left", width=1), "ab_support_text")
        text.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        self._wrap(text, head, 40 + 14 + 6)

        panels = tk.Frame(card, bg=BG)
        panels.grid(row=1, column=0, sticky="ew", padx=20, pady=(16, 0))
        panels.grid_columnconfigure(0, weight=5, uniform="panel")
        panels.grid_columnconfigure(1, weight=4, uniform="panel")
        self._build_crypto(self._panel(panels, 0, "ab_crypto"))
        self._build_telegram(self._panel(panels, 1, "ab_tg_donate"))

        direct = tk.Frame(card, bg=BG)
        direct.grid(row=2, column=0, sticky="ew", padx=20, pady=(16, 20))
        direct.grid_columnconfigure((0, 1), weight=1, uniform="direct")
        self.tr(PlainLabel(direct, "", font=F["button_bold"], color=C["text"], bg=BG, anchor="w"),
                    "ab_direct").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.donate_buttons = {}
        for column, (key, text_key, url) in enumerate(about_data.DIRECT_DONATE):
            button = DonateButton(direct, theme.DONATE_COLORS[key], "", lambda u=url: self.open_url(u))
            button.grid(row=1, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0))
            self.tr(button.title, text_key)
            self.donate_buttons[key] = button

    def _build_crypto(self, panel):
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=0)
        self.wallet_buttons = {}
        for i, (key, label, address) in enumerate(about_data.WALLETS, start=1):
            PlainLabel(panel, label, font=F["text"], color=C["text_secondary"], bg=ELEV, anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 12), pady=(0 if i == 1 else 8, 0))
            pill = tk.Frame(panel, bg=ELEV, height=px(self, 34))
            pill.grid(row=i, column=1, sticky="ew", pady=(0 if i == 1 else 8, 0))
            pill.pack_propagate(False)
            RoundedBackdrop(pill, C["bg_primary"], C["border"], ELEV, radius=6)
            PlainLabel(pill, about_data.shorten(address), font=F["mono"], color=C["text"], bg=C["bg_primary"],
                       anchor="w").pack(fill="both", expand=True, padx=px(self, 10))
            button = IconButton(panel, "copy", size=34, icon_size=14, fg_color="transparent", hover_color=T["hover_elevated"],
                                border_color=C["border_strong"], tooltip=lambda: self.text("ab_copy"),
                                command=lambda a=address: self.copy(a))
            button.grid(row=i, column=2, padx=(8, 0), pady=(0 if i == 1 else 8, 0))
            self.wallet_buttons[key] = button

    def _build_telegram(self, panel):
        panel.grid_columnconfigure(0, weight=0)
        panel.grid_columnconfigure((1, 2), weight=1, uniform="tg")
        for i, (currency, app_url, web_url) in enumerate(about_data.TELEGRAM_DONATE, start=1):
            pad = (0 if i == 1 else 8, 0)
            PlainLabel(panel, currency, font=F["mono"], color=C["text_secondary"], bg=ELEV, anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 12), pady=pad)
            app = Button(panel, "", kind="blue", height=34, font=F["label_bold"], pad_x=8,
                         command=lambda u=app_url: self.open_url(u))
            app.grid(row=i, column=1, sticky="ew", padx=(0, 4), pady=pad)
            web = Button(panel, "", kind="secondary", height=34, font=F["label"], pad_x=8, fg_color="transparent",
                         border_color=C["border_strong"], hover_color=T["hover_elevated"],
                         command=lambda u=web_url: self.open_url(u))
            web.grid(row=i, column=2, sticky="ew", padx=(4, 0), pady=pad)
            self.tr(app, "ab_app")
            self.tr(web, "ab_browser")

    def copy(self, address):
        """Полный адрес — в буфер обмена (на экране он сокращён)."""
        self.clipboard_clear()
        self.clipboard_append(address)
        Toast(self, self.text("ab_copied"), kind="success")

    # ── Состояние компонентов ───────────────────────────────────────────────
    def refresh_data(self):
        """Проверить компоненты в фоне (при каждом показе страницы). Пока ответа нет — «проверяю…», старый ответ не мигает."""
        if self._checking:
            return
        self._checking = True
        if self.found is None:
            self._render_components()
        threading.Thread(target=lambda: self._results.put(about_data.check_components()), daemon=True).start()
        self._poll_id = self.after(POLL_MS, self._poll)

    def _poll(self):
        self._poll_id = None
        try:
            self.found = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(POLL_MS, self._poll)
            return
        self._checking = False
        self._render_components()

    def _render_components(self):
        for key, (mark, name) in self._status.items():
            ok = None if self.found is None else self.found.get(key, False)
            if ok is None:
                mark.configure(image="")
                name.configure(text=self.text("ab_checking"), fg=C["text_muted"])
                continue
            word = {"templates": ("ab_loaded", "ab_not_loaded")}.get(key, ("ab_found", "ab_not_found"))[0 if ok else 1]
            color = C["success"] if ok else C["danger_text"]
            mark.photo = plain_icon(self, "check" if ok else "x", color, 13)
            mark.configure(image=mark.photo)
            name.configure(text=self.text(word), fg=color)

    # ── Язык и закрытие ─────────────────────────────────────────────────────
    def update_language(self, lang):
        self.lang = lang
        for widget, key in self._texts:
            widget.configure(text=theme.plain_text(get_text(lang, key)))
        self._render_components()

    def destroy(self):
        if self._poll_id:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        super().destroy()
