"""Окна вмешательства нового окна (задача 15, шаг 3). Макетов нет — нарисованы в стиле макетов из общих виджетов
(design/screenshots/08_states.png: значок в цветной подложке, заголовок, текст, кнопки справа).

- «Требуется вмешательство» (плохой бой, [SOS_TRIGGER] {"titans": ...}): «Пройти руками» → MANUAL,
  «Игнорировать» → IGNORE, «Откатить бой» → окно «Собери состав» → ROLLBACK:титаны. Бой шёл вручную (Ангус) —
  вместо «Откатить бой» «Остановить бота» → STOP.
- «Нет подходящего пака» (NO_VALID_TEAM): «Пройти руками» → MANUAL, «Собрать новый пак» → «Собери состав» →
  NEW_PACK:титаны, «Остановить бота» → STOP (ошибка 3.1 старого окна: «Игнорировать» слало ignore, которого бот не знает).
- «Пак справился» (TEST_SUCCESS): «Сохранить пак» → CONFIRM, «Попробовать другой» → «Собери состав» → ROLLBACK:титаны.

Что показано (ваш ответ 22.10.2026, сверка 3.3–3.4): причина, комната, враги квадратами, ваш пак — полоски ХП «до → после»,
красным — ниже порога паники (общего или личного); внизу — «Если не ответить, бот решит сам через 9:41»
(sos_timeout_minutes; 0 — строки нет). Комната, враги, причина и ХП до боя — из bot_data/sos_info.json (его пишет бот).
Крестик окна (ошибка 3.2): не останавливает бота сразу, а спрашивает «Остановить бота?» (on_close).
Окна только рисуют и сообщают выбор (on_answer); команды боту шлёт главная (ui/main_page.py).
"""
import time

import customtkinter as ctk

import telegram_report
from i18n import get_text
from ui import theme
from ui.icons import icon
from ui.widgets import Button, TitanAvatar, Tooltip, anchor_area, present_window, titan_name

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

WIDTH = 580
TICK_MS = 1000
SOON_S = 60   # меньше минуты до решения бота — строка таймера жёлтая

# Значок окна: иконка, её цвет, подложка
LOOKS = {
    "danger": ("triangle-alert", C["danger_text"], T["danger_on_surface"]),
    "warning": ("users", C["warning"], T["warning_on_surface"]),
    "success": ("check", C["success"], theme.blend(C["success"], C["bg_surface"], 0.14)),
}


