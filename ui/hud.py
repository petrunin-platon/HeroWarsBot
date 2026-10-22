"""Мини-бар (док-плеер) под окном игры (задача 15, шаг 4; макет design/mockups/02_hud, сверка — раздел 2).

Окно без рамки высотой 60 стоит вплотную под картинкой игры в окне scrcpy и шириной с неё (ui/hud_place.py),
раз в 0,5 с проверяет, где окно игры, и едет за ним (пока окно двигают — чаще). На картинку игры не заходит
ни на пиксель: иначе мини-бар попал бы на снимок, по которому бот ищет кнопки. Окно игры свёрнуто или закрыто —
мини-бар прячется.

Колонки 15/25/40/20 (как в макете): состояние (фарм / пауза / SOS) и сколько этажей пройдено (номер этажа бот
не знает, ответ 1.6); цель сессии с полоской (как на главной, ответ 1.7); два последних события (ui/hud_events.py);
кнопки: пауза / продолжить (F9), стоп (F10), выключить экран телефона, развернуть окно программы.
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
from ui import hud_events, hud_place, theme
from ui.icons import dot, icon
from ui.widgets import IconButton

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

FOLLOW_MS = 500          # как часто мини-бар смотрит, где окно игры
MOVING_MS = 100          # окно игры двигают — смотрим чаще, чтобы мини-бар не отставал
PULSE_MS = 800           # точка состояния «дышит» на фарме и на SOS
COLUMNS = (15, 25, 40, 20)
BUTTON = 38
PAD = 14

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
        self._column_width = None
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
        self._build_events(self.columns[2])
        self._build_buttons(self.columns[3])
        self.body.bind("<Configure>", self._layout, add="+")

    # ── Части ───────────────────────────────────────────────────────────────
    def _label(self, master, font, color, **kwargs):
        return ctk.CTkLabel(master, text="", font=font, text_color=color, fg_color="transparent", height=16,
                            anchor="w", **kwargs)

    def _build_status(self, column):
        column.grid_rowconfigure((0, 3), weight=1)
        self.dot = ctk.CTkLabel(column, text="", width=10, height=10)
        self.dot.grid(row=1, column=0, rowspan=2, padx=(PAD, 10))
        self.status = self._label(column, (theme.FONT_FAMILY, 12, "bold"), C["success"])
        self.status.grid(row=1, column=1, sticky="w")
        self.floors = self._label(column, F["label"], C["text_secondary"])
        self.floors.grid(row=2, column=1, sticky="w", pady=(2, 0))

    def _build_goal(self, column):
        column.grid_rowconfigure((0, 3), weight=1)
        column.grid_columnconfigure(1, weight=1)
        self.goal_icon = ctk.CTkLabel(column, text="", width=18, height=18)
        self.goal_icon.grid(row=1, column=0, rowspan=2, padx=(PAD, 10))
        head = tk.Frame(column, bg=C["bg_surface"])
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
        self.goal_bar.grid(row=2, column=1, sticky="ew", padx=(0, PAD), pady=(6, 0))
        self.goal_bar.set(0)
        self.goal_heads = (head,)

    def _build_events(self, column):
        column.grid_rowconfigure((0, 3), weight=1)
        column.grid_columnconfigure(0, weight=1)
        first = tk.Frame(column, bg=C["bg_surface"])
        first.grid(row=1, column=0, sticky="ew", padx=PAD)
        first.grid_columnconfigure(1, weight=1)
        self.badge = ctk.CTkLabel(first, text="", font=F["small_bold"], height=18, corner_radius=4, padx=6)
        self.badge.grid(row=0, column=0, padx=(0, 8))
        self.event_text = self._label(first, F["text"], C["text"])
        self.event_text.grid(row=0, column=1, sticky="w")
        self.event_time = self._label(first, (theme.MONO_FAMILY, 11), C["text_muted"])
        self.event_time.grid(row=0, column=2, sticky="e", padx=(8, 0))
        second = tk.Frame(column, bg=C["bg_surface"])
        second.grid(row=2, column=0, sticky="ew", padx=PAD, pady=(4, 0))
        second.grid_columnconfigure(0, weight=1)
        self.prev_text = self._label(second, F["label"], C["text_muted"])
        self.prev_text.grid(row=0, column=0, sticky="w")
        self.prev_time = self._label(second, (theme.MONO_FAMILY, 11), C["text_muted"])
        self.prev_time.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.event_rows = (first, second)

    def _build_buttons(self, column):
        column.grid_rowconfigure((0, 2), weight=1)
        column.grid_columnconfigure(0, weight=1)
        row = tk.Frame(column, bg=C["bg_surface"])
        row.grid(row=1, column=0, sticky="e", padx=(0, 8))
        self.buttons = {}
        style = dict(fg_color=C["bg_elevated"], hover_color=T["hover_elevated"], border_color=C["border"])
        for name, icon_name, color, size in (("pause", "pause-filled", C["warning"], 15),
                                             ("stop", "square-filled", C["danger"], 14),
                                             ("sleep", "moon", C["text_secondary"], 16),
                                             ("expand", "maximize-2", C["text_secondary"], 16)):
            button = IconButton(row, icon_name, size=BUTTON, icon_size=size, icon_color=color,
                                tooltip=lambda n=name: self._tip(n), command=lambda n=name: self._pressed(n), **style)
            button.pack(side="left", padx=(4, 0))
            self.buttons[name] = button

    # ── Раскладка ───────────────────────────────────────────────────────────
    def _layout(self, _event=None):
        """Колонки 15/25/40/20 от ширины мини-бара (как grid-template-columns макета), линии между ними."""
        try:
            width, height = self.body.winfo_width() - 2, self.body.winfo_height() - 2
        except tk.TclError:
            return
        if width < 10 or height < 10:
            return
        total = sum(COLUMNS)
        x = 1
        for index, share in enumerate(COLUMNS):
            w = round(width * share / total) if index < len(COLUMNS) - 1 else width + 1 - x
            self.columns[index].place(x=x, y=1, width=max(1, w), height=height)
            if index:
                self.lines[index - 1].place(x=x, y=1, width=1, height=height)
            x += w
        widths = round(width * COLUMNS[2] / total)
        if widths != self._column_width:
            self._column_width = widths
            self._events_version = None
            if self.view:
                self._render_events(self.view)

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
        return round(S["hud_height"] * ctk.ScalingTracker.get_widget_scaling(self.status))

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
                        for button in self.buttons.values():
                            if button.tooltip:
                                button.tooltip.side = tip_side
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
            if self.view:
                self.render(self.view)

    def render(self, view):
        """view — состояние от главной: state, floors, goal (вид, сделано, нужно, доля) или None, titanite, feed."""
        self.view = view
        state = view["state"]
        g = lambda key: get_text(self.lang, key)  # noqa: E731
        self._paint_frame(state)
        self._set(self.status, g(STATES[state][0]), text_color=C["danger_text" if state == "sos" else STATES[state][1]])
        self._set(self.floors, g("hud_floors").format(n=view["floors"]))
        self._render_goal(view)
        self._render_events(view)
        self._render_button(state)
        self._paint_dot()

    def _paint_frame(self, state):
        bg = self._background(state)
        line = theme.blend(C["danger"], bg, 0.35) if state == "sos" else C["border"]
        border = C["danger"] if state == "sos" else C["border"]
        look = (bg, line, border)
        if look == self._look:
            return
        self._look = look
        self.body.configure(bg=bg, highlightbackground=border, highlightcolor=border)
        for frame in self.columns + list(self.goal_heads) + list(self.event_rows) + [self.buttons["pause"].master]:
            frame.configure(bg=bg)
        for line_frame in self.lines:
            line_frame.configure(bg=line)
        for column in self.columns:
            for child in column.winfo_children():
                if isinstance(child, ctk.CTkBaseClass):
                    child.configure(bg_color=bg)
        for frame in list(self.goal_heads) + list(self.event_rows) + [self.buttons["pause"].master]:
            for child in frame.winfo_children():
                child.configure(bg_color=bg)

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

    def _render_events(self, view):
        feed = view["feed"]
        key = (feed.version, len(feed.events), self.lang)
        if key == self._events_version:
            return
        self._events_version = key
        events = feed.latest()
        if not events:
            self.badge.grid_remove()
            self._set(self.event_text, "")
            self._set(self.event_time, "")
        else:
            name, color, bg = hud_events.badge(events[0], self.lang)
            self.badge.grid()
            self.badge.configure(text=name, text_color=color, fg_color=bg)
            self._set(self.event_time, events[0].time)
            self._set(self.event_text, self._fit(hud_events.text(events[0], self.lang), F["text"], name, events[0].time))
        if len(events) > 1:
            self._set(self.prev_time, events[1].time)
            self._set(self.prev_text, self._fit(hud_events.text(events[1], self.lang), F["label"], "", events[1].time))
        else:
            self._set(self.prev_text, "")
            self._set(self.prev_time, "")

    def _fit(self, text, font_spec, badge_text, time_text):
        """Обрезать текст с «…», чтобы он влез в колонку событий: иначе он раздвинул бы колонку (как в макете —
        text-overflow: ellipsis)."""
        scale = ctk.ScalingTracker.get_widget_scaling(self.status)
        font = self._font(font_spec, scale)
        small = self._font((theme.MONO_FAMILY, 11), scale)
        bold = self._font((theme.FONT_FAMILY, 11, "bold"), scale)
        room = (self._column_width or 400) - round((2 * PAD + 8) * scale) - small.measure(time_text)
        if badge_text:
            room -= bold.measure(badge_text) + round((12 + 8) * scale)
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
