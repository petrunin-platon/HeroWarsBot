"""Мини-бар (док-плеер) под окном игры (задача 15, шаг 4; макет design/mockups/02_hud, сверка — раздел 2).

Окно без рамки стоит вплотную под картинкой игры в окне scrcpy и шириной с неё (ui/hud_place.py),
раз в 0,5 с проверяет, где окно игры, и едет за ним (пока окно двигают — чаще). На картинку игры не заходит
ни на пиксель: иначе мини-бар попал бы на снимок, по которому бот ищет кнопки. Окно игры свёрнуто или закрыто —
мини-бар прячется.

Высота 100 вместо 60 из макета и 5 колонок (ваш ответ после проверки шага 4: в 60 было тесно, 4 строки):
- состояние (фарм / пауза / SOS), что бот делает сейчас и сколько секунд, комнаты и этажи (номер этажа бот не знает,
  ответ 1.6), время сессии;
- цель сессии с полоской (как на главной, ответ 1.7), среднее время комнаты, сколько осталось до цели;
- ХП пака после последнего боя (квадраты титанов, ниже порога паники — красным);
- четыре последних события (ui/hud_events.py);
- кнопки 2×2 (шире квадрата, по центру колонки): пауза / продолжить (F9), стоп (F10), выключить экран телефона, развернуть окно программы.
На SOS мини-бар красный, а первая кнопка поднимает окно SOS (ваш ответ 22.10.2026): бот ждёт решения, а не «продолжить».

Мини-бар никогда не становится активным окном (ui/hud_place.py: win_no_activate): бот работает, только пока активно
окно игры (main.py:wait_for_focus), и щелчок по мини-бару его бы остановил.
Правила против зависаний (ui/widgets.py): поверх всех окон, но без особых режимов прозрачности; наведение меняет
только цвета; свои after отменяются в destroy().
"""
import tkinter as tk
from tkinter import font as tkfont

import customtkinter as ctk

from i18n import get_text
from ui import hud_events, hud_place, log_lines, theme
from ui.icons import dot, icon
from ui.widgets import IconButton, TitanAvatar

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

FOLLOW_MS = 500          # как часто мини-бар смотрит, где окно игры
MOVING_MS = 100          # окно игры двигают — смотрим чаще, чтобы мини-бар не отставал
PULSE_MS = 800           # точка состояния «дышит» на фарме и на SOS
# Колонки (ваш ответ после проверки шага 4: панель выше, 4 строки, ХП пака): состояние, цель, пак, события, кнопки
COLUMNS = (15, 21, 19, 33, 12)
BUTTON = 38
BUTTON_WIDE = 64         # кнопки шире квадрата: колонка не пустует, но и не забита до краёв (ваш ответ)
PAD = 14
LINE_GAP = 3             # между строками колонки
AVATAR = 30              # квадрат титана в колонке пака
MAX_TEAM = 5
BADGE = 60               # метки событий одной ширины: текст событий начинается в одном месте

# Состояние → (ключ надписи, цвет точки и надписи)
STATES = {
    "starting": ("hud_starting", "success"),
    "farm": ("hud_farm", "success"),
    "paused": ("hud_paused", "warning"),
    "debug": ("hud_debug", "warning"),
    "sos": ("hud_sos", "danger"),
}


class HudWindow(tk.Toplevel):
    """Окно мини-бара. CustomTkinter следит за масштабом Windows у всех окон, где есть его виджеты, и при смене
    (мини-бар уехал на экран с другим масштабом) зовёт эти два метода — у простого окна Tk их нет."""

    def block_update_dimensions_event(self):
        pass

    def unblock_update_dimensions_event(self):
        pass