def hp_value(value):
    """ХП из строки бота: число или {"hp": число, "energy": ...} (окно «Пак справился»)."""
    if isinstance(value, dict):
        value = value.get("hp", 0)
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def countdown_text(seconds):
    """9:41"""
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class InterventionWindow(ctk.CTkToplevel):
    """Общее у окон вмешательства. asked_at — когда бот задал вопрос (время строки), timeout_min — через сколько минут
    бот решит сам (0 — ждёт всегда). on_answer(команда) — выбор; on_close() — крестик."""

    def __init__(self, master, lang, look, title, text, timeout_min=0, asked_at=None, timer_key="sosw_timer",
                 on_answer=None, on_close=None, clock=time.monotonic):
        root = master.winfo_toplevel()
        super().__init__(root, fg_color=C["bg_surface"])
        self.withdraw()
        self.lang = lang
        self.on_answer = on_answer
        self.on_close = on_close
        self.clock = clock
        self.root_window = root
        self.timer_key = timer_key
        self.deadline = (asked_at if asked_at is not None else clock()) + timeout_min * 60 if timeout_min else None
        self.closed = False
        self.hidden = False      # спрятано на время «Собери состав»
        self.buttons = {}
        self._tick_id = None
        self.title(title)
        self.resizable(False, False)
        self.transient(root)
        self.protocol("WM_DELETE_WINDOW", self._close_pressed)
        self.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 0))
        head.grid_columnconfigure(1, weight=1)
        icon_name, color, bg = LOOKS[look]
        badge = ctk.CTkFrame(head, width=40, height=40, corner_radius=10, fg_color=bg)
        badge.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 14))
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="", image=icon(icon_name, color, 20)).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(head, text=title, font=F["dialog_title"], text_color=C["text"], anchor="w", justify="left").grid(
            row=0, column=1, sticky="w", pady=(0, 4))
        self.text_label = ctk.CTkLabel(head, text=text, font=F["text"], text_color=C["text_secondary"], anchor="w",
                                       justify="left", wraplength=WIDTH - 130)
        self.text_label.grid(row=1, column=1, sticky="w")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="ew", padx=24, pady=(16, 0))
        self.body.grid_columnconfigure(0, weight=1)
        self._rows = 0
        self.timer_label = ctk.CTkLabel(self, text="", font=F["label"], text_color=C["text_muted"], anchor="w",
                                        compound="left")
        self.button_row = ctk.CTkFrame(self, fg_color="transparent")
        self.button_row.grid(row=3, column=0, sticky="ew", padx=24, pady=(14, 22))
        if self.deadline is not None:
            self.timer_label.grid(row=2, column=0, sticky="w", padx=24, pady=(14, 0))
            self._tick()

    # ── Блоки содержимого ───────────────────────────────────────────────────
    def block(self):
        """Плашка с фактами (bg_elevated, рамка): возвращает рамку, внутри — сетка «подпись | значение»."""
        frame = ctk.CTkFrame(self.body, fg_color=C["bg_elevated"], corner_radius=8, border_width=1,
                             border_color=C["border"])
        frame.grid(row=self._rows, column=0, sticky="ew", pady=(0, 10))
        frame.grid_columnconfigure(1, weight=1)
        self._rows += 1
        return frame

    def fact(self, frame, row, label, widget_or_text, last=False):
        pad = (12 if row == 0 else 6, 12 if last else 0)
        ctk.CTkLabel(frame, text=label, font=F["label"], text_color=C["text_muted"], anchor="nw", width=84,
                     height=20).grid(row=row, column=0, sticky="nw", padx=(14, 8), pady=pad)
        if isinstance(widget_or_text, str):
            widget_or_text = ctk.CTkLabel(frame, text=widget_or_text, font=F["text"], text_color=C["text"],
                                          anchor="w", justify="left", wraplength=WIDTH - 190, height=20)
        widget_or_text.grid(row=row, column=1, sticky="nw", padx=(0, 14), pady=pad)  # верх — вровень с подписью

    def add_facts(self, reason=None, room=None, room_no=None, enemies=None):
        """Причина, комната, враги (то, что есть)."""
        rows = []
        if reason:
            rows.append((get_text(self.lang, "sosw_reason"), telegram_report.humanize(reason, self.lang)))
        if room:
            rows.append((get_text(self.lang, "sosw_room"), self._room_widget(room, room_no)))
        if enemies:
            rows.append((get_text(self.lang, "sosw_enemies"), self._enemies_widget(enemies)))
        if not rows:
            return
        frame = self.block()
        for i, (label, value) in enumerate(rows):
            if not isinstance(value, str):
                value = value(frame)
            self.fact(frame, i, label, value, last=i == len(rows) - 1)

    def _room_widget(self, room, room_no):
        def build(master):
            box = ctk.CTkFrame(master, fg_color="transparent")
            style = theme.element_style(room)
            ctk.CTkLabel(box, text="", image=icon(style["icon"], style["color"], 15), width=15).pack(side="left")
            name = theme.plain_text(get_text(self.lang, f"elem_{room}"))
            ctk.CTkLabel(box, text=name, font=F["body_bold"], text_color=style["text"], height=20).pack(
                side="left", padx=(6, 0))
            if room_no:
                ctk.CTkLabel(box, text="· " + get_text(self.lang, "sosw_room_no").format(n=room_no), font=F["text"],
                             text_color=C["text_muted"], height=20).pack(side="left", padx=(6, 0))
            return box
        return build

    def _enemies_widget(self, enemies):
        def build(master):
            box = ctk.CTkFrame(master, fg_color="transparent")
            for i, enemy in enumerate(enemies):
                TitanAvatar(box, enemy, lang=self.lang, size=32).pack(side="left", padx=(0 if i == 0 else 6, 0))
            return box
        return build

    def add_team(self, titans, before=None, panic=None):
        """Ваш пак: квадрат, имя, полоска ХП, «до → после». Красным — ниже порога паники титана."""
        if not titans:
            return
        before = before or {}
        frame = self.block()
        ctk.CTkLabel(frame, text=get_text(self.lang, "sosw_team"), font=F["label"], text_color=C["text_muted"],
                     anchor="w", height=18).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(10, 4))
        frame.grid_columnconfigure(1, weight=0)
        frame.grid_columnconfigure(2, weight=1)
        for row, (titan, value) in enumerate(titans.items(), start=1):
            hp = hp_value(value)
            low = panic is not None and hp < panic(titan)
            color = C["danger"] if low else C["success"]
            last = row == len(titans)
            pad = (4, 12 if last else 4)
            TitanAvatar(frame, titan, lang=self.lang, size=28).grid(row=row, column=0, sticky="w", padx=(14, 10),
                                                                     pady=pad)
            ctk.CTkLabel(frame, text=titan_name(self.lang, titan), font=F["text"], text_color=C["text"], anchor="w",
                         width=96, height=20).grid(row=row, column=1, sticky="w", pady=pad)
            bar = ctk.CTkProgressBar(frame, height=6, corner_radius=3, fg_color=C["bg_primary"], progress_color=color,
                                     border_width=0)
            bar.set(hp / 100)
            bar.grid(row=row, column=2, sticky="ew", padx=(8, 12), pady=pad)
            was = before.get(titan)
            text = f"{hp_value(was)}% → {hp}%" if was is not None and hp_value(was) != hp else f"{hp}%"
            ctk.CTkLabel(frame, text=text, font=F["mono"], text_color=C["danger_text"] if low else C["text"],
                         anchor="e", width=92, height=20).grid(row=row, column=3, sticky="e", padx=(0, 14), pady=pad)

    def add_buttons(self, specs):
        """specs — (имя, надпись, вид, иконка, подсказка, обработчик), слева направо; главная кнопка — последняя."""
        for name, text, kind, icon_name, tip, command in reversed(specs):
            button = Button(self.button_row, text, kind=kind, icon_name=icon_name, icon_size=14,
                            height=S["button_height_footer"], command=command)
            button.pack(side="right", padx=(10, 0))
            if tip:
                Tooltip(button, tip, side="top")
            self.buttons[name] = button

    # ── Таймер ──────────────────────────────────────────────────────────────
    def _tick(self):
        self._tick_id = None
        if self.closed:
            return
        left = self.deadline - self.clock()
        if left > 0:
            text = get_text(self.lang, self.timer_key).format(t=countdown_text(left))
            color = C["warning"] if left < SOON_S else C["text_muted"]
        else:
            text, color = get_text(self.lang, "sosw_timer_now"), C["warning"]
        if text != self.timer_label.cget("text"):
            self.timer_label.configure(text=" " + text, text_color=color, image=icon("gauge", color, 14))
        try:
            self._tick_id = self.after(TICK_MS, self._tick)
        except Exception:
            self._tick_id = None

    # ── Показ, ответ, закрытие ──────────────────────────────────────────────
    def show(self):
        """Показать по центру окна программы (окно программы свёрнуто — сначала развернуть: иначе окна не видно).
        Свёрнуто в мини-бар (шаг 4) — по центру картинки игры, окно программы остаётся свёрнутым (ui/widgets.py).
        Показ — через present_window: окно собрано целиком и не пропадает после перекраски заголовка в Windows."""
        if self.closed:
            return
        self.hidden = False
        try:
            # В мини-баре (шаг 4) окно программы не разворачиваем: окно SOS встанет над игрой само по себе
            if self.root_window.state() == "iconic" and not getattr(self.root_window, "mini", False):
                self.root_window.deiconify()
        except Exception:
            pass
        present_window(self, self._place_centered, hidden=lambda: self.closed or self.hidden)

    def _place_centered(self):
        root = self.root_window
        self.update_idletasks()
        w, h = max(WIDTH, self.winfo_reqwidth()), self.winfo_reqheight()
        ax, ay, aw, ah = anchor_area(root)
        x = ax + (aw - w) // 2
        y = ay + (ah - h) // 3
        x = max(0, min(x, self.winfo_screenwidth() - w))
        y = max(0, min(y, self.winfo_screenheight() - h - 40))
        self.geometry(f"{w}x{h}+{x}+{y}")

    def hide(self):
        """Спрятать на время окна «Собери состав» (закрыли его — окно вернётся, ошибка 3.2)."""
        if not self.closed:
            self.hidden = True
            self.withdraw()

    def answer(self, command):
        """Выбор сделан: окно закрывается, главная шлёт команду боту."""
        if self.closed:
            return
        self.close_silently()
        if self.on_answer:
            self.on_answer(command)

    def _close_pressed(self):
        if self.on_close:
            self.on_close()

    def close_silently(self):
        """Закрыть без ответа (бот решил сам — [SOS_CLOSE], ответ пришёл из Telegram, окно программы закрывается)."""
        if self.closed:
            return
        self.closed = True
        if self._tick_id:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None
        try:
            self.destroy()
        except Exception:
            pass


