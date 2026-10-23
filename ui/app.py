"""Новое окно программы (задача 15, шаг 2 — каркас).

Запуск: start.bat или python gui.py (обычный запуск). Старое окно на всякий случай — start_old.bat или python gui.py --old-ui.

Каркас — по design/README.md («Каркас окна»): слева полоска 64 px (логотип, 6 разделов с подсказками, Telegram, язык),
сверху шапка 56 px (название раздела, плашка телефона, три кнопки), ниже — страница. С шага 3 главная новая
(ui/main_page.py), с шага 5а — «Мастер правил» (ui/rules_page.py), с шага 6 — «Аналитика» (ui/analytics_page.py)
и «Статистика» (ui/stats_page.py), с шага 7 — «О программе» (ui/about_page.py), остальные страницы пока — старые вкладки, их заменят следующие шаги. Для них окно — прежний
controller: current_lang, frames, select_frame; главная для них — frames["dash"] с append_log().

Связь с ботом не меняется (протокол тот же): бота запускает, читает и останавливает главная через ui/bot_link.py.
Кнопки шапки и F9/F10 вызывают её же: та же пауза (pause.flag), тот же стоп, те же строки в журнале.

Чтобы окно не зависало и закрывалось крестиком (правила — в начале ui/widgets.py):
- всё, что ждёт (окно scrcpy, клавиши, profile.yml, кнопки шапки, строки бота, Telegram), работает в фоновых потоках;
  в окно — через очередь self.events, её окно разбирает раз в 100 мс (after);
- крестик: если бот работает — вопрос «Остановить бота?»; потом остановить потоки и свои after, спрятать окно,
  остановить бота и scrcpy (как старое окно) и закрыть окно — mainloop кончается, процесс выходит сам;
- сторож ui/freeze_guard.py пишет bot_data/debug/ui_freeze_*.txt, если окно не отвечает 5 с.

Мини-бар (шаг 4, ui/hud.py): бот запустился (или «Свернуть в мини-бар») — окно сворачивается на панель задач,
под игрой появляется мини-бар (ваш ответ 22.10.2026). «Развернуть» в мини-баре или кнопка окна на панели задач —
окно снова целиком, мини-бар прячется. Бот остановился — окно разворачивается само (там «Итог сессии»).
Пока окно в мини-баре (mini), окна SOS и «Собери состав» показываются сами по себе над игрой (ui/widgets.py).
"""
import os
import queue
import sys
import tkinter as tk

import customtkinter as ctk
from customtkinter.windows.widgets.core_widget_classes import DropdownMenu

from config import APP_VERSION, GAME_WINDOW_TITLE, PAUSE_FLAG_FILE
from i18n import LANGUAGES, get_text
from ui import hud_place, phone, theme, ui_settings
from ui.about_page import AboutPage
from ui.analytics_page import AnalyticsPage
from ui.freeze_guard import FreezeGuard
from ui.guide_tab import GuideFrame
from ui.hotkeys import HotkeyWatcher
from ui.hud import Hud
from ui.icons import dot, icon, icon_with_dot
from ui.main_page import MainPage
from ui.rules_page import RulesPage
from ui.stats_page import StatsPage
from ui.status import StatusWatcher
from ui.widgets import Button, ConfirmDialog, IconButton, Toast, Tooltip
from ui.window_fit import fit_window, work_area

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

# Разделы: имя (как в старом окне), старая вкладка, иконка, подсказка в полоске, заголовок в шапке
PAGES = (
    ("dash", MainPage, "house", "btn_main", "page_title_main"),
    ("rules", RulesPage, "sliders-vertical", "btn_rules", "btn_rules"),
    ("analytics", AnalyticsPage, "activity", "btn_analytics", "btn_analytics"),
    ("stats", StatsPage, "chart-no-axes-column", "btn_stats", "page_title_stats"),
    ("guide", GuideFrame, "book-open", "btn_guide", "btn_guide"),
    ("about", AboutPage, "info", "btn_about", "btn_about"),
)
DRAIN_MS = 100          # как часто окно забирает события из очереди
RESTART_PAUSE_MS = 1000  # перезапуск scrcpy: пауза между остановкой и запуском (как в старом окне)


class DotIconButton(IconButton):
    """Кнопка полоски с точкой состояния у иконки (Telegram: зелёная — включён, серая — не настроен)."""

    def __init__(self, master, icon_name, dot_color, **kwargs):
        self._dot_color = dot_color
        super().__init__(master, icon_name, kind="nav", **kwargs)

    def _icon_image(self):
        color = C["blue_text"] if self._active else C["text_secondary"]
        return icon_with_dot(self._icon_name, color, self._icon_size, self._dot_color)

    def set_dot(self, color):
        if color != self._dot_color:
            self._dot_color = color
            self.configure(image=self._icon_image())


