"""Главная нового окна (задача 15, шаг 3; макет design/mockups/01_main): запуск фарма, текущая сессия, журнал, окна SOS.

Вместо старой главной ui/dashboard.py (она остаётся старому окну). Связь с ботом — ui/bot_link.py (протокол тот же),
окна вмешательства — ui/sos_dialogs.py и ui/titan_picker.py, Telegram — ui/sos_telegram.py (с повторами).

Сверху карточка в одном из состояний (сверка 1.4–1.8, ваши ответы 22.10.2026):
- «С чего начать» — пока нет profile.yml (настройки ни разу не сохраняли): подключить телефон, проверить паки, Telegram;
- «Конфигурация запуска» — цель сессии (одна, первая ненулевая), «Бот решает сам», порог паники, сброс дня (profile.yml);
- «Текущая сессия» — бот работает: титанит, этажи и дверь, бои, время (и «комната в среднем»); полоска — по цели;
- «Итог сессии» — бот остановился: те же цифры, причина, «Подробно» (строки [ИТОГ]); ✕ — снова конфигурация.
Справа: «Подключить телефон» / «Начать фарм» / «Свернуть в мини-бар» (до шага 4 сворачивает окно на панель задач),
«Пауза F9» (на паузе и после [ПАУЗА ОТЛАДКИ] — зелёная «Продолжить») и «СТОП F10».
Ниже журнал: строки бота как есть, тег цветом своей «таблетки» (ui/log_lines.py), таблетки «Все / Бои / Правила /
Система / Ошибки (N)» — выбранная запоминается (bot_data/ui_settings.json), «Копировать» по правому щелчку.

Всё, что приходит из фоновых потоков (строки бота, ответ scrcpy, ответ из Telegram), окно забирает из очереди App.events
(ui/app.py разбирает её раз в 100 мс и зовёт on_event). Виджеты — только из главного потока.
Для старых вкладок главная по-прежнему frames["dash"] с append_log().
"""
import datetime
import itertools
import json
import os
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import font as tkfont

import customtkinter as ctk

import data_paths
import session_log
import telegram_report
from config import GAME_WINDOW_TITLE
from i18n import get_text
from ui import bot_link, launch_config, log_lines, sos_dialogs, theme, ui_settings
from ui.icons import dot, icon
from ui.log_lines import ALL, ERRORS, FIGHTS, FILTERS, RULES, SYSTEM
from ui.sos_telegram import SOS as TG_SOS
from ui.sos_telegram import TEST as TG_TEST
from ui.sos_telegram import TelegramQuestion, telegram_ready
from ui.titan_picker import TitanPicker
from ui.widgets import Button, Card, Chip, ClickFrame, ConfirmDialog, KeyButton, Tooltip, present_window

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

RIGHT_WIDTH = 288          # правая колонка карточки (308 px в макете вместе с отступом 20)
TICK_MS = 1000             # раз в секунду: время сессии, пауза, изменения profile.yml
MAX_LINES = 50000          # столько строк журнала окно помнит (для «Сохранить лог» и таблеток)
MAX_SHOWN = 4000           # столько последних строк показывает (полный лог бот сам пишет в bot_data/logs/)
TEST_INFO_MAX_AGE_S = 15 * 60  # окно «Пак справился»: комната и враги — из sos_info.json прошлого окна SOS
FILTER_KEYS = {ALL: "log_all", FIGHTS: "log_fights", RULES: "log_rules", SYSTEM: "log_system", ERRORS: "log_errors"}
GOAL_KEYS = {"titanite": "main_goal_titanite", "rooms": "main_goal_rooms", "floors": "main_goal_floors",
             "time": "main_goal_time"}
# Ответ из Telegram → команда боту (как ui/intervention_dialog.py и ui/dashboard.py)
TG_COMMANDS = {"manual": "MANUAL", "ignore": "IGNORE", "stop": "STOP", "CONFIRM": "CONFIRM"}


def stamp():
    """Время для строк самого окна — как у бота: 14:03:21.457."""
    return session_log.format_stamp(datetime.datetime.now())