def sos_window(master, lang, titans, is_manual, info, panic, timeout_min, asked_at, on_answer, on_close,
               on_rollback):
    """«Требуется вмешательство». on_rollback() — «Откатить бой» (главная открывает «Собери состав»)."""
    window = InterventionWindow(master, lang, "danger", get_text(lang, "sosw_title"), get_text(lang, "sosw_text"),
                                timeout_min=timeout_min, asked_at=asked_at, on_answer=on_answer, on_close=on_close)
    window.add_facts(info.get("reason"), info.get("room"), info.get("room_no"), info.get("enemies"))
    window.add_team(titans, info.get("hp_before"), panic)
    specs = [
        ("manual", get_text(lang, "sosw_manual"), "secondary", "gamepad-2", get_text(lang, "sosw_tip_manual"),
         lambda: window.answer("MANUAL")),
        ("ignore", get_text(lang, "sosw_ignore"), "secondary", "arrow-right", get_text(lang, "sosw_tip_ignore"),
         lambda: window.answer("IGNORE")),
    ]
    if is_manual:
        specs.append(("stop", get_text(lang, "sosw_stop"), "danger", "square-filled", get_text(lang, "sosw_tip_stop"),
                      lambda: window.answer("STOP")))
    else:
        specs.append(("rollback", get_text(lang, "sosw_rollback"), "blue", "rotate-ccw",
                      get_text(lang, "sosw_tip_rollback"), on_rollback))
    window.add_buttons(specs)
    window.show()
    return window