class DevicePlate(ctk.CTkFrame):
    """Плашка в шапке: «● HeroWarsBot_Arena подключено» (зелёная) или «● Ожидание телефона…» (красная).
    Подключено — есть окно scrcpy (ui/status.py)."""

    def __init__(self, master):
        super().__init__(master, fg_color=C["bg_surface"], border_width=1, border_color=C["border"],
                         corner_radius=S["radius_control"])
        self.connected = None
        self._dot = ctk.CTkLabel(self, text="", width=8, height=24)
        self._dot.pack(side="left", padx=(12, 8), pady=5)
        self._name = ctk.CTkLabel(self, text=GAME_WINDOW_TITLE, font=F["mono"], text_color=C["text"], height=24)
        self._status = ctk.CTkLabel(self, text="", font=F["text"], height=24)
        self._status.pack(side="left", padx=(0, 12), pady=5)

    def show(self, connected, lang):
        self.connected = connected
        self._dot.configure(image=dot(C["success"] if connected else C["danger"], 8))
        if connected:
            self._name.pack(side="left", padx=(0, 8), pady=5, before=self._status)
            self._status.configure(text=get_text(lang, "hdr_connected"), text_color=C["success"])
        else:
            self._name.pack_forget()
            self._status.configure(text=get_text(lang, "hdr_waiting"), text_color=C["danger_text"])


def find_game_window():
    """Окно игры для мини-бара (hud_place.GameWindow) или None. Вне Windows окна scrcpy нет."""
    if not hud_place.windows_available():
        return None
    return hud_place.win_find_game(GAME_WINDOW_TITLE)