def read_recent_info(path, max_age):
    """sos_info.json не старше max_age секунд (для окна «Пак справился» — оно бывает через несколько минут после SOS)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or time.time() - data.get("saved", 0) > max_age:
        return {}
    return data


def set_text(label, text, **colors):
    """Поменять надпись (и цвет), только если она правда поменялась: лишняя перерисовка — лишняя работа окна."""
    changes = {}
    if label.cget("text") != text:
        changes["text"] = text
    for key, value in colors.items():
        if label.cget(key) != value:
            changes[key] = value
    if changes:
        label.configure(**changes)


class Tile(ctk.CTkFrame):
    """Плашка «подпись — значение» (макет: фон bg_elevated, рамка, скругление 8). Справа в подписи — проценты цели,
    под значением — полоска цели (синяя, 4 px)."""

    def __init__(self, master):
        super().__init__(master, fg_color=C["bg_elevated"], corner_radius=8, border_width=1, border_color=C["border"])
        self.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(self, text="", font=F["label"], text_color=C["text_muted"], anchor="w", height=16)
        self.label.grid(row=0, column=0, sticky="w", padx=(12, 6), pady=(9, 0))
        self.right = ctk.CTkLabel(self, text="", font=F["label"], text_color=C["text_muted"], anchor="e", height=16)
        self.right.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=(9, 0))
        row = ctk.CTkFrame(self, fg_color="transparent", height=22)
        row.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(3, 9))
        self.icon = ctk.CTkLabel(row, text="", width=15, height=20)
        self.value = ctk.CTkLabel(row, text="", font=F["body_bold"], text_color=C["text"], height=20)
        self.value.pack(side="left")
        self.extra = ctk.CTkLabel(row, text="", font=F["body"], text_color=C["text_muted"], height=20)
        self.badge = ctk.CTkLabel(row, text="", font=F["small_bold"], corner_radius=4, height=18)
        self.bar = ctk.CTkProgressBar(self, height=4, corner_radius=2, fg_color=C["bg_primary"],
                                      progress_color=C["blue"], border_width=0)
        self._shown = {"icon": False, "extra": False, "badge": False, "bar": False}
        self._icon_key = None

    def _toggle(self, name, show, place):
        """Показать или убрать часть плашки, только если это правда поменялось."""
        if show == self._shown[name]:
            return
        self._shown[name] = show
        if show:
            place()
        elif name == "bar":
            self.bar.grid_remove()
        else:
            getattr(self, name).pack_forget()

    def show(self, label, value, mono=False, extra="", right="", icon_spec=None, badge=None, progress=None):
        set_text(self.label, label)
        set_text(self.right, right)
        font = F["mono_field"] if mono else F["body_bold"]
        if self.value.cget("font") != font:
            self.value.configure(font=font)
        set_text(self.value, value)
        if icon_spec != self._icon_key:
            self._icon_key = icon_spec
            if icon_spec:
                self.icon.configure(image=icon(icon_spec[0], icon_spec[1], 15))
        self._toggle("icon", bool(icon_spec), lambda: self.icon.pack(side="left", padx=(0, 6), before=self.value))
        set_text(self.extra, extra)
        self._toggle("extra", bool(extra), lambda: self.extra.pack(side="left", padx=(6, 0), after=self.value))
        if badge:
            text, fg, color = badge
            set_text(self.badge, text, fg_color=fg, text_color=color)
        self._toggle("badge", bool(badge), lambda: self.badge.pack(side="left", padx=(8, 0)))
        if progress is not None:
            self.bar.set(progress)
        self._toggle("bar", progress is not None,
                     lambda: self.bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 11)))


class StepRow(ctk.CTkFrame):
    """Шаг чек-листа «С чего начать»: номер в кружке (текущий — синий, готовый — зелёная галочка), заголовок,
    подпись, справа «сейчас» или ссылка («Открыть →»)."""

    def __init__(self, master, number, link_command=None):
        super().__init__(master, fg_color=C["bg_elevated"], corner_radius=8, border_width=1, border_color=C["border"])
        self.number = number
        self.grid_columnconfigure(1, weight=1)
        self.ring = ctk.CTkFrame(self, width=24, height=24, corner_radius=12, border_width=1)
        self.ring.grid(row=0, column=0, rowspan=2, padx=(12, 12), pady=9)
        self.ring.grid_propagate(False)
        self.circle = ctk.CTkLabel(self.ring, text=str(number), width=18, height=18, font=F["label_bold"],
                                   fg_color="transparent")
        self.circle.place(relx=0.5, rely=0.5, anchor="center")
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=1, sticky="sw", pady=(8, 0))
        self.title = ctk.CTkLabel(top, text="", font=F["body_bold"], text_color=C["text"], height=18, anchor="w")
        self.title.pack(side="left")
        self.optional = ctk.CTkLabel(top, text="", font=F["body"], text_color=C["text_muted"], height=18)
        self.sub = ctk.CTkLabel(self, text="", font=F["label"], text_color=C["text_secondary"], height=16, anchor="w")
        self.sub.grid(row=1, column=1, sticky="nw", pady=(1, 8))
        self.now = ctk.CTkLabel(self, text="", font=F["label_bold"], text_color=C["blue_text"], height=18)
        self.link = Button(self, "", kind="link", height=28, pad_x=8, command=link_command) if link_command else None
        self._look = None

    def set_texts(self, title, sub, optional="", now="", link=""):
        set_text(self.title, title)
        set_text(self.sub, sub)
        set_text(self.optional, f"· {optional}" if optional else "")
        if optional:
            self.optional.pack(side="left", padx=(5, 0))
        set_text(self.now, now)
        if self.link is not None and self.link.cget("text") != link:
            self.link.configure(text=link)

    def set_state(self, state):
        """state: "now" — текущий шаг, "done" — сделано, "todo" — ещё не дошли."""
        if state == self._look:
            return
        self._look = state
        if state == "now":
            self.configure(border_color=theme.blend(C["blue"], C["bg_elevated"], 0.55))
            self.ring.configure(fg_color=C["blue_button"], border_color=C["blue_button"])
            self.circle.configure(text=str(self.number), image=None, text_color=C["white"])
        elif state == "done":
            self.configure(border_color=C["border"])
            self.ring.configure(fg_color=C["green_button"], border_color=C["green_button"])
            self.circle.configure(text="", image=icon("check", C["white"], 13))
        else:
            self.configure(border_color=C["border"])
            self.ring.configure(fg_color=C["bg_primary"], border_color=C["border_strong"])
            self.circle.configure(text=str(self.number), image=None, text_color=C["text_secondary"])
        self.now.grid_remove()
        if self.link is not None:
            self.link.grid_remove()
        if state == "now" and self.link is None:
            self.now.grid(row=0, column=2, rowspan=2, padx=(8, 14))
        elif self.link is not None and state != "done":
            self.link.grid(row=0, column=2, rowspan=2, padx=(8, 8))


class DashedPanel(tk.Canvas):
    """Пустой журнал (макет первого запуска): фон bg_primary, пунктирная рамка border_strong со скруглением 8.
    У рамок CustomTkinter пунктира нет — рисуем на холсте. При смене размера перерисовываются только линии холста."""

    def __init__(self, master, radius=8):
        super().__init__(master, highlightthickness=0, bd=0, bg=C["bg_surface"], height=60)
        self.radius = radius
        self.bind("<Configure>", self._redraw, add="+")

    def _redraw(self, _event=None):
        self.delete("frame")
        w, h = self.winfo_width() - 1, self.winfo_height() - 1
        if w < 20 or h < 20:
            return
        r = round(self.radius * ctk.ScalingTracker.get_widget_scaling(self))
        fill = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h, w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
        self.create_polygon(fill, smooth=True, fill=C["bg_primary"], outline="", tags="frame")
        style = dict(fill=C["border_strong"], dash=(4, 3), tags="frame")
        for x0, y0, x1, y1 in ((r, 0, w - r, 0), (r, h, w - r, h), (0, r, 0, h - r), (w, r, w, h - r)):
            self.create_line(x0, y0, x1, y1, **style)
        for x, y, start in ((0, 0, 90), (w - 2 * r, 0, 0), (0, h - 2 * r, 180), (w - 2 * r, h - 2 * r, 270)):
            self.create_arc(x, y, x + 2 * r, y + 2 * r, start=start, extent=90, style="arc",
                            outline=C["border_strong"], dash=(4, 3), tags="frame")


class Question:
    """Открытый вопрос бота: окно вмешательства (или только Telegram), окно «Собери состав», вопрос в Telegram."""

    _ids = itertools.count(1)

    def __init__(self, kind, epoch, titans=None, room=None):
        self.id = next(Question._ids)
        self.kind = kind            # bot_link.SOS, NO_TEAM, TEST_OK
        self.epoch = epoch
        self.titans = titans or {}
        self.room = room
        self.window = None
        self.picker = None
        self.confirm = None
        self.telegram = None
        self.info = {}              # bot_data/sos_info.json этого вопроса
        self.asked_at = None        # когда бот спросил (для «бот решит сам через …»)

    def close(self):
        """Закрыть всё без ответа (бот решил сам, ответ пришёл из Telegram, бот остановился)."""
        for part in (self.confirm, self.picker):
            if part is not None:
                part.close() if isinstance(part, ConfirmDialog) else part.close_silently()
        self.confirm = self.picker = None
        if self.window is not None:
            self.window.close_silently()
        if self.telegram is not None:
            self.telegram.stop()


class SummaryWindow(ctk.CTkToplevel):
    """«Подробно» в «Итоге сессии»: строки [ИТОГ] бота (этапы, долгие комнаты, счётчики)."""

    def __init__(self, master, lang, lines):
        root = master.winfo_toplevel()
        super().__init__(root, fg_color=C["bg_surface"])
        self.withdraw()
        self.title(get_text(lang, "main_summary_title"))
        self.transient(root)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        box = ctk.CTkTextbox(self, fg_color=C["bg_primary"], border_width=1, border_color=C["border"],
                             corner_radius=8, font=F["mono"], text_color=C["text"], wrap="word", border_spacing=10)
        box.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 12))
        box.insert("end", "\n".join(lines))
        box.configure(state="disabled")
        Button(self, get_text(lang, "main_close"), kind="secondary", height=S["button_height_footer"],
               command=self.destroy).grid(row=1, column=0, sticky="e", padx=20, pady=(0, 20))
        self.bind("<Escape>", lambda _e: self.destroy())
        present_window(self, lambda: self._place(root), hidden=lambda: not self.winfo_exists())

    def _place(self, root):
        w, h = 760, 440
        x = root.winfo_rootx() + (root.winfo_width() - w) // 2
        y = root.winfo_rooty() + (root.winfo_height() - h) // 3
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")


class MainPage(ctk.CTkFrame):
    def __init__(self, master, controller, link=None):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.controller = controller
        self.lang = getattr(controller, "current_lang", "RU")
        self.link = link or bot_link.BotLink(controller.events)
        self.stats = log_lines.SessionStats()
        self.classifier = log_lines.Classifier()
        self.lines = []
        self.errors = 0
        self.settings_path = getattr(controller, "settings_path", None)
        saved = ui_settings.load(self.settings_path).get("log_filter")
        self.filter = saved if saved in FILTERS else ALL
        self.phone = False
        self.telegram_on = False
        self.connecting = False
        self.scrcpy_process = None
        self.questions = []
        self.summary_visible = False
        self.run_config = None            # настройки, с которыми запущен бот (порог паники, таймаут SOS)
        self.profile_exists, profile = launch_config.read_profile()
        self.config = launch_config.launch_config(profile)
        self._profile_mtime = self._mtime()
        self._paused = self.link.paused()
        self._pending = []
        self._flush_id = None
        self._tick_id = None
        self._shown = 0
        self._errors_shown = None
        self._empty_shown = None
        self._more_shown = True
        self._closing = False
        self._clear_dialog = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_top()
        self._build_journal()
        self.update_language(self.lang)
        self._render_log()
        self._tick_id = self.after(TICK_MS, self._tick)

    # ── Карточка сверху ─────────────────────────────────────────────────────
    def _build_top(self):
        top = Card(self)
        top.grid(row=0, column=0, sticky="ew", pady=(0, S["gap_l"]))
        top.grid_columnconfigure(0, weight=1)
        self.top = top
        self.left = ctk.CTkFrame(top, fg_color="transparent", width=10, height=10)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(20, 20), pady=20)
        self.left.grid_columnconfigure(0, weight=1)
        # Разделитель во всю высоту содержимого, как border-left правой колонки в макете (рамка CustomTkinter
        # толщиной 1 px не рисуется — обычная рамка Tk, как в шапке окна)
        tk.Frame(top, width=1, bg=C["border"]).grid(row=0, column=1, sticky="ns", pady=20)
        right = ctk.CTkFrame(top, fg_color="transparent", width=10, height=10)
        right.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        right.grid_columnconfigure(0, minsize=RIGHT_WIDTH, weight=1)
        right.grid_rowconfigure(1, weight=1)
        self._build_left_views()
        self._build_right(right)

    def _title_row(self, master):
        row = ctk.CTkFrame(master, fg_color="transparent", height=24)
        row.grid(row=0, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        title = ctk.CTkLabel(row, text="", font=F["section"], text_color=C["text"], anchor="w", height=22)
        title.grid(row=0, column=0, sticky="w")
        return row, title

    def _tiles(self, master, row=1):
        grid = ctk.CTkFrame(master, fg_color="transparent", width=10, height=10)
        grid.grid(row=row, column=0, sticky="ew", pady=(14, 0))
        grid.grid_columnconfigure((0, 1), weight=1, uniform="tile")
        tiles = []
        for i in range(4):
            tile = Tile(grid)
            tile.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 5, 5 if i % 2 == 0 else 0),
                      pady=(0 if i < 2 else 10, 0))
            tiles.append(tile)
        return tiles

    def _build_left_views(self):
        views = {}
        # С чего начать
        first = ctk.CTkFrame(self.left, fg_color="transparent", width=10, height=10)
        first.grid_columnconfigure(0, weight=1)
        row, self.first_title = self._title_row(first)
        self.first_meta = ctk.CTkLabel(row, text="", font=F["label"], text_color=C["text_muted"], height=22)
        self.first_meta.grid(row=0, column=1, sticky="e")
        steps = ctk.CTkFrame(first, fg_color="transparent", width=10, height=10)
        steps.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        steps.grid_columnconfigure(0, weight=1)
        self.steps = [StepRow(steps, 1), StepRow(steps, 2, lambda: self.controller.select_frame("rules")),
                      StepRow(steps, 3, self.open_telegram)]
        for i, step in enumerate(self.steps):
            step.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 8, 0))
        views["first"] = first
        # Конфигурация запуска
        config = ctk.CTkFrame(self.left, fg_color="transparent", width=10, height=10)
        config.grid_columnconfigure(0, weight=1)
        row, self.config_title = self._title_row(config)
        self.config_edit = Button(row, "", kind="link", height=24, pad_x=4,
                                  command=lambda: self.controller.select_frame("rules"))
        self.config_edit.grid(row=0, column=1, sticky="e")
        self.config_tiles = self._tiles(config)
        views["config"] = config
        # Текущая сессия
        session = ctk.CTkFrame(self.left, fg_color="transparent", width=10, height=10)
        session.grid_columnconfigure(0, weight=1)
        row, self.session_title = self._title_row(session)
        self.session_status = ctk.CTkLabel(row, text="", font=F["button_bold"], height=22, compound="left")
        self.session_status.grid(row=0, column=1, sticky="e")
        self.session_tiles = self._tiles(session)
        views["session"] = session
        # Итог сессии
        summary = ctk.CTkFrame(self.left, fg_color="transparent", width=10, height=10)
        summary.grid_columnconfigure(0, weight=1)
        row, self.summary_title = self._title_row(summary)
        self.summary_more = Button(row, "", kind="ghost", icon_name="file-text", icon_size=14, height=26, pad_x=8,
                                   command=self.show_summary_details)
        self.summary_more.grid(row=0, column=1, sticky="e", padx=(0, 4))
        self.summary_close = Button(row, "", kind="ghost", icon_name="x", icon_size=14, height=26, pad_x=4,
                                    command=self.hide_summary)
        self.summary_close.grid(row=0, column=2, sticky="e")
        self.summary_close_tip = Tooltip(self.summary_close, lambda: get_text(self.lang, "main_summary_hide"))
        self.summary_reason = ctk.CTkLabel(summary, text="", font=F["label"], text_color=C["text_secondary"],
                                           anchor="w", justify="left", height=16)
        self.summary_reason.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.summary_tiles = self._tiles(summary, row=2)
        self.summary_tiles[0].master.grid_configure(pady=(10, 0))
        views["summary"] = summary
        self.left_views = views
        self.left_mode = None

    def _build_right(self, right):
        self.cta = {
            "connect": Button(right, "", kind="blue", icon_name="smartphone", icon_size=20, height=S["cta_height"],
                              font=F["cta"], command=self.launch_phone),
            "start": Button(right, "", kind="cta", icon_name="play-filled", icon_size=20, command=self.start_bot),
            "running": Button(right, "", kind="secondary", icon_name="minimize-2", icon_size=18,
                              height=S["cta_height"], font=(theme.FONT_FAMILY, 16, "bold"),
                              border_color=C["border_strong"], command=self.minimize_window),
        }
        for button in self.cta.values():
            button.configure(corner_radius=8)
        self.cta["running"].configure(image=icon("minimize-2", C["blue_text"], 18))
        self.right_mode = None
        self.note = ctk.CTkLabel(right, text="", font=F["label"], text_color=C["text_muted"], wraplength=RIGHT_WIDTH - 8,
                                 justify="center")
        self.note.grid(row=1, column=0, sticky="ew", pady=10)
        controls = ctk.CTkFrame(right, fg_color="transparent", width=10, height=10)
        controls.grid(row=2, column=0, sticky="ew")
        controls.grid_columnconfigure((0, 1), weight=1, uniform="ctl")
        self.pause_button = KeyButton(controls, "", "F9", kind="pause", command=self.pause_or_continue, height=42,
                                      tooltip=lambda: get_text(self.lang, self._pause_tip))
        self.pause_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.stop_button = KeyButton(controls, "", "F10", kind="stop", command=self.stop_bot, height=42,
                                     tooltip=lambda: get_text(self.lang, "main_tip_stop"))
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._pause_tip = "main_tip_pause"

    # ── Журнал ──────────────────────────────────────────────────────────────
    def _build_journal(self):
        card = Card(self)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=(16, 12), pady=(10, 9))
        header.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(header, text="", image=icon("terminal", C["text_muted"], 16), width=16).grid(
            row=0, column=0, padx=(0, 10))
        self.log_title = ctk.CTkLabel(header, text="", font=F["section"], text_color=C["text"], height=24)
        self.log_title.grid(row=0, column=1, sticky="w")
        chips = ctk.CTkFrame(header, fg_color="transparent")
        chips.grid(row=0, column=3, sticky="e")
        self.chips = {}
        for i, key in enumerate(FILTERS):
            chip = Chip(chips, "", selected=key == self.filter, command=lambda k=key: self.set_filter(k))
            chip.pack(side="left", padx=(0 if i == 0 else 6, 0))
            self.chips[key] = chip
        tk.Frame(card, height=1, bg=C["border"]).grid(row=1, column=0, sticky="ew", padx=1)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(body, fg_color=C["bg_primary"], border_width=1, border_color=C["border"],
                                      corner_radius=8, font=F["mono"], text_color=C["text"], wrap="word",
                                      border_spacing=8, scrollbar_button_color=C["border_strong"],
                                      scrollbar_button_hover_color=C["border_focus"])
        self.log_box.grid(row=0, column=0, sticky="nsew")
        # Перенесённые строки начинаются под текстом, а не под временем (шрифт — уже с масштабом Windows)
        indent = tkfont.Font(root=self, font=self.log_box._textbox.cget("font")).measure("00:00:00.000 ")
        self.log_box.tag_config("line", spacing1=2, spacing3=2, lmargin2=indent)
        self.log_box.tag_config("time", foreground=C["text_muted"])
        for key, color in theme.LOG_CATEGORY_COLORS.items():
            self.log_box.tag_config(f"c_{key}", foreground=color)
        self._setup_readonly(self.log_box)
        self.empty = DashedPanel(body)
        self.empty.grid(row=0, column=0, sticky="nsew")
        inner = ctk.CTkFrame(self.empty, fg_color=C["bg_primary"], bg_color=C["bg_primary"], corner_radius=0)
        inner.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(inner, text="", image=icon("terminal", C["text_muted"], 22)).pack()
        self.empty_title = ctk.CTkLabel(inner, text="", font=F["body_bold"], text_color=C["text"], height=22)
        self.empty_title.pack(pady=(8, 2))
        self.empty_text = ctk.CTkLabel(inner, text="", font=F["text"], text_color=C["text_secondary"], height=18)
        self.empty_text.pack()
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.save_button = Button(footer, "", kind="secondary", icon_name="save", icon_size=15, height=34, pad_x=12,
                                  command=self.export_log)
        self.save_button.pack(side="left")
        self.send_button = Button(footer, "", kind="secondary", icon_name="send", icon_size=15, height=34, pad_x=12,
                                  command=self.send_log_to_author)
        self.send_button.pack(side="left", padx=(8, 0))
        self.clear_button = Button(footer, "", kind="ghost_danger", icon_name="trash-2", icon_size=15, height=34,
                                   pad_x=12, command=self.ask_clear_log)
        self.clear_button.pack(side="right")

    def _setup_readonly(self, textbox):
        """Журнал только для чтения: выделить и скопировать можно, менять нельзя (как в старом окне)."""
        def prevent_edit(event):
            if event.state & 0x0004 or event.state & 0x0008:
                if event.keysym.lower() in ("c", "a"):
                    return None
            if event.keysym in ("Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End"):
                return None
            return "break"

        textbox.bind("<Key>", prevent_edit)
        textbox.bind("<<Paste>>", lambda e: "break")
        textbox.bind("<<Cut>>", lambda e: "break")
        self.context_menu = tk.Menu(self, tearoff=False, bg=C["bg_elevated"], fg=C["text"],
                                    activebackground=C["blue_button"], activeforeground=C["white"], bd=0)
        self.context_menu.add_command(label="", command=self.copy_selection)
        textbox.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        try:
            if self.log_box.get(tk.SEL_FIRST, tk.SEL_LAST):
                self.context_menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            pass
        finally:
            try:
                self.context_menu.grab_release()
            except tk.TclError:
                pass

    def copy_selection(self):
        try:
            text = self.log_box.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return
        self.clipboard_clear()
        self.clipboard_append(text)

    # ── Язык ────────────────────────────────────────────────────────────────
    def update_language(self, lang):
        self.lang = lang
        g = lambda key: get_text(lang, key)  # noqa: E731
        self.first_title.configure(text=g("main_first_title"))
        self.first_meta.configure(text=g("main_first_meta"))
        self.steps[0].set_texts(g("main_step1_title"), g("main_step1_text"), now=g("main_step_now"))
        self.steps[1].set_texts(g("main_step2_title"), g("main_step2_text"), link=g("main_open"))
        self.steps[2].set_texts(g("main_step3_title"), g("main_step3_text"), optional=g("main_step3_optional"),
                                link=g("main_setup"))
        self.config_title.configure(text=g("main_config_title"))
        self.config_edit.configure(text=g("main_config_edit"))
        self.session_title.configure(text=g("main_session_title"))
        self.summary_title.configure(text=g("main_summary_title"))
        self.summary_more.configure(text=g("main_summary_more"))
        self.cta["connect"].configure(text=g("main_btn_connecting") if self.connecting else g("main_btn_connect"))
        self.cta["start"].configure(text=g("main_btn_start"))
        self.cta["running"].configure(text=g("main_btn_minimize"))
        self.stop_button.set_text(g("main_btn_stop"))
        self.log_title.configure(text=g("log_title"))
        for key, chip in self.chips.items():
            chip.set_text(g(FILTER_KEYS[key]))
        self.save_button.configure(text=g("log_save"))
        self.send_button.configure(text=g("log_send"))
        self.clear_button.configure(text=g("log_clear"))
        self.context_menu.entryconfigure(0, label=g("ctx_copy"))
        self.refresh()
        self._update_empty()

    # ── Состояние окна ──────────────────────────────────────────────────────
    def bot_running(self):
        return self.link.running()

    def _left_mode(self):
        if self.link.running():
            return "session"
        if self.summary_visible:
            return "summary"
        return "config" if self.profile_exists else "first"

    def _right_mode(self):
        if self.link.running():
            return "running"
        return "start" if self.phone else "connect"

    def refresh(self):
        """Перерисовать карточку сверху по состоянию: что слева, что справа, пауза и стоп."""
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        left = self._left_mode()
        if left != self.left_mode:
            if self.left_mode:
                self.left_views[self.left_mode].grid_remove()
            self.left_views[left].grid(row=0, column=0, sticky="nsew")
            self.left_mode = left
        if left == "first":
            self._show_first()
        elif left == "config":
            self._show_config()
        elif left == "session":
            self._show_session()
        else:
            self._show_summary()

        right = self._right_mode()
        if right != self.right_mode:
            if self.right_mode:
                self.cta[self.right_mode].grid_remove()
            self.cta[right].grid(row=0, column=0, sticky="new")
            self.right_mode = right
        connect = self.cta["connect"]
        connect.set_enabled(not self.connecting)
        set_text(connect, g("main_btn_connecting") if self.connecting else g("main_btn_connect"))
        note = {"connect": "main_note_connect", "start": "main_note_ready", "running": "main_note_running"}[right]
        set_text(self.note, g(note))

        running = self.link.running() and not self.link.starting
        if self.link.debug_wait:
            kind, text, tip = "continue", g("main_btn_continue"), "main_tip_debug"
        elif self._paused and running:
            kind, text, tip = "continue", g("main_btn_continue"), "main_tip_continue"
        else:
            kind, text, tip = "pause", g("main_btn_pause"), "main_tip_pause"
        self._pause_tip = tip
        self.pause_button.set_kind(kind, text)
        self.pause_button.set_enabled(running)
        self.stop_button.set_enabled(self.link.running())

    def _show_first(self):
        steps = self.steps
        steps[0].set_state("done" if self.phone else "now")
        steps[1].set_state("now" if self.phone else "todo")
        steps[2].set_state("done" if self.telegram_on else "todo")

    def _goal_texts(self, goal):
        """(подпись цели, значение) для плашки «Цель сессии»."""
        if not goal:
            return get_text(self.lang, "main_goal_none"), None
        kind, value = goal
        number = get_text(self.lang, "main_minutes").format(n=value) if kind == "time" else log_lines.group_digits(value)
        return f"{get_text(self.lang, GOAL_KEYS[kind])} — {number}", theme.GOAL_ICONS[kind]

    def _show_config(self):
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        cfg = self.config
        goal_text, goal_icon = self._goal_texts(cfg["goal"])
        tiles = self.config_tiles
        tiles[0].show(g("main_goal"), goal_text, icon_spec=goal_icon)
        on = cfg["auto"]
        badge = (g("main_on"), T["success_badge_bg"], C["success"]) if on else \
            (g("main_off"), C["bg_primary"], C["text_muted"])
        tiles[1].show(g("main_mode"), g("main_mode_auto"), badge=badge)
        tiles[2].show(g("main_panic"), f"{cfg['panic']}%", mono=True)
        tiles[3].show(g("main_reset"), f"{int(cfg['reset_hour']) % 24:02d}:00", mono=True)

    def _session_tiles(self, tiles, stats, goal, summary=False):
        """Четыре плашки сессии (и итога): титанит, этажи и дверь, бои, время. summary — в «Итоге» ещё окна SOS."""
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        elapsed = stats.elapsed()
        progress = launch_config.goal_progress(goal, stats.rooms, stats.titanite, stats.floors, elapsed)
        kind = goal[0] if goal else None

        def goal_parts(this_kind, done_text):
            """Цифра плашки «сделано / цель» и проценты справа — у плашки цели (титанит, этажи)."""
            if kind != this_kind or progress is None:
                return done_text, "", None
            _done, target, share = progress
            return f"{done_text} / {log_lines.group_digits(target)}", f"{share * 100:.0f}%", share

        def goal_share(this_kind):
            """Цели по комнатам и времени: справа «35% из 100» (в саму цифру цель не влезает), полоска — та же."""
            if kind != this_kind or progress is None:
                return "", None
            _done, target, share = progress
            target_text = g("main_minutes").format(n=target) if kind == "time" else log_lines.group_digits(target)
            return g("main_of_target").format(pct=f"{share * 100:.0f}%", target=target_text), share

        value, right, share = goal_parts("titanite", log_lines.group_digits(stats.titanite))
        tiles[0].show(g("main_tile_titanite"), value, mono=True, right=right, progress=share)
        value, right, share = goal_parts("floors", str(stats.floors))
        door = ""
        if stats.door:
            name = get_text(self.lang, f"elem_{stats.door}")
            door = g("main_tile_door").format(door=stats.door.upper() if name == f"elem_{stats.door}"
                                              else theme.plain_text(name))
        tiles[1].show(g("main_tile_floors"), value, mono=True, extra=f"· {door}" if door else "", right=right,
                      progress=share)
        battles = g("main_battles_value").format(wins=stats.rooms, total=stats.battles)
        right, share = goal_share("rooms")
        tiles[2].show(g("main_tile_battles"), battles, right=right, progress=share,
                      extra=g("main_sos_value").format(sos=stats.sos) if summary else "")
        avg = stats.avg_room()
        avg_text = g("main_room_avg").format(s=f"{avg:.0f}") if avg is not None else ""
        right, share = goal_share("time")
        # «комната в среднем 28 с» — мелко в строке подписи (сверка 1.8); там же проценты, если цель — время
        tiles[3].show(g("main_tile_time"), log_lines.clock_text(elapsed), mono=True,
                      extra=avg_text if right else "", right=right or avg_text, progress=share)

    def _show_session(self):
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        if self.link.starting:
            status, color = g("main_status_starting"), C["text_muted"]
        elif self.link.stopping:
            status, color = g("main_status_stopping"), C["text_muted"]
        elif self.open_windows():
            status, color = g("main_status_sos"), C["danger_text"]
        elif self.link.debug_wait:
            status, color = g("main_status_debug"), C["warning"]
        elif self._paused:
            status, color = g("main_status_paused"), C["warning"]
        else:
            status, color = g("main_status_running"), C["success"]
        if self.session_status.cget("text") != " " + status:
            self.session_status.configure(text=" " + status, text_color=color, image=dot(color, 8))
        goal = (self.run_config or self.config)["goal"]
        self._session_tiles(self.session_tiles, self.stats, goal)

    def _show_summary(self):
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        stats = self.stats
        reason = stats.stop_reason and telegram_report.humanize(stats.stop_reason, self.lang) or \
            g(stats.ended_by or log_lines.ENDED_EXIT)
        set_text(self.summary_reason, g("main_summary_reason").format(reason=reason))
        if bool(stats.summary) != self._more_shown:
            self._more_shown = bool(stats.summary)
            if self._more_shown:
                self.summary_more.grid()
            else:
                self.summary_more.grid_remove()
        goal = (self.run_config or self.config)["goal"]
        self._session_tiles(self.summary_tiles, stats, goal, summary=True)

    # ── Кнопки карточки ─────────────────────────────────────────────────────
    def launch_phone(self):
        """«Подключить телефон»: scrcpy в фоне (как старая главная), ответ — через очередь окна."""
        if self.connecting:
            return
        self.connecting = True
        proc = self.scrcpy_process
        if proc and proc.poll() is None:
            proc.terminate()
        self.append_log("[СИСТЕМА] Вызов scrcpy... Открой игру на телефоне и зайди в коридор.\n")
        events = self.controller.events

        def task():
            try:
                from environment import launch_scrcpy
                events.put(("scrcpy", launch_scrcpy(GAME_WINDOW_TITLE)))
            except Exception as e:
                events.put(("scrcpy", e))

        threading.Thread(target=task, name="scrcpy-launch", daemon=True).start()
        self.refresh()

    def _scrcpy_done(self, result):
        self.connecting = False
        if isinstance(result, Exception):
            self.append_log(f"[ОШИБКА] Не удалось запустить scrcpy: {result}\n")
        elif not result:
            self.append_log("[ОШИБКА] Окно scrcpy не появилось или утилита не найдена!\n")
        else:
            if result != "ALREADY_RUNNING":
                self.scrcpy_process = result
            self.set_phone(True)
        self.refresh()

    def start_bot(self):
        """«Начать фарм»: настройки бота — те же, что он прочитает из profile.yml; запуск — ui/bot_link.py."""
        if self.link.running() or not self.phone:
            return
        self.run_config = launch_config.launch_config(launch_config.read_profile()[1])
        self.summary_visible = False
        self.stats.reset()
        if self.link.start(self.lang):
            self.refresh()

    def minimize_window(self):
        """«Свернуть в мини-бар»: мини-бар — шаг 4, пока окно просто сворачивается на панель задач (ваш ответ)."""
        try:
            self.winfo_toplevel().iconify()
        except tk.TclError:
            pass

    def pause_or_continue(self):
        """«Пауза F9»: мягкая пауза (pause.flag) или снять её; после [ПАУЗА ОТЛАДКИ] — «Продолжить» (пустая строка)."""
        if not self.link.running() or self.link.starting:
            return
        if self.link.debug_wait:
            self.link.continue_debug()
            self.append_log("[GUI] Продолжить: бот идёт дальше после паузы отладки.\n")
        else:
            self._paused = self.link.toggle_pause()
        self.refresh()

    def toggle_pause(self):
        self.pause_or_continue()

    def stop_bot(self):
        """«СТОП F10»: бот останавливается сразу (итог сессии в Telegram не уходит), как старая кнопка."""
        if self.link.kill():
            self.close_questions()
            self._paused = self.link.paused()
            self.refresh()

    def hide_summary(self):
        self.summary_visible = False
        self.refresh()

    def show_summary_details(self):
        if self.stats.summary:
            SummaryWindow(self, self.lang, self.stats.summary)

    def open_telegram(self):
        opener = getattr(self.controller, "open_telegram", None)
        if opener:
            opener()

    # ── Телефон, Telegram, профиль ──────────────────────────────────────────
    def set_phone(self, connected):
        """Есть ли окно scrcpy (ui/status.py). Закрыли его во время фарма — бот останавливается (как старое окно)."""
        changed = connected != self.phone
        self.phone = connected
        if not connected and self.link.running():
            self.append_log("[GUI] Окно scrcpy закрыто — останавливаю бота.\n")
            self.link.kill(ended_by=log_lines.ENDED_SCRCPY)
            self.close_questions()
        if changed or not connected:
            self.refresh()

    def set_telegram(self, on):
        if on != self.telegram_on:
            self.telegram_on = on
            self.refresh()

    def _mtime(self):
        try:
            return os.path.getmtime(launch_config.PROFILE)
        except OSError:
            return None

    def _reload_profile(self):
        self.profile_exists, profile = launch_config.read_profile()
        self.config = launch_config.launch_config(profile)

    def _tick(self):
        """Раз в секунду: время сессии, пауза (её мог поставить и сам бот), изменения profile.yml."""
        self._tick_id = None
        if self._closing:
            return
        try:
            changed = False
            mtime = self._mtime()
            if mtime != self._profile_mtime:
                self._profile_mtime = mtime
                self._reload_profile()
                changed = True
            paused = self.link.paused()
            if paused != self._paused:
                self._paused = paused
                changed = True
            if changed or self.left_mode == "session":
                self.refresh()
        finally:
            if not self._closing:
                self._tick_id = self.after(TICK_MS, self._tick)

    # ── События из очереди окна ─────────────────────────────────────────────
    def on_event(self, kind, value):
        if kind == "bot_line":
            self.add_bot_line(value)
        elif kind == "bot_event":
            self._bot_event(*value)
        elif kind == "bot_started":
            if value == self.link.run_id:
                self.stats.start()
                self.refresh()
        elif kind == "bot_exit":
            self._bot_exited(value)
        elif kind == "scrcpy":
            self._scrcpy_done(value)
        elif kind == "tg_answer":
            self._telegram_answer(*value)
        elif kind == "tg_failed":
            self._telegram_failed(value)

    def _bot_exited(self, run_id):
        if not self.link.exited(run_id):
            return
        self.append_log("[СИСТЕМА] Процесс бота завершен.\n")
        self.close_questions()
        if self.stats.started is not None:
            self.stats.finish(self.link.ended_by or log_lines.ENDED_EXIT)
            self.summary_visible = True
        self._paused = self.link.paused()
        self.refresh()

    def _bot_event(self, kind, data, asked_at):
        if kind == bot_link.SOS_CLOSE:
            # Вы не ответили — бот решил сам: окна закрываются, ответы из них боту уже не уходят (как старое окно)
            self.link.sos_closed()
            self.close_questions()
        elif kind == bot_link.DEBUG_PAUSE:
            self.link.debug_wait = True
        elif kind == bot_link.SOS:
            self._open_sos(data, asked_at)
        elif kind == bot_link.NO_TEAM:
            self._open_no_team(data, asked_at)
        elif kind == bot_link.TEST_OK:
            self._open_test(data, asked_at)
        self.refresh()

    # ── Окна вмешательства ──────────────────────────────────────────────────
    def open_windows(self):
        return [q for q in self.questions if q.window is not None and not q.window.closed]

    def _run_settings(self):
        cfg = self.run_config or self.config
        return cfg["settings"].panic_hp, cfg["sos_timeout"]

    def _telegram(self, question, kind, titans, info=None, is_manual=False, can_rollback=True, only_telegram=False):
        """Вопрос в Telegram (с повторами). only_telegram — окна в программе нет: не ушло — окно откроется здесь."""
        events = self.controller.events
        failed = (lambda: events.put(("tg_failed", question.id))) if only_telegram else None
        question.telegram = TelegramQuestion(
            kind, titans, self.lang, lambda decision: events.put(("tg_answer", (question.id, decision))),
            lambda text: events.put(("log", text)), info=info, is_manual=is_manual, can_rollback=can_rollback,
            on_failed=failed).start()

    def _open_sos(self, data, asked_at):
        info = telegram_report.read_sos_info(data_paths.sos_info_file())
        titans = data.get("titans") or {}
        question = Question(bot_link.SOS, self.link.epoch, titans, info.get("room"))
        panic, timeout = self._run_settings()
        question.window = sos_dialogs.sos_window(
            self, self.lang, titans, data.get("is_manual", False), info, panic, timeout, asked_at,
            on_answer=lambda command: self._answer(question, command), on_close=lambda: self._ask_stop(question),
            on_rollback=lambda: self._pick(question, "ROLLBACK:"))
        self.questions.append(question)
        self._telegram(question, TG_SOS, titans, info, is_manual=data.get("is_manual", False))

    def _open_no_team(self, data, asked_at):
        question = Question(bot_link.NO_TEAM, self.link.epoch, room=data.get("room"))
        _panic, timeout = self._run_settings()
        question.window = sos_dialogs.no_team_window(
            self, self.lang, data, timeout, asked_at, on_answer=lambda command: self._answer(question, command),
            on_close=lambda: self._ask_stop(question), on_new_pack=lambda: self._pick(question, "NEW_PACK:"))
        self.questions.append(question)
        info = telegram_report.read_sos_info(data_paths.sos_info_file())
        self._telegram(question, TG_SOS, {}, info, can_rollback=False)

    def _open_test(self, data, asked_at):
        titans = data.get("titans") or {}
        info = read_recent_info(data_paths.sos_info_file(), TEST_INFO_MAX_AGE_S)
        question = Question(bot_link.TEST_OK, self.link.epoch, titans, info.get("room"))
        question.info, question.asked_at = info, asked_at
        self.questions.append(question)
        if data.get("source") == "telegram" and telegram_ready():
            # Пак прислали из Telegram — и спрашиваем там же (как старое окно). Не ушло — спросим здесь
            self._telegram(question, TG_TEST, titans, only_telegram=True)
            return
        self._test_window(question)

    def _test_window(self, question):
        panic, timeout = self._run_settings()
        question.window = sos_dialogs.test_window(
            self, self.lang, question.titans, question.info, panic, timeout, question.asked_at,
            on_answer=lambda command: self._answer(question, command), on_close=lambda: self._ask_stop(question),
            on_other=lambda: self._pick(question, "ROLLBACK:"))

    def _telegram_failed(self, question_id):
        """Вопрос «Пак справился» ушёл только в Telegram, но так и не отправился — спрашиваем в окне программы."""
        question = next((q for q in self.questions if q.id == question_id), None)
        if question is not None and question.window is None and question.kind == bot_link.TEST_OK:
            self._test_window(question)
            self.refresh()

    def _pick(self, question, prefix):
        """«Откатить бой», «Попробовать другой», «Собрать новый пак» — окно «Собери состав». Закрыли его без выбора —
        окно вмешательства возвращается (ошибка 3.2: раньше крестик этого окна останавливал бота)."""
        if question.window is None or question.window.closed or question.picker is not None:
            return
        question.window.hide()
        rollback = prefix.startswith("ROLLBACK")

        def cancelled():
            question.picker = None
            if question.window is not None:
                question.window.show()

        def picked(team):
            question.picker = None
            if question.window is not None:
                question.window.close_silently()
            self._answer(question, prefix + ",".join(team))

        selected = list(question.titans) if rollback else []
        question.picker = TitanPicker(
            self, self.lang, on_apply=picked, on_cancel=cancelled, room=question.room, selected=selected,
            apply_text=get_text(self.lang, "pick_rollback" if rollback else "pick_apply"),
            apply_kind="blue" if rollback else "save")

    def _answer(self, question, command, source="GUI"):
        """Ответ боту на вопрос (окно или Telegram): одна строка в stdin, если вопрос не устарел."""
        if question not in self.questions:
            return
        self.questions.remove(question)
        question.close()
        if command == "STOP":
            sent = self.link.request_stop(question.epoch)
        else:
            sent = self.link.answer(command, question.epoch)
        if sent:  # устаревший ответ link не отправит и сам напишет почему
            self.append_log(f"[GUI] Ответ боту: {command}\n" if source == "GUI" else
                            f"[TELEGRAM] Ответ из Telegram: {command}\n")
        self.refresh()

    def _ask_stop(self, question):
        """Крестик окна вмешательства: «Остановить бота?» (ваш ответ 22.10.2026), а не остановка сразу."""
        if question.confirm is not None and not question.confirm.done:
            question.confirm.lift()
            return
        lang = self.lang
        test = question.kind == bot_link.TEST_OK
        text = get_text(lang, "sosw_stop_text_test" if test else "sosw_stop_text")

        def confirmed():
            question.confirm = None
            if test:
                # На вопрос «Пак справился» бот команду STOP не понимает — останавливаем, как «СТОП»
                self.questions.remove(question)
                question.close()
                self.stop_bot()
            else:
                self._answer(question, "STOP")

        def cancelled():
            question.confirm = None

        question.confirm = ConfirmDialog(question.window, get_text(lang, "close_bot_title"), text,
                                         get_text(lang, "sosw_stop"), on_confirm=confirmed, on_cancel=cancelled,
                                         kind="warning", lang=lang, confirm_kind="danger_solid",
                                         confirm_icon="square-filled")

    def _telegram_answer(self, question_id, decision):
        question = next((q for q in self.questions if q.id == question_id), None)
        if question is None:
            return
        if decision.startswith("rb_custom:"):
            command = "ROLLBACK_TG:" + decision.split(":", 1)[1]
        else:
            command = TG_COMMANDS.get(decision)
        if command is None:
            return
        self._answer(question, command, source="TELEGRAM")

    def close_questions(self):
        """Закрыть все окна вмешательства и вопросы в Telegram без ответа."""
        questions, self.questions = self.questions, []
        for question in questions:
            question.close()

    # ── Журнал: строки ──────────────────────────────────────────────────────
    def append_log(self, text):
        """Строка самого окна (и старых вкладок): со временем в начале, как у бота."""
        for raw in str(text).split("\n"):
            raw = raw.rstrip()
            if raw.strip():
                self._add_line(f"{stamp()} {raw}")

    def add_bot_line(self, line):
        line = line.rstrip("\r\n")
        if not line.strip():
            return  # пустые строки бота (print("\n...")) в журнале не нужны
        self.stats.feed(line)
        self._add_line(line)

    def _add_line(self, line):
        category, color, (time_end, span), counted = self.classifier.classify(line)
        entry = (line, category, color, time_end, span)
        self.lines.append(entry)
        if len(self.lines) > MAX_LINES:
            del self.lines[:len(self.lines) - MAX_LINES]
        if counted:
            self.errors += 1
        if self.filter in (ALL, category):
            self._pending.append(entry)
        if self._flush_id is None and not self._closing:
            self._flush_id = self.after_idle(self.flush_log)

    def flush_log(self):
        """Показать накопленные строки разом (окно разбирает очередь раз в 100 мс)."""
        if self._flush_id is not None:
            try:
                self.after_cancel(self._flush_id)
            except tk.TclError:
                pass
            self._flush_id = None
        self._show_errors()
        if not self._pending:
            return
        pending, self._pending = self._pending, []
        box = self.log_box
        at_end = box.yview()[1] >= 0.999
        for entry in pending:
            self._insert(entry)
        self._shown += len(pending)
        if self._shown > MAX_SHOWN:
            extra = self._shown - MAX_SHOWN
            box.delete("1.0", f"{extra + 1}.0")
            self._shown = MAX_SHOWN
        if at_end:
            box.see("end")
        self._update_empty()

    def _insert(self, entry):
        """Строка журнала. Перенос — перед строкой, а не после: иначе под последней строкой пустая строка,
        и при прокрутке вниз внизу журнала остаётся пустое место."""
        line, _category, color, time_end, span = entry
        box = self.log_box
        if box.compare("end-1c", "!=", "1.0"):
            box.insert("end", "\n", ("line",))
        if time_end:
            box.insert("end", line[:time_end], ("time", "line"))
        pos = time_end
        if span:
            if span[0] > pos:
                box.insert("end", line[pos:span[0]], ("line",))
            box.insert("end", line[span[0]:span[1]], (f"c_{color}", "line"))
            pos = span[1]
        box.insert("end", line[pos:], ("line",))

    def _render_log(self):
        """Заново показать строки выбранной таблетки (последние MAX_SHOWN)."""
        self._pending = []
        box = self.log_box
        box.delete("1.0", "end")
        shown = [e for e in self.lines if self.filter in (ALL, e[1])][-MAX_SHOWN:]
        for entry in shown:
            self._insert(entry)
        self._shown = len(shown)
        box.see("end")
        self._show_errors()
        self._update_empty()

    def _show_errors(self):
        """Счётчик «Ошибки (N)» — только когда число поменялось (перестройка таблетки — лишняя работа окна)."""
        if self.errors != self._errors_shown:
            self._errors_shown = self.errors
            self.chips[ERRORS].set_count(self.errors)

    def _update_empty(self):
        """Пустой журнал (или пустая таблетка) — подсказка вместо строк, как в макете первого запуска."""
        empty = self._shown == 0
        if empty:
            first = self.filter == ALL
            set_text(self.empty_title, get_text(self.lang, "log_empty_title" if first else "log_empty_filter_title"))
            set_text(self.empty_text, get_text(self.lang, "log_empty_text" if first else "log_empty_filter_text"))
        if empty != self._empty_shown:
            self._empty_shown = empty
            if empty:
                self.empty.grid()
            else:
                self.empty.grid_remove()

    def set_filter(self, key):
        if key == self.filter:
            return
        self.filter = key
        for name, chip in self.chips.items():
            chip.set_selected(name == key)
        self._render_log()
        try:
            ui_settings.save(self.settings_path, log_filter=key)
        except OSError:
            pass

    def ask_clear_log(self):
        """«Очистить» — с подтверждением (design/README.md: опасные действия только с подтверждением)."""
        if self._clear_dialog is not None and not self._clear_dialog.done:
            self._clear_dialog.lift()
            return
        lang = self.lang
        self._clear_dialog = ConfirmDialog(self, get_text(lang, "log_clear_title"), get_text(lang, "log_clear_text"),
                                           get_text(lang, "log_clear_ok"), on_confirm=self.clear_log, kind="danger",
                                           lang=lang)

    def clear_log(self):
        self.lines = []
        self.errors = 0
        self.classifier = log_lines.Classifier()
        self._render_log()

    def log_text(self):
        """Все строки журнала (что помнит окно) — для «Сохранить лог»."""
        return "\n".join(entry[0] for entry in self.lines) + "\n"

    def export_log(self):
        """«Сохранить лог»: как старая главная — файл gui_log_<время>.txt, по умолчанию рядом с логами бота."""
        default_name = f"gui_log_{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}.txt"
        filepath = ctk.filedialog.asksaveasfilename(
            initialdir=os.path.abspath(data_paths.logs_dir()), initialfile=default_name, defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not filepath:
            return None
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=== ЛОГ ТЕРМИНАЛА (GUI) ===\n")
                f.write(self.log_text())
        except OSError as e:
            self.append_log(f"[ОШИБКА] Не удалось сохранить лог: {e}\n")
            return None
        self.append_log(f"[СИСТЕМА] Лог терминала сохранен: {filepath}\n")
        return filepath

    def send_log_to_author(self):
        filepath = self.export_log()
        if not filepath:
            self.append_log("[СИСТЕМА] Сохранение лога отменено.\n")
            return
        self.append_log("[СИСТЕМА] Открываю почтовый клиент ОС...\n")
        body = ("Привет, Platon! Вот логи сессии.%0A%0A"
                "(Пожалуйста, прикрепите файлы gui_log_...txt и battle_log.csv к этому письму)")
        webbrowser.open(f"mailto:Petrunin.platon@gmail.com?subject=HeroWars Bot Log Report&body={body}")

    # ── Закрытие окна программы ─────────────────────────────────────────────
    def shutdown_processes(self):
        """Окно закрывается: свои таймеры, окна SOS, Telegram, бот и scrcpy — как старое окно (shutdown_processes)."""
        self._closing = True
        for after_id in (self._tick_id, self._flush_id):
            if after_id:
                try:
                    self.after_cancel(after_id)
                except tk.TclError:
                    pass
        self._tick_id = self._flush_id = None
        self.close_questions()
        self.link.close()
        bot_link.cleanup_process(self.scrcpy_process)