class Hud:
    """root — окно программы (по нему CustomTkinter считает масштаб); locate() — окно игры (hud_place.GameWindow) или
    None; on_command(имя) — кнопка: "pause" (пауза или продолжить), "sos" (показать окно SOS), "stop", "sleep", "expand"."""

    def __init__(self, root, lang, locate, on_command):
        self.root = root
        self.lang = lang
        self.locate = locate
        self.on_command = on_command
        self.visible = False         # мини-бар включён (окно программы свёрнуто в него)
        self.shown = False           # и правда на экране (есть окно игры и место под ним)
        self.place = None            # (x, y, ширина, высота, "below"/"above")
        self.game = None             # последнее найденное окно игры
        self.view = None
        self._events_version = None
        self._follow_id = None
        self._pulse_id = None
        self._pulse_on = True
        self._frame_id = None
        self._look = None
        self._widths = None
        self._team_shown = None
        self._goal_image = None
        self._button_look = None
        self._button_enabled = None
        self._fonts = {}

        top = self.top = HudWindow(root)
        top.withdraw()
        top.overrideredirect(True)
        try:
            top.attributes("-topmost", True)   # поверх окон, но не на игре: место считает hud_place.place
        except tk.TclError:
            pass
        top.configure(bg=C["border"])
        self.body = tk.Frame(top, bg=C["bg_surface"], highlightthickness=1, highlightbackground=C["border"],
                             highlightcolor=C["border"])
        self.body.pack(fill="both", expand=True)
        self.columns = [tk.Frame(self.body, bg=C["bg_surface"], width=10, height=10) for _ in COLUMNS]
        self.lines = [tk.Frame(self.body, bg=C["border"], width=1) for _ in COLUMNS[1:]]
        for column in self.columns:
            column.pack_propagate(False)
            column.grid_propagate(False)
        self._build_status(self.columns[0])
        self._build_goal(self.columns[1])
        self._build_team(self.columns[2])
        self._build_events(self.columns[3])
        self._build_buttons(self.columns[4])
        self.body.bind("<Configure>", self._layout, add="+")

    # ── Части ───────────────────────────────────────────────────────────────
    def _label(self, master, font, color, **kwargs):
        return ctk.CTkLabel(master, text="", font=font, text_color=color, fg_color="transparent", height=16,
                            anchor="w", **kwargs)

    def _frame(self, master):
        return tk.Frame(master, bg=C["bg_surface"])

    def _build_status(self, column):
        """Состояние, что бот делает сейчас, комнаты и этажи, время сессии."""
        column.grid_rowconfigure((0, 5), weight=1)
        column.grid_columnconfigure(1, weight=1)
        self.dot = ctk.CTkLabel(column, text="", width=10, height=10)
        self.dot.grid(row=1, column=0, padx=(PAD, 10))
        self.status = self._label(column, (theme.FONT_FAMILY, 12, "bold"), C["success"])
        self.status.grid(row=1, column=1, sticky="w")
        self.now = self._label(column, F["label"], C["text"])
        self.counters = self._label(column, F["label"], C["text_secondary"])
        self.clock = self._label(column, F["mono"], C["text_secondary"])
        for row, label in enumerate((self.now, self.counters, self.clock), start=2):
            label.grid(row=row, column=1, sticky="w", pady=(LINE_GAP, 0), padx=(0, 8))

    def _build_goal(self, column):
        """Цель с полоской, среднее время комнаты и сколько осталось до цели."""
        column.grid_rowconfigure((0, 5), weight=1)
        column.grid_columnconfigure(1, weight=1)
        self.goal_icon = ctk.CTkLabel(column, text="", width=18, height=18)
        self.goal_icon.grid(row=1, column=0, rowspan=2, padx=(PAD, 10))
        head = self._frame(column)
        head.grid(row=1, column=1, sticky="ew", padx=(0, PAD))
        head.grid_columnconfigure(0, weight=1)
        self.goal_name = self._label(head, F["label"], C["text_secondary"])
        self.goal_name.grid(row=0, column=0, sticky="w")
        self.goal_done = self._label(head, F["mono"], C["text"])
        self.goal_done.grid(row=0, column=1, sticky="e")
        self.goal_target = self._label(head, F["mono"], C["text_muted"])
        self.goal_target.grid(row=0, column=2, sticky="e")
        self.goal_bar = ctk.CTkProgressBar(column, height=6, corner_radius=3, fg_color=C["bg_elevated"],
                                           progress_color=C["blue"], border_width=0)
        self.goal_bar.grid(row=2, column=1, sticky="ew", padx=(0, PAD), pady=(6, 2))
        self.goal_bar.set(0)
        self.avg = self._label(column, F["label"], C["text_secondary"])
        self.avg.grid(row=3, column=1, sticky="w", pady=(LINE_GAP, 0))
        self.eta = self._label(column, F["label"], C["text_secondary"])
        self.eta.grid(row=4, column=1, sticky="w", pady=(LINE_GAP, 0))

    def _build_team(self, column):
        """ХП пака после последнего боя: квадраты титанов и ХП под ними (ниже порога паники — красным)."""
        column.grid_rowconfigure((0, 3), weight=1)
        column.grid_columnconfigure(0, weight=1)
        self.team_title = self._label(column, F["label"], C["text_secondary"])
        self.team_title.grid(row=1, column=0, sticky="w", padx=PAD)
        row = self._frame(column)
        row.grid(row=2, column=0, sticky="w", padx=PAD, pady=(6, 0))
        self.team_slots = []
        for index in range(MAX_TEAM):
            cell = self._frame(row)
            cell.grid(row=0, column=index, padx=(0 if index == 0 else 8, 0))
            avatar = TitanAvatar(cell, "araji", lang=self.lang, size=AVATAR)
            avatar.grid(row=0, column=0)
            hp = ctk.CTkLabel(cell, text="", font=F["mono"], text_color=C["text"], fg_color="transparent",
                              height=14, width=AVATAR)
            hp.grid(row=1, column=0, pady=(2, 0))
            cell.grid_remove()
            self.team_slots.append((cell, avatar, hp))
        self.team_empty = self._label(row, F["label"], C["text_muted"])
        self.team_empty.grid(row=0, column=MAX_TEAM, sticky="w")

    def _build_events(self, column):
        column.grid_rowconfigure((0, hud_events.KEEP + 1), weight=1)
        column.grid_columnconfigure(0, weight=1)
        self.event_rows = []
        for index in range(hud_events.KEEP):
            row = self._frame(column)
            row.grid(row=index + 1, column=0, sticky="ew", padx=PAD, pady=(0 if index == 0 else LINE_GAP, 0))
            row.grid_columnconfigure(1, weight=1)
            badge = ctk.CTkLabel(row, text="", font=F["small_bold"], height=16, corner_radius=4, padx=6, width=BADGE)
            badge.grid(row=0, column=0, padx=(0, 8))
            text = self._label(row, F["text"] if index == 0 else F["label"],
                               C["text"] if index == 0 else C["text_muted"])
            text.grid(row=0, column=1, sticky="w")
            when = self._label(row, (theme.MONO_FAMILY, 11), C["text_muted"])
            when.grid(row=0, column=2, sticky="e", padx=(8, 0))
            self.event_rows.append((row, badge, text, when))

    def _build_buttons(self, column):
        column.grid_rowconfigure((0, 2), weight=1)
        column.grid_columnconfigure(0, weight=1)
        grid = self._frame(column)
        grid.grid(row=1, column=0)
        self.buttons = {}
        style = dict(fg_color=C["bg_elevated"], hover_color=T["hover_elevated"], border_color=C["border"])
        for index, (name, icon_name, color, size) in enumerate((("pause", "pause-filled", C["warning"], 15),
                                                                ("stop", "square-filled", C["danger"], 14),
                                                                ("sleep", "moon", C["text_secondary"], 16),
                                                                ("expand", "maximize-2", C["text_secondary"], 16))):
            button = IconButton(grid, icon_name, size=BUTTON, icon_size=size, icon_color=color,
                                tooltip=lambda n=name: self._tip(n), command=lambda n=name: self._pressed(n), **style)
            button.configure(width=BUTTON_WIDE)
            button.grid(row=index // 2, column=index % 2, padx=(0 if index % 2 == 0 else 6, 0),
                        pady=(0 if index < 2 else 6, 0))
            self.buttons[name] = button

    def _tooltips(self):
        tips = [button.tooltip for button in self.buttons.values()]
        tips += [avatar.tooltip for _cell, avatar, _hp in self.team_slots]
        return [tip for tip in tips if tip]

    # ── Раскладка ───────────────────────────────────────────────────────────
    def _layout(self, _event=None):
        """Колонки по долям COLUMNS от ширины мини-бара (как grid-template-columns макета), линии между ними."""
        try:
            width, height = self.body.winfo_width() - 2, self.body.winfo_height() - 2
        except tk.TclError:
            return
        if width < 10 or height < 10:
            return
        total = sum(COLUMNS)
        x = 1
        widths = []
        for index, share in enumerate(COLUMNS):
            w = round(width * share / total) if index < len(COLUMNS) - 1 else width + 1 - x
            self.columns[index].place(x=x, y=1, width=max(1, w), height=height)
            if index:
                self.lines[index - 1].place(x=x, y=1, width=1, height=height)
            widths.append(w)
            x += w
        if widths != self._widths:
            self._widths = widths
            self._events_version = None
            if self.view:
                self.render(self.view)

    # ── Показ и место ───────────────────────────────────────────────────────
    def show(self):
        """Включить мини-бар: он встанет под окном игры, как только оно найдётся."""
        if self.visible:
            return
        self.visible = True
        self._follow()
        self._pulse()

    def hide(self):
        self.visible = False
        self.shown = False
        for name in ("_follow_id", "_pulse_id"):
            after_id = getattr(self, name)
            if after_id:
                try:
                    self.top.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, name, None)
        try:
            self.top.withdraw()
        except tk.TclError:
            pass

    def height(self):
        return round(S["hud_height_tall"] * ctk.ScalingTracker.get_widget_scaling(self.status))

    def _follow(self):
        self._follow_id = None
        if not self.visible:
            return
        delay = FOLLOW_MS
        try:
            game = self.locate()
        except Exception:
            game = None    # сбой поиска окна — не повод ронять окно программы; попробуем через 0,5 с
        self.game = game
        spot = hud_place.place(game, self.height()) if game is not None else None
        try:
            if spot is None:
                if self.shown:
                    self.top.withdraw()
                    self.shown = False
            else:
                if spot != self.place or not self.shown:
                    x, y, w, h, side = spot
                    self.top.geometry(f"{w}x{h}+{x}+{y}")
                    if spot[:2] != (self.place or spot)[:2]:
                        delay = MOVING_MS
                    if side != (self.place or (None,) * 5)[4]:
                        tip_side = "bottom" if side == "below" else "top"   # подсказки — не на картинке игры
                        for tip in self._tooltips():
                            tip.side = tip_side
                    self.place = spot
                if not self.shown:
                    self.top.deiconify()
                    self.shown = True
                    self._no_activate(game)
        except tk.TclError:
            return
        self._follow_id = self.top.after(delay, self._follow)

    def _no_activate(self, game):
        """Мини-бар не забирает активность у окна игры (только Windows)."""
        if not hud_place.windows_available():
            return
        try:
            self.top.update_idletasks()
            if self._frame_id is None:
                self._frame_id = int(self.top.wm_frame(), 16)
                hud_place.win_no_activate(self._frame_id)
            hud_place.win_give_back_focus({self._frame_id}, game.hwnd)
        except Exception:
            pass

    def game_area(self):
        """(x, y, ширина, высота) картинки игры или None — по центру её встают окна SOS, пока окно программы свёрнуто."""
        game = self.game
        if game is None:
            return None
        client = game.client
        return client.left, client.top, client.width, client.height

    def _pulse(self):
        self._pulse_id = None
        if not self.visible:
            return
        self._pulse_on = not self._pulse_on
        self._paint_dot()
        self._pulse_id = self.top.after(PULSE_MS, self._pulse)

    def _paint_dot(self):
        state = self.view["state"] if self.view else "farm"
        color = C[STATES[state][1]]
        if state in ("farm", "sos", "starting") and not self._pulse_on:
            color = theme.blend(color, self._background(state), 0.45)
        try:
            self.dot.configure(image=dot(color, 10))
        except tk.TclError:
            pass

    # ── Кнопки ──────────────────────────────────────────────────────────────
    def _pressed(self, name):
        if name == "pause" and self.view and self.view["state"] == "sos":
            name = "sos"
        self.on_command(name)

    def _tip(self, name):
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        state = self.view["state"] if self.view else "farm"
        if name == "pause":
            return g({"sos": "hud_tip_sos", "debug": "main_tip_debug", "paused": "main_tip_continue"}.get(
                state, "main_tip_pause"))
        return g({"stop": "main_tip_stop", "sleep": "hdr_tip_sleep", "expand": "hud_tip_expand"}[name])

    # ── Что показать ────────────────────────────────────────────────────────
    def _background(self, state):
        return C["sos_bg"] if state == "sos" else C["bg_surface"]

    def set_language(self, lang):
        if lang != self.lang:
            self.lang = lang
            self._look = None
            self._events_version = None
            self._team_shown = None
            if self.view:
                self.render(self.view)

    def render(self, view):
        """view — состояние от главной (MainPage.hud_view): state, rooms, floors, elapsed, goal (вид, сделано, нужно,
        доля) или None, titanite, avg, eta, per_hour, panic(титан), heal_hp, feed."""
        self.view = view
        state = view["state"]
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        self._paint_frame(state)
        self._set(self.status, g(STATES[state][0]), text_color=C["danger_text" if state == "sos" else STATES[state][1]])
        status_room = self._room(0, 34)
        self._set(self.now, self._fit(hud_events.phase_text(view["feed"], self.lang), F["label"], status_room))
        self._set(self.counters, self._fit(g("hud_counters").format(rooms=view["rooms"], floors=view["floors"]),
                                           F["label"], status_room))
        self._set(self.clock, g("hud_time").format(t=log_lines.clock_text(view["elapsed"])))
        self._render_goal(view)
        self._render_team(view)
        self._render_events(view)
        self._render_button(state)
        self._paint_dot()

    def _room(self, column, pad):
        """Сколько пикселей влезает в колонку column за вычетом отступов pad (в пикселях макета)."""
        scale = ctk.ScalingTracker.get_widget_scaling(self.status)
        width = self._widths[column] if self._widths else 200
        return max(20, width - round(pad * scale))

    def _paint_frame(self, state):
        bg = self._background(state)
        line = theme.blend(C["danger"], bg, 0.35) if state == "sos" else C["border"]
        border = C["danger"] if state == "sos" else C["border"]
        look = (bg, line, border)
        if look == self._look:
            return
        self._look = look
        self.body.configure(bg=bg, highlightbackground=border, highlightcolor=border)
        for line_frame in self.lines:
            line_frame.configure(bg=line)
        self._recolor(self.body, bg)

    def _recolor(self, widget, bg):
        """Фон всех частей мини-бара (обычный или красноватый SOS). Внутрь виджетов CustomTkinter не лезем."""
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkBaseClass):
                child.configure(bg_color=bg)
            elif isinstance(child, tk.Frame) and child not in self.lines:
                child.configure(bg=bg)
                self._recolor(child, bg)

    def _render_goal(self, view):
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        goal = view.get("goal")
        if goal:
            kind, done, target, share = goal
            icon_name, color = theme.GOAL_ICONS[kind]
            self._set(self.goal_name, g(f"main_goal_{kind}"))
            self._set(self.goal_done, done)
            self._set(self.goal_target, f" / {target}")
            self.goal_bar.grid()
            if abs(self.goal_bar.get() - share) > 0.001:
                self.goal_bar.set(share)
        else:
            icon_name, color = theme.GOAL_ICONS["titanite"]
            self._set(self.goal_name, g("main_goal_titanite"))
            self._set(self.goal_done, view.get("titanite", "0"))
            self._set(self.goal_target, "")
            self.goal_bar.grid_remove()
        image_key = (icon_name, color)
        if self._goal_image != image_key:
            self._goal_image = image_key
            self.goal_icon.configure(image=icon(icon_name, color, 18))
        room = self._room(1, PAD + 42)
        avg = view.get("avg")
        self._set(self.avg, self._fit(g("hud_avg_room").format(s=round(avg)) if avg is not None else g("hud_avg_none"),
                                      F["label"], room))
        eta = view.get("eta")
        if goal:
            text = g("hud_eta_none") if eta is None else g("hud_eta_done") if eta == 0 else \
                g("hud_eta").format(t=hud_events.duration_text(eta, self.lang))
        else:
            per_hour = view.get("per_hour")
            text = g("hud_per_hour").format(n=log_lines.group_digits(per_hour)) if per_hour else ""
        self._set(self.eta, self._fit(text, F["label"], room))

    def _render_team(self, view):
        """ХП пака после последнего боя. ХП ниже порога паники (личного или общего) — красным, ниже порога отхила —
        жёлтым, как бот и решает после боя."""
        feed = view["feed"]
        panic, heal_hp = view.get("panic"), view.get("heal_hp") or 0
        team = feed.team[:MAX_TEAM]
        key = (tuple(team), self.lang)
        if key == self._team_shown:
            return
        self._team_shown = key
        self._set(self.team_title, get_text(self.lang, "hud_team_title"))
        for index, (cell, avatar, hp_label) in enumerate(self.team_slots):
            if index >= len(team):
                cell.grid_remove()
                continue
            titan, hp = team[index]
            if avatar.titan != titan:
                avatar.set_titan(titan)
            if avatar.lang != self.lang:
                avatar.set_language(self.lang)
            if hp is None:
                text, color = "—", C["danger_text"]
            else:
                text = f"{hp}%"
                color = C["danger_text"] if panic and hp < panic(titan) else \
                    C["warning"] if hp < heal_hp else C["text"]
            self._set(hp_label, text, text_color=color)
            cell.grid()
        if team:
            self.team_empty.grid_remove()
        else:
            self._set(self.team_empty, get_text(self.lang, "hud_team_empty"))
            self.team_empty.grid()

    def _render_events(self, view):
        feed = view["feed"]
        key = (feed.version, len(feed.events), self.lang, tuple(self._widths or ()))
        if key == self._events_version:
            return
        self._events_version = key
        events = feed.latest()
        room = self._room(3, 2 * PAD + 8)
        small = self._font((theme.MONO_FAMILY, 11), ctk.ScalingTracker.get_widget_scaling(self.status))
        bold = self._font((theme.FONT_FAMILY, 11, "bold"), ctk.ScalingTracker.get_widget_scaling(self.status))
        scale = ctk.ScalingTracker.get_widget_scaling(self.status)
        for index, (_row, badge, text, when) in enumerate(self.event_rows):
            if index >= len(events):
                badge.grid_remove()
                self._set(text, "")
                self._set(when, "")
                continue
            event = events[index]
            name, color, bg = hud_events.badge(event, self.lang)
            if (badge.cget("text"), badge.cget("text_color"), badge.cget("fg_color")) != (name, color, bg):
                badge.configure(text=name, text_color=color, fg_color=bg)
            badge.grid()
            self._set(when, event.time)
            badge_w = max(bold.measure(name) + round(12 * scale), round(BADGE * scale))
            left = room - small.measure(event.time) - badge_w - round(16 * scale)
            self._set(text, self._fit(hud_events.text(event, self.lang), F["text"] if index == 0 else F["label"], left))

    def _fit(self, text, font_spec, room):
        """Обрезать текст с «…», чтобы он влез в room пикселей: иначе он раздвинул бы колонку (как в макете —
        text-overflow: ellipsis)."""
        font = self._font(font_spec, ctk.ScalingTracker.get_widget_scaling(self.status))
        if font.measure(text) <= room:
            return text
        while text and font.measure(text + "…") > room:
            text = text[:-1]
        return text.rstrip() + "…"

    def _font(self, spec, scale):
        """Шрифт для замера ширины текста (в пикселях экрана), один на размер и масштаб."""
        key = (spec, scale)
        fonts = self._fonts
        if key not in fonts:
            fonts[key] = tkfont.Font(root=self.top, family=spec[0], size=-round(spec[1] * scale),
                                     weight=spec[2] if len(spec) > 2 else "normal")
        return fonts[key]

    def _render_button(self, state):
        button = self.buttons["pause"]
        if state in ("paused", "debug", "sos"):
            look = ("play-filled", C["success"], C["green"])
        else:
            look = ("pause-filled", C["warning"], C["border"])
        if self._button_look != look:
            self._button_look = look
            button.set_icon(look[0], look[1])
            button.configure(border_color=look[2])
        enabled = state != "starting"
        if self._button_enabled != enabled:
            self._button_enabled = enabled
            button.set_enabled(enabled)

    @staticmethod
    def _set(label, text, **colors):
        changes = {k: v for k, v in colors.items() if label.cget(k) != v}
        if label.cget("text") != text:
            changes["text"] = text
        if changes:
            label.configure(**changes)

    def destroy(self):
        self.hide()
        try:
            self.top.destroy()
        except tk.TclError:
            pass