class App(ctk.CTk):
    def __init__(self, settings_path=None, status_watcher=None, hotkey_watcher=None, game_locator=None):
        super().__init__(fg_color=C["bg_primary"])
        self.settings_path = settings_path
        saved = ui_settings.load(settings_path).get("language")
        self.current_lang = saved if saved in LANGUAGES else "RU"
        self.events = queue.Queue()      # события из фоновых потоков: ("log", текст), ("phone", да/нет), ...
        self.page = None
        self.phone_connected = False
        self.telegram_on = False
        self._closing = False
        self._close_dialog = None
        self._timers = {}                # свои after, которые надо отменить при закрытии
        self.mini = False                # окно свёрнуто в мини-бар (шаг 4)
        self.hud = None
        self.game_locator = game_locator or find_game_window

        self.title(get_text(self.current_lang, "app_title"))
        width, height, min_w, min_h, x, y = fit_window(work_area(self), self._get_window_scaling())
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min_w, min_h)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Map>", self._on_map, add="+")

        # Как старое окно: пауза, оставшаяся от прошлого запуска, не должна держать бота
        if os.path.exists(PAUSE_FLAG_FILE):
            os.remove(PAUSE_FLAG_FILE)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self._build_rail()
        tk.Frame(self, width=1, bg=C["border"]).grid(row=0, column=1, sticky="ns")
        main = ctk.CTkFrame(self, corner_radius=0, fg_color=C["bg_primary"])
        main.grid(row=0, column=2, sticky="nsew")
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)
        self._build_header(main)
        tk.Frame(main, height=1, bg=C["border"]).grid(row=1, column=0, sticky="ew")
        self.content = ctk.CTkFrame(main, corner_radius=0, fg_color=C["bg_primary"])
        self.content.grid(row=2, column=0, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.frames = {name: page(self.content, self) for name, page, *_ in PAGES}
        self.plate.show(False, self.current_lang)
        self.select_frame("dash")
        self.set_language(self.current_lang, force=True)

        self.status = (status_watcher or StatusWatcher(self.events, GAME_WINDOW_TITLE)).start()
        self.hotkeys = (hotkey_watcher or HotkeyWatcher(self.events, GAME_WINDOW_TITLE)).start()
        self._timers["drain"] = self.after(DRAIN_MS, self._drain)
        self.guard = FreezeGuard(self).start()

    # ── Полоска слева ───────────────────────────────────────────────────────
    def _build_rail(self):
        rail = ctk.CTkFrame(self, width=S["rail_width"], corner_radius=0, fg_color=C["bg_primary"])
        rail.grid(row=0, column=0, sticky="ns")
        rail.pack_propagate(False)

        logo = ctk.CTkFrame(rail, width=40, height=40, corner_radius=10, fg_color=C["bg_elevated"], border_width=1,
                            border_color=C["border"])
        logo.pack(pady=(12, 0))
        logo.pack_propagate(False)
        mark = ctk.CTkLabel(logo, text="", image=icon("shield-check", C["green"], 22))
        mark.place(relx=0.5, rely=0.5, anchor="center")
        tip = Tooltip(logo, lambda: get_text(self.current_lang, "app_title"), side="right")
        tip.attach(mark)
        ctk.CTkLabel(rail, text=f"v{APP_VERSION}", font=F["version"], text_color=C["text_muted"], height=14).pack(
            pady=(6, 0))
        tk.Frame(rail, width=28, height=1, bg=C["border"]).pack(pady=(10, 10))

        self.nav = {}
        for name, _page, icon_name, tip_key, _title_key in PAGES:
            button = IconButton(rail, icon_name, kind="nav", tooltip_side="right",
                                tooltip=lambda k=tip_key: theme.plain_text(get_text(self.current_lang, k)),
                                command=lambda n=name: self.select_frame(n))
            button.pack(pady=(0, 6))
            self.nav[name] = button

        bottom = ctk.CTkFrame(rail, fg_color="transparent")
        # Низ кнопки языка — вровень с низом страницы (журнала главной): тот же отступ, что у содержимого
        bottom.pack(side="bottom", pady=(0, S["content_padding"]))
        self.tg_button = DotIconButton(bottom, "send", C["text_muted"], icon_size=18, tooltip_side="right",
                                       tooltip=self._telegram_tip, command=self.open_telegram)
        self.tg_button.pack(pady=(0, 8))
        self.lang_button = Button(bottom, self.current_lang, kind="secondary", icon_name="chevron-down", icon_size=10,
                                  height=34, pad_x=4, compound="right", fg_color=C["bg_surface"],
                                  hover_color=T["hover_surface"], font=F["label_bold"], command=self.open_language_menu)
        self.lang_button.configure(width=44)
        self.lang_button.pack()
        Tooltip(self.lang_button, lambda: f'{get_text(self.current_lang, "nav_language")}: '
                                          f'{LANGUAGES[self.current_lang]}', side="right")
        self.lang_menu = DropdownMenu(self, values=list(LANGUAGES.values()), command=self._language_chosen,
                                      fg_color=C["bg_elevated"], hover_color=C["blue_button"], text_color=C["text"],
                                      font=F["text"], min_character_width=12)

    def _telegram_tip(self):
        return get_text(self.current_lang, "nav_tg_on" if self.telegram_on else "nav_tg_off")

    # ── Шапка ───────────────────────────────────────────────────────────────
    def _build_header(self, main):
        header = ctk.CTkFrame(main, height=S["header_height"], corner_radius=0, fg_color=C["bg_primary"])
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_rowconfigure(0, weight=1)
        header.grid_columnconfigure(0, weight=1)
        pad = S["content_padding"]
        self.title_label = ctk.CTkLabel(header, text="", font=F["page_title"], text_color=C["text"], anchor="w")
        self.title_label.grid(row=0, column=0, sticky="w", padx=(pad, 16))
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=(0, pad))
        self.plate = DevicePlate(right)
        self.plate.pack(side="left")
        self.header_buttons = {}
        for name, tip_key, command in (("moon", "hdr_tip_sleep", self.sleep_phone),
                                       ("refresh-cw", "hdr_tip_restart", self.restart_scrcpy),
                                       ("maximize-2", "hdr_tip_reset_size", self.reset_window_size)):
            button = IconButton(right, name, icon_size=16, command=command,
                                tooltip=lambda k=tip_key: get_text(self.current_lang, k))
            button.pack(side="left", padx=(8, 0))
            self.header_buttons[name] = button

    # ── Страницы и язык ─────────────────────────────────────────────────────
    def select_frame(self, frame_name):
        """Открыть раздел. Уходим из «Мастера правил» с несохранёнными изменениями — сначала «Сохранить изменения?»."""
        if self.page == "rules" and frame_name != "rules":
            self.frames["rules"].ask_leave(lambda: self._show_frame(frame_name))
            return
        self._show_frame(frame_name)

    def _show_frame(self, frame_name):
        if frame_name in ("stats", "about"):
            self.frames[frame_name].refresh_data()   # цифры статистики и состояние компонентов — при каждом показе
        for frame in self.frames.values():
            frame.grid_forget()
        frame = self.frames[frame_name]
        pad = 0 if getattr(frame, "full_bleed", False) else S["content_padding"]  # мастер правил: футер во всю ширину
        frame.grid(row=0, column=0, sticky="nsew", padx=pad, pady=pad)
        self.page = frame_name
        for name, button in self.nav.items():
            button.set_active(name == frame_name)
        self._show_title()

    def _show_title(self):
        title_key = next(title for name, _p, _i, _t, title in PAGES if name == self.page)
        self.title_label.configure(text=theme.plain_text(get_text(self.current_lang, title_key)))

    def open_language_menu(self):
        button = self.lang_button
        self.lang_menu.open(button.winfo_rootx() + button.winfo_width() + 8,
                            button.winfo_rooty() + button.winfo_height() - self.lang_menu.winfo_reqheight())

    def _language_chosen(self, name):
        code = next((code for code, native in LANGUAGES.items() if native == name), None)
        if code:
            self.set_language(code)
            try:
                ui_settings.save(self.settings_path, language=code)
            except OSError as e:
                self.frames["dash"].append_log(f"[ОШИБКА] Не удалось запомнить язык окна: {e}\n")

    def set_language(self, lang, force=False):
        if lang == self.current_lang and not force:
            return
        self.current_lang = lang
        if not force:  # при запуске журнал пустой: язык окна не новость (макет первого запуска)
            self.frames["dash"].append_log(f"[GUI] Язык интерфейса изменен: {LANGUAGES[lang]} ({lang})\n")
        self.title(get_text(lang, "app_title"))
        self.lang_button.configure(text=lang)
        self._show_title()
        self.plate.show(self.phone_connected, lang)
        for frame in self.frames.values():
            if hasattr(frame, "update_language"):
                frame.update_language(lang)
        if self.hud is not None:
            self.hud.set_language(lang)

    # ── События из фоновых потоков ──────────────────────────────────────────
    def log_later(self, text):
        """Строка в журнал из любого потока: окно покажет её при следующем разборе очереди."""
        self.events.put(("log", text))

    def _drain(self):
        self._timers.pop("drain", None)
        if self._closing:
            return
        try:
            for _ in range(200):
                try:
                    kind, value = self.events.get_nowait()
                except queue.Empty:
                    break
                self._handle_event(kind, value)
            self.frames["dash"].flush_log()
            self.frames["rules"].update_bot_state(self.bot_running())
        finally:
            if not self._closing:
                self._timers["drain"] = self.after(DRAIN_MS, self._drain)

    def _handle_event(self, kind, value):
        dash = self.frames["dash"]
        if kind == "log":
            dash.append_log(value)
        elif kind == "phone":
            self.phone_connected = value
            self.plate.show(value, self.current_lang)
            dash.set_phone(value)
        elif kind == "telegram":
            self.telegram_on = value
            self.tg_button.set_dot(C["success"] if value else C["text_muted"])
            dash.set_telegram(value)
        elif kind == "hotkey":
            self.on_hotkey(value)
        else:  # строки и события бота, ответ scrcpy, ответ из Telegram — главной
            dash.on_event(kind, value)

    # ── Кнопки шапки, Telegram, F9/F10 ──────────────────────────────────────
    def sleep_phone(self):
        phone.in_background(phone.sleep_screen, self.log_later)

    def reset_window_size(self):
        phone.in_background(phone.reset_window_size, self.log_later)

    def restart_scrcpy(self):
        """Как «Перезапуск» старой главной, но пауза между остановкой и запуском — через after, окно не замирает."""
        dash = self.frames["dash"]
        dash.append_log("[ADB] Перезапуск scrcpy...\n")
        proc = dash.scrcpy_process
        if proc and proc.poll() is None:
            proc.terminate()
        if "restart" in self._timers:
            self.after_cancel(self._timers.pop("restart"))
        self._timers["restart"] = self.after(RESTART_PAUSE_MS, self._launch_phone)

    def _launch_phone(self):
        self._timers.pop("restart", None)
        self.frames["dash"].launch_phone()

    def open_telegram(self):
        """Настройки Telegram (ответ пользователя 22.10.2026). Пока — старое окно из «Мастера правил»:
        сохраняется оно там же, кнопкой «Сохранить настройки» (новое окно Telegram — шаг 5б)."""
        self.select_frame("rules")
        self.frames["rules"].open_tg_dialog()

    def bot_running(self):
        return self.frames["dash"].bot_running()

    def on_hotkey(self, name):
        """F9 — как кнопка «Пауза» главной (мягкая пауза, снять паузу, «Продолжить» после паузы отладки),
        F10 — как «СТОП»."""
        dash = self.frames["dash"]
        if not self.bot_running():
            dash.append_log(f"[GUI] Нажата {name}, но бот не запущен.\n")
            return
        dash.append_log(f"[GUI] Нажата {name}.\n")
        if name == "F9":
            dash.pause_or_continue()
        elif name == "F10":
            dash.stop_bot()

    # ── Мини-бар (шаг 4) ────────────────────────────────────────────────────
    def enter_mini(self):
        """Свернуть окно в мини-бар под игрой. Только пока бот работает: без него мини-бару нечего показывать."""
        if self._closing or self.mini or not self.bot_running():
            return
        if self.hud is None:
            self.hud = Hud(self, self.current_lang, self.game_locator, self.hud_command)
        self.mini = True
        self.update_hud()
        self.hud.show()
        try:
            if sys.platform == "win32":
                self.iconify()     # кнопка окна остаётся на панели задач
            else:
                self.withdraw()    # в Linux без диспетчера окон (виртуальный экран тестов) iconify ждёт его 2 с впустую
        except tk.TclError:
            pass
        self.frames["dash"].raise_questions()  # открытые окна SOS не прячутся вместе с окном программы

    def leave_mini(self, restore=True):
        """Окно снова целиком, мини-бар прячется. restore=False — окно уже развернули (кнопка на панели задач)."""
        if not self.mini:
            return
        self.mini = False
        if self.hud is not None:
            self.hud.hide()
        if restore and not self._closing:
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except tk.TclError:
                pass

    def _on_map(self, event):
        """Окно развернули с панели задач, пока оно было в мини-баре, — мини-бар больше не нужен."""
        if event.widget is self and self.mini and self.state() == "normal":
            self.leave_mini(restore=False)

    def update_hud(self):
        if self.mini and self.hud is not None:
            self.hud.render(self.frames["dash"].hud_view())

    def hud_command(self, name):
        """Кнопки мини-бара — те же действия, что кнопки главной и шапки."""
        dash = self.frames["dash"]
        if name == "pause":
            dash.pause_or_continue()
        elif name == "sos":
            dash.raise_questions(open_missing=True)
        elif name == "stop":
            dash.stop_bot()
        elif name == "sleep":
            self.sleep_phone()
        elif name == "expand":
            self.leave_mini()

    def dialog_area(self):
        """По центру чего ставить окна SOS, пока окно программы в мини-баре: картинка игры (или None)."""
        return self.hud.game_area() if self.hud is not None else None

    # ── Закрытие ────────────────────────────────────────────────────────────
    def on_close(self):
        """Крестик окна. Бот работает — сначала вопрос (ответ пользователя 22.10.2026), иначе закрываем сразу."""
        if self._closing:
            return
        if self.frames["rules"].dirty():
            # Несохранённые настройки мастера правил — сначала «Сохранить изменения?» (ваш ответ 22.10.2026)
            if self.state() != "normal":
                self.deiconify()
            self.frames["rules"].ask_leave(self._close_after_rules)
            return
        self._close_after_rules()

    def _close_after_rules(self):
        if self._closing:
            return
        if not self.bot_running():
            self.shutdown()
            return
        if self._close_dialog is not None and self._close_dialog.winfo_exists():
            self._close_dialog.lift()
            return
        if self.state() != "normal":
            self.deiconify()  # окно подтверждения привязано к главному: у свёрнутого окна его не видно
        lang = self.current_lang
        self._close_dialog = ConfirmDialog(self, get_text(lang, "close_bot_title"), get_text(lang, "close_bot_text"),
                                           get_text(lang, "close_bot_ok"), on_confirm=self.shutdown, kind="warning",
                                           lang=lang, confirm_kind="danger_solid", confirm_icon="square-filled")

    def shutdown(self):
        """Остановить всё своё и закрыть окно: процесс программы после этого выходит сам."""
        if self._closing:
            return
        self._closing = True
        self.guard.stop()
        self.status.stop()
        self.hotkeys.stop()
        for after_id in self._timers.values():
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        self._timers.clear()
        Toast.close_all(self)
        if self.hud is not None:
            self.hud.destroy()
        try:
            self.withdraw()  # окно пропадает сразу; остановка бота и scrcpy — до 2 с на каждый
        except tk.TclError:
            pass
        try:
            self.frames["dash"].shutdown_processes()
        except Exception as e:
            print(f"[GUI] Не удалось остановить бота или scrcpy: {e}", file=sys.__stderr__)
        self.destroy()


def run():
    ctk.set_appearance_mode("Dark")
    app = App()
    app.mainloop()