def no_team_window(master, lang, data, timeout_min, asked_at, on_answer, on_close, on_new_pack):
    """«Нет подходящего пака». data — JSON из строки бота: room, enemies, reason."""
    window = InterventionWindow(master, lang, "warning", get_text(lang, "nopack_title"), get_text(lang, "nopack_text"),
                                timeout_min=timeout_min, asked_at=asked_at, on_answer=on_answer, on_close=on_close)
    window.add_facts(data.get("reason"), data.get("room"), None, data.get("enemies"))
    window.add_buttons([
        ("stop", get_text(lang, "sosw_stop"), "danger", "square-filled", get_text(lang, "sosw_tip_stop"),
         lambda: window.answer("STOP")),
        ("manual", get_text(lang, "sosw_manual"), "secondary", "gamepad-2", get_text(lang, "nopack_tip_manual"),
         lambda: window.answer("MANUAL")),
        ("new_pack", get_text(lang, "sosw_new_pack"), "blue", "users", get_text(lang, "nopack_tip_new"), on_new_pack),
    ])
    window.show()
    return window


def test_window(master, lang, titans, info, panic, timeout_min, asked_at, on_answer, on_close, on_other):
    """«Пак справился»: проверяемый пак выиграл — сохранить его правилом или попробовать другой."""
    window = InterventionWindow(master, lang, "success", get_text(lang, "testw_title"), get_text(lang, "testw_text"),
                                timeout_min=timeout_min, asked_at=asked_at, timer_key="testw_timer",
                                on_answer=on_answer, on_close=on_close)
    window.add_facts(None, info.get("room"), None, info.get("enemies"))
    window.add_team(titans, None, panic)
    window.add_buttons([
        ("other", get_text(lang, "testw_other"), "secondary", "rotate-ccw", get_text(lang, "testw_tip_other"),
         on_other),
        ("confirm", get_text(lang, "testw_save"), "save", "save", get_text(lang, "testw_tip_save"),
         lambda: window.answer("CONFIRM")),
    ])
    window.show()
    return window
