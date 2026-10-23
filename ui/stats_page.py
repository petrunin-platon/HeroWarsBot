"""«Статистика активности» нового окна (задача 15, шаг 6; макет design/mockups/05_stats) — вместо ui/statistics_tab.py.

Сверху слева подсказка (выбран столбик — синяя плашка «Показан день: …» с ✕), справа «Период»: 7, 14, 30 дней,
«Всё время». Пять плиток: титанит, титанит сегодня, зелье, комнаты, этажи — за период или за выбранный столбик
(«Создано правил» и дневной нормы нет — ваши ответы 6.2). График по титаниту на обычном холсте Tk: шкала с сеткой
слева, без чисел над столбиками (ваше замечание: число видно при наведении и в плашке выбранного столбика).
Щелчок по столбику — он ярче, остальные бледнее, рядом плашка с титанитом; у недели — по дням, у месяца — по неделям.
Повторный щелчок или ✕ в синей плашке — снова итоги периода. «Таблица» — те же столбики таблицей.
Внизу «Ручная корректировка» (выбранный на графике день подставляется, даже если он старше 7 дней — ваш ответ)
и «Сбросить» — только после вопроса (в старой вкладке стирала всё без вопроса).

Расчёты — ui/stats_data.py (без Tk). Цифры читаются при каждом показе страницы (App._show_frame → refresh_data),
и график перерисовывается, только если цифры или размер поменялись (без мигания). Наведение меняет только цвета
на холсте, перерисовка по размеру окна — один раз после того, как размер перестал меняться.
"""
import math
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

import stats_manager
from i18n import get_text
from ui import stats_data, theme
from ui.widgets import Button, Card, ConfirmDialog, Dropdown, PlainLabel, Toast, Tooltip, plain_icon, scaled_font

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES
CH = theme.CHART_COLORS
BG = C["bg_surface"]
TILES = ("titanite", "today", "potions", "rooms", "floors")
TILE_KEYS = {"titanite": "st_titanite", "today": "st_today", "potions": "st_potions", "rooms": "st_rooms",
             "floors": "st_floors"}
REDRAW_MS = 60          # перерисовка по размеру — когда размер перестал меняться
BAR_SHARE = 0.62        # ширина столбика — доля его места
BAR_MAX = 64


def px(widget, value):
    return round(value * ctk.ScalingTracker.get_widget_scaling(widget))


def short_date(day):
    return day.strftime("%d.%m")


def bucket_label(bucket):
    """Подпись под столбиком: 18.10, 13–19.10 (29.09–05.10), 10.2026."""
    start, end = bucket["start"], bucket["end"]
    if bucket["kind"] == "day":
        return short_date(start)
    if bucket["kind"] == "month":
        return start.strftime("%m.%Y")
    if start == end:
        return short_date(start)
    if start.month == end.month:
        return f"{start.day:02d}–{short_date(end)}"
    return f"{short_date(start)}–{short_date(end)}"


def bucket_title(bucket):
    """Полная дата для плашек: 19.10.2026, 13.10–19.10.2026, 10.2026."""
    start, end = bucket["start"], bucket["end"]
    if bucket["kind"] == "month":
        return start.strftime("%m.%Y")
    if bucket["kind"] == "day" or start == end:
        return start.strftime("%d.%m.%Y")
    return f"{short_date(start)}–{end.strftime('%d.%m.%Y')}"


class BarChart(tk.Canvas):
    """График титанита: шкала слева, сетка, столбики, подписи снизу; наведение — число над столбиком;
    выбранный столбик — ярче, колонка под ним и плашка с цифрами. on_select(номер или None) — после щелчка."""

    def __init__(self, master, on_select, text):
        super().__init__(master, bg=BG, highlightthickness=0, bd=0)
        self.on_select = on_select
        self.text = text
        self.bars = []
        self.selected = None
        self.hovered = None
        self._geometry = None      # (x центров, ширина столбика, низ, верх графика, масштаб) после рисования
        self._drawn = None         # что нарисовано: (ширина, высота, ключ данных) — не рисовать то же второй раз
        self._redraw_id = None
        self.font = scaled_font(self, F["small"])
        self.font_bold = scaled_font(self, F["small_bold"])
        self.font_value = scaled_font(self, F["body_bold"])
        self._measure = tkfont.Font(root=self, font=self.font)
        self._measure_bold = tkfont.Font(root=self, font=self.font_bold)
        self.bind("<Configure>", self._resized, add="+")
        self.bind("<Motion>", self._motion, add="+")
        self.bind("<Leave>", lambda _e: self._hover(None), add="+")
        self.bind("<Button-1>", self._click, add="+")

    # ── Данные ──────────────────────────────────────────────────────────────
    def show(self, bars, selected=None):
        self.bars = bars
        self.selected = selected
        self.hovered = None
        self.redraw()

    def set_selected(self, index):
        """Выбрать столбик без перерисовки всего графика: только цвета, колонка и плашка."""
        self.selected = index
        if self._drawn is not None:
            self._drawn = self._drawn[:2] + (self._data_key(),)
        self._paint_selection()

    def _data_key(self):
        return tuple((b["start"], b["end"], b["titanite"]) for b in self.bars), self.selected, self.text("st_empty")

    def _resized(self, _event=None):
        if self._redraw_id:
            self.after_cancel(self._redraw_id)
        self._redraw_id = self.after(REDRAW_MS, self.redraw)

    def cancel(self):
        if self._redraw_id:
            try:
                self.after_cancel(self._redraw_id)
            except tk.TclError:
                pass
            self._redraw_id = None

    # ── Рисование ───────────────────────────────────────────────────────────
    def redraw(self, force=False):
        self._redraw_id = None
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        key = (w, h, self._data_key())
        if key == self._drawn and not force:
            return
        self._drawn = key
        self.delete("all")
        self.hovered = None
        values = [b["titanite"] for b in self.bars]
        ticks = stats_data.nice_ticks(max(values, default=0))
        labels = [stats_data.compact(t) for t in ticks]
        left = max(self._measure.measure(t) for t in labels) + px(self, 12)
        top, bottom, right = px(self, 22), px(self, 26), px(self, 6)
        plot_w, plot_h = max(10, w - left - right), max(10, h - top - bottom)
        base = top + plot_h
        scale = plot_h / ticks[-1]
        for value, label in zip(ticks, labels):
            y = base - value * scale
            self.create_line(left, y, w - right, y, fill=CH["grid"], dash=(2, 4) if value else ())
            self.create_text(left - px(self, 8), y, text=label, fill=CH["axis"], font=self.font, anchor="e")
        n = max(1, len(self.bars))
        slot = plot_w / n
        bar_w = max(3, min(slot * BAR_SHARE, px(self, BAR_MAX)))
        centers = [left + slot * (i + 0.5) for i in range(len(self.bars))]
        self._geometry = (centers, bar_w, slot, base, top, left, w - right)
        self.create_rectangle(0, 0, 0, 0, fill=CH["column"], outline="", state="hidden", tags="column")
        for i, (x, value) in enumerate(zip(centers, values)):
            height = value * scale
            if value > 0:
                height = max(height, 2)
            self.create_rectangle(x - bar_w / 2, base - height, x + bar_w / 2, base, fill=CH["bar"], outline="",
                                  width=0, tags=("bar", f"bar{i}"), state="normal" if value > 0 else "hidden")
        self._draw_labels(centers, slot, base)
        if not any(values):
            self.create_text(left + plot_w / 2, top + plot_h / 2, text=self.text("st_empty"), fill=C["text_muted"],
                             font=scaled_font(self, F["label"]))
        self.create_rectangle(0, 0, 0, 0, fill=CH["plate"], outline=CH["plate_border"], state="hidden",
                              tags="tip_bg")
        self.create_text(0, 0, text="", fill=C["text"], font=self.font_bold, state="hidden", tags="tip")
        self._paint_selection()

    def _draw_labels(self, centers, slot, base):
        """Подписи снизу. Не влезают все — через одну (две ...), последняя (сегодня) и выбранная — всегда."""
        texts = [bucket_label(b) for b in self.bars]
        widest = max((self._measure.measure(t) for t in texts), default=0) + px(self, 10)
        step = max(1, math.ceil(widest / max(slot, 1)))
        last = len(texts) - 1
        self._label_visible = [(last - i) % step == 0 for i in range(len(texts))]
        for i, (x, label) in enumerate(zip(centers, texts)):
            visible = self._label_visible[i]
            self.create_text(x, base + px(self, 13), text=label, font=self.font, fill=CH["label"],
                             tags=("label", f"label{i}"), state="normal" if visible else "hidden")

    def _paint_selection(self):
        self.delete("plate")
        if self._geometry is None:
            return
        centers, bar_w, slot, base, top, left, right = self._geometry
        sel = self.selected
        for i in range(len(self.bars)):
            color = CH["bar"] if sel is None else (CH["bar_hover"] if i == sel else CH["bar_dim"])
            self.itemconfigure(f"bar{i}", fill=color)
            label_color = CH["label_selected"] if i == sel or (sel is None and self.bars[i]["today"]) else CH["label"]
            self.itemconfigure(f"label{i}", fill=label_color, font=self.font_bold if i == sel else self.font,
                               state="normal" if i == sel or self._label_visible[i] else "hidden")
        if sel is None or sel >= len(self.bars):
            self.itemconfigure("column", state="hidden")
            return
        x = centers[sel]
        half = min(slot * 0.46, bar_w / 2 + px(self, 12))
        self.coords("column", x - half, top - px(self, 4), x + half, base)
        self.itemconfigure("column", state="normal")
        self.tag_lower("column")
        self._draw_plate(sel, x, bar_w, top, base, left, right)

    def _draw_plate(self, index, x, bar_w, top, base, left, right):
        """Плашка у выбранного столбика: дата, титанит; у недели — по дням, у месяца — по неделям."""
        bucket = self.bars[index]
        title = bucket_title(bucket) + (f" · {self.text('st_today_mark')}" if bucket["kind"] == "day"
                                        and bucket["today"] else "")
        rows = []
        if bucket["kind"] == "week" and len(bucket["days"]) > 1:
            rows = [(short_date(d), v) for d, v in bucket["per_day"]]
            head = self.text("st_per_day")
        elif bucket["kind"] == "month":
            weeks = {}
            for d, v in bucket["per_day"]:
                key = d.isocalendar()[:2]
                first, _last, total = weeks.get(key, (d, d, 0))
                weeks[key] = (first, d, total + v)
            rows = [(f"{short_date(a)}–{short_date(b)}" if a != b else short_date(a), v) for a, b, v in weeks.values()]
            head = self.text("st_per_week")
        pad, line, value_h, gap_rows = px(self, 12), px(self, 18), px(self, 24), px(self, 6)
        title_item = self.create_text(0, 0, text=title, fill=C["text_secondary"], font=self.font, anchor="nw",
                                      tags="plate")
        total = stats_data.full(bucket["titanite"])
        value_item = self.create_text(0, 0, text=total, fill=C["text"], font=self.font_value, anchor="nw",
                                      tags="plate")
        col_w = max(self._measure.measure(title), self._measure_bold.measure(total) + px(self, 8), px(self, 120))
        height = pad + line + value_h + pad
        per_col, row_items = 1, []
        if rows:
            head_item = self.create_text(0, 0, text=head, fill=C["text_muted"], font=self.font, anchor="nw",
                                         tags="plate")
            for label, v in rows:
                row_items.append((self.create_text(0, 0, text=label, font=self.font, anchor="nw", tags="plate",
                                                   fill=C["text_secondary"] if v else C["text_muted"]),
                                  self.create_text(0, 0, text=stats_data.full(v), font=self.font_bold, anchor="ne",
                                                   tags="plate", fill=C["text"] if v else C["text_muted"])))
            col_w = max(col_w, max(self._measure.measure(lbl) + self._measure_bold.measure(stats_data.full(v))
                                   for lbl, v in rows) + px(self, 24))
            room = (base - top) - height - gap_rows - line
            per_col = max(1, int(room // line))
            height += gap_rows + line + line * min(len(rows), per_col)
        columns = max(1, math.ceil(len(rows) / per_col)) if rows else 1
        width = col_w * columns + px(self, 16) * (columns - 1)
        box_w, box_h = width + pad * 2, height
        gap = px(self, 10)
        bx = x + bar_w / 2 + gap
        if bx + box_w > right:
            bx = x - bar_w / 2 - gap - box_w
        bx = max(left + 2, min(bx, right - box_w))
        by = top
        self.create_rectangle(bx, by, bx + box_w, by + box_h, fill=CH["plate"], outline=CH["plate_border"],
                              tags=("plate", "plate_bg"))
        self.tag_lower("plate_bg", title_item)
        cy = by + pad
        self.coords(title_item, bx + pad, cy)
        cy += line
        self.coords(value_item, bx + pad, cy)
        cy += value_h
        if rows:
            cy += gap_rows
            self.coords(head_item, bx + pad, cy)
            cy += line
            for n, (label_item, value_item) in enumerate(row_items):
                col, row = divmod(n, per_col)
                cx = bx + pad + col * (col_w + px(self, 16))
                self.coords(label_item, cx, cy + row * line)
                self.coords(value_item, cx + col_w, cy + row * line)

    # ── Мышь ────────────────────────────────────────────────────────────────
    def _index_at(self, x):
        if self._geometry is None or not self.bars:
            return None
        centers, _bar_w, slot, _base, _top, left, right = self._geometry
        if x < left or x > right:
            return None
        return min(len(self.bars) - 1, max(0, int((x - left) // slot)))

    def _motion(self, event):
        self._hover(self._index_at(event.x))

    def _hover(self, index):
        """Наведение: столбик чуть ярче, над ним число. Только цвета и место надписи на холсте."""
        if index == self.hovered or self._geometry is None:
            return
        old, self.hovered = self.hovered, index
        if old is not None and old != self.selected:
            color = CH["bar"] if self.selected is None else CH["bar_dim"]
            self.itemconfigure(f"bar{old}", fill=color)
        if index is None or not self.bars[index]["titanite"]:
            self.itemconfigure("tip", state="hidden")
            self.itemconfigure("tip_bg", state="hidden")
            return
        if index != self.selected:
            self.itemconfigure(f"bar{index}", fill=CH["bar_hover"])
        centers, _bar_w, _slot, base, top, _left, _right = self._geometry
        bar = self.coords(f"bar{index}")
        y = max(top - px(self, 10), (bar[1] if bar else base) - px(self, 12))
        self.itemconfigure("tip", text=stats_data.full(self.bars[index]["titanite"]), state="normal")
        self.coords("tip", centers[index], y)
        x1, y1, x2, y2 = self.bbox("tip")
        self.coords("tip_bg", x1 - 6, y1 - 2, x2 + 6, y2 + 2)
        self.itemconfigure("tip_bg", state="normal")
        self.tag_raise("tip_bg")
        self.tag_raise("tip")

    def _click(self, event):
        index = self._index_at(event.x)
        if index is None:
            return
        self.on_select(None if index == self.selected else index)


class Segments(tk.Frame):
    """«Период»: 7 дней | 14 дней | 30 дней | Всё время. Выбранный — синий. Обычные надписи Tk в скруглённой рамке."""

    def __init__(self, master, keys, value, command):
        super().__init__(master, bg=C["bg_primary"])
        self.box = Card(self, fg_color=BG, corner_radius=8, width=10, height=10)
        self.box.pack()
        inner = tk.Frame(self.box, bg=BG)
        inner.pack(padx=4, pady=4)
        self.value = value
        self.command = command
        self.items = {}
        for key in keys:
            label = tk.Label(inner, text="", bg=BG, fg=C["text_secondary"], font=scaled_font(self, F["button"]),
                             padx=px(self, 14), pady=px(self, 5), bd=0, highlightthickness=0, cursor="hand2")
            label.pack(side="left", padx=(0, 2))
            label.bind("<Button-1>", lambda _e, k=key: self._choose(k), add="+")
            label.bind("<Enter>", lambda _e, k=key: self._paint(k, hover=True), add="+")
            label.bind("<Leave>", lambda _e, k=key: self._paint(k), add="+")
            self.items[key] = label
        for key in keys:
            self._paint(key)

    def _paint(self, key, hover=False):
        label = self.items[key]
        if key == self.value:
            bg, fg = C["blue_button"], C["white"]
        else:
            bg, fg = (C["bg_elevated"] if hover else BG), (C["text"] if hover else C["text_secondary"])
        if label.cget("bg") != bg or label.cget("fg") != fg:
            label.configure(bg=bg, fg=fg)

    def _choose(self, key):
        if key == self.value:
            return
        old, self.value = self.value, key
        self._paint(old)
        self._paint(key)
        self.command(key)

    def set_texts(self, texts):
        for key, text in texts.items():
            if self.items[key].cget("text") != text:
                self.items[key].configure(text=text)


class StatsPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.controller = controller
        self.lang = getattr(controller, "current_lang", "RU")
        self.stats = None
        self.today = None
        self.period = stats_data.DEFAULT_PERIOD
        self.bars = []
        self.selected = None
        self.table_shown = False
        self._table_key = None
        self._dialog = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_top()
        self._build_tiles()
        self._build_chart()
        self._build_fix()
        self.update_language(self.lang)

    def text(self, key):
        return get_text(self.lang, key)

    def log(self, line):
        dash = self.controller.frames.get("dash") if hasattr(self.controller, "frames") else None
        if dash is not None:
            dash.append_log(line)

    # ── Постройка ───────────────────────────────────────────────────────────
    def _build_top(self):
        top = tk.Frame(self, bg=C["bg_primary"])
        top.grid(row=0, column=0, sticky="ew", pady=(0, S["gap_l"]))
        top.grid_columnconfigure(0, weight=1)
        self.hint = PlainLabel(top, "", font=F["label"], color=C["text_secondary"], bg=C["bg_primary"], anchor="w")
        self.hint.grid(row=0, column=0, sticky="w")
        # Синяя плашка «Показан день: … ✕» — щелчок по ней возвращает итоги периода
        self.chip = tk.Frame(top, bg=T["blue_on_surface"], highlightthickness=1,
                             highlightbackground=T["nav_active_border"], cursor="hand2")
        self._chip_icon = plain_icon(self, "calendar", C["blue_text"], 14)
        self._chip_x = plain_icon(self, "x", C["blue_text"], 13)
        parts = [tk.Label(self.chip, image=self._chip_icon, bg=T["blue_on_surface"], bd=0),
                 PlainLabel(self.chip, "", font=F["label_bold"], color=C["blue_text"], bg=T["blue_on_surface"]),
                 tk.Label(self.chip, image=self._chip_x, bg=T["blue_on_surface"], bd=0)]
        self.chip_label = parts[1]
        for i, part in enumerate(parts):
            part.pack(side="left", padx=(px(self, 10) if i == 0 else px(self, 6), px(self, 10) if i == 2 else 0),
                      pady=px(self, 5))
        for widget in [self.chip] + parts:
            widget.bind("<Button-1>", lambda _e: self.select(None), add="+")
        right = tk.Frame(top, bg=C["bg_primary"])
        right.grid(row=0, column=1, sticky="e")
        self.period_label = PlainLabel(right, "", font=F["label"], color=C["text_secondary"], bg=C["bg_primary"])
        self.period_label.pack(side="left", padx=(0, px(self, 10)))
        self.segments = Segments(right, stats_data.PERIODS, self.period, self._period_chosen)
        self.segments.pack(side="left")

    def _build_tiles(self):
        row = tk.Frame(self, bg=C["bg_primary"])
        row.grid(row=1, column=0, sticky="ew", pady=(0, S["gap_l"]))
        self.tiles = {}
        self.tile_values = {}
        for i, name in enumerate(TILES):
            row.grid_columnconfigure(i, weight=1, uniform="tile")
            card = Card(row, width=10, height=10)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0 if i == len(TILES) - 1 else 6))
            inner = tk.Frame(card, bg=BG)
            inner.pack(fill="x", padx=px(self, 14), pady=px(self, 12))
            head = tk.Frame(inner, bg=BG)
            head.pack(fill="x")
            icon_name, color = theme.STAT_TILES[name]
            picture = plain_icon(self, icon_name, color, 15)
            icon_label = tk.Label(head, image=picture, bg=BG, bd=0)
            icon_label.image = picture
            icon_label.pack(side="left")
            title = PlainLabel(head, "", font=F["label"], color=C["text_secondary"], anchor="w")
            title.pack(side="left", padx=(px(self, 6), 0))
            value = PlainLabel(inner, "0", font=(theme.MONO_FAMILY, 22, "bold"), color=C["text"], anchor="w")
            value.pack(fill="x", pady=(px(self, 6), 0))
            self.tiles[name] = (title, value)
            # Сокращённое число (105.5K) — полностью в подсказке при наведении на плитку
            tip = Tooltip(card, lambda n=name: stats_data.full(self.tile_values.get(n, 0)))
            for part in (inner, head, icon_label, title, value):
                tip.attach(part)

    def _build_chart(self):
        card = Card(self, width=10, height=10)
        card.grid(row=2, column=0, sticky="nsew", pady=(0, S["gap_l"]))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        head = tk.Frame(card, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=px(self, 16), pady=(px(self, 12), px(self, 4)))
        head.grid_columnconfigure(2, weight=1)
        self.chart_title = PlainLabel(head, "", font=F["card_title"], color=C["text"])
        self.chart_title.grid(row=0, column=0, sticky="w")
        self.chart_sub = PlainLabel(head, "", font=F["label"], color=C["text_muted"])
        self.chart_sub.grid(row=0, column=1, sticky="w", padx=(px(self, 8), 0))
        self.table_button = Button(head, "", kind="secondary", icon_name="table", icon_size=14, height=30,
                                   pad_x=10, command=self.toggle_table)
        self.table_button.grid(row=0, column=3, sticky="e")
        self.body = tk.Frame(card, bg=BG)
        self.body.grid(row=1, column=0, sticky="nsew", padx=px(self, 12), pady=(0, px(self, 10)))
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.chart = BarChart(self.body, self.select, self.text)
        self.chart.grid(row=0, column=0, sticky="nsew")
        self.table = tk.Frame(self.body, bg=BG)

    def _build_fix(self):
        card = Card(self, width=10, height=10)
        card.grid(row=3, column=0, sticky="ew")
        inner = tk.Frame(card, bg=BG)
        inner.pack(fill="x", padx=px(self, 16), pady=px(self, 12))
        inner.grid_columnconfigure(4, weight=1)
        self.fix_title = PlainLabel(inner, "", font=F["card_title"], color=C["text"])
        self.fix_title.grid(row=0, column=0, sticky="w", padx=(0, px(self, 14)))
        self.fix_day = Dropdown(inner, [], "", icons={}, width=210, command=self._fix_day_chosen)
        self.fix_day.grid(row=0, column=1, sticky="w")
        self.fix_label = PlainLabel(inner, "", font=F["label"], color=C["text_secondary"])
        self.fix_label.grid(row=0, column=2, sticky="w", padx=(px(self, 16), px(self, 10)))
        self.fix_entry = ctk.CTkEntry(inner, width=96, height=S["control_height"], corner_radius=S["radius_control"],
                                      border_width=1, border_color=C["border"], fg_color=C["bg_elevated"],
                                      text_color=C["text"], font=F["mono_field"])
        self.fix_entry.grid(row=0, column=3, sticky="w")
        self.fix_entry.bind("<Return>", lambda _e: self.apply_fix(), add="+")
        self.fix_entry.bind("<KeyRelease>", lambda _e: self._entry_error(False), add="+")
        self._entry_bad = False
        self.apply_button = Button(inner, "", kind="save", command=self.apply_fix)
        self.apply_button.grid(row=0, column=5, sticky="e", padx=(0, px(self, 8)))
        self.reset_button = Button(inner, "", kind="ghost_danger", icon_name="trash-2", icon_size=15,
                                   command=self.ask_reset)
        self.reset_button.grid(row=0, column=6, sticky="e")

    # ── Язык ────────────────────────────────────────────────────────────────
    def update_language(self, lang):
        self.lang = lang
        self.period_label.configure(text=self.text("st_period"))
        self.segments.set_texts({p: self.text(f"st_p_{p}") for p in stats_data.PERIODS})
        for name, (title, _value) in self.tiles.items():
            title.configure(text=self.text(TILE_KEYS[name]))
        self.chart_title.configure(text=self.text("st_chart"))
        self.fix_title.configure(text=self.text("st_fix"))
        self.fix_label.configure(text=self.text("st_fix_value"))
        self.apply_button.configure(text=self.text("st_apply"))
        self.reset_button.configure(text=self.text("st_reset"))
        self._show_table_button()
        if self.stats is not None:
            self._show_all(force=True)

    # ── Данные ──────────────────────────────────────────────────────────────
    def refresh_data(self):
        """Прочитать bot_data/stats.json (при каждом показе страницы). Цифры те же — ничего не перерисовывается."""
        stats = stats_manager.load_stats()
        today = stats_data.today_of(stats_manager.get_game_datetime())
        if stats == self.stats and today == self.today:
            return
        self.stats, self.today = stats, today
        self._recalc()

    def _recalc(self):
        old = self.bars[self.selected]["start"] if self.selected is not None and self.selected < len(self.bars) else None
        self.bars = stats_data.buckets(self.stats, self.period, self.today)
        self.selected = next((i for i, b in enumerate(self.bars) if b["start"] == old), None)
        self._show_all()

    def _show_all(self, force=False):
        self._show_top()
        self._show_tiles()
        kind = self.bars[0]["kind"] if self.bars else "day"
        self.chart_sub.configure(text="· " + self.text(f"st_by_{kind}"))
        if self.table_shown:
            self._show_table(force=force)
        else:
            self.chart.show(self.bars, self.selected)
            if force:
                self.chart.redraw(force=True)
        self._fill_fix_days()

    def _show_top(self):
        if self.selected is None:
            self.chip.grid_forget()
            self.hint.configure(text=self.text("st_hint"))
            self.hint.grid(row=0, column=0, sticky="w")
        else:
            bucket = self.bars[self.selected]
            key = {"day": "st_shown_day", "week": "st_shown_week", "month": "st_shown_month"}[bucket["kind"]]
            title = bucket_title(bucket)
            if bucket["kind"] == "day" and bucket["today"]:
                title += f" · {self.text('st_today_mark')}"
            self.chip_label.configure(text=self.text(key).format(date=title))
            self.hint.grid_forget()
            self.chip.grid(row=0, column=0, sticky="w")

    def _show_tiles(self):
        if self.selected is not None:
            bucket = self.bars[self.selected]
            values = {m: bucket[m] for m in stats_data.METRICS}
            values["today"] = stats_data.day_titanite(self.stats, self.today)
        else:
            values = stats_data.totals(self.stats, self.period, self.today, bars=self.bars)
        for name, (_title, label) in self.tiles.items():
            self.tile_values[name] = values.get(name, 0)
            text = stats_data.tile_number(self.tile_values[name])
            if label.cget("text") != text:
                label.configure(text=text)

    def _period_chosen(self, period):
        self.period = period
        self.selected = None
        self._recalc()

    def select(self, index):
        """Выбрать столбик (None — снова итоги периода). Дневной столбик подставляется в ручную корректировку."""
        if index == self.selected:
            return
        self.selected = index
        self._show_top()
        self._show_tiles()
        if self.table_shown:
            self._paint_table_selection()
        else:
            self.chart.set_selected(index)
        if index is not None and self.bars[index]["kind"] == "day":
            day = self.bars[index]["start"]
            self._fill_fix_days(day)
            self.fix_day.set(stats_data.day_key(day))
            self._set_entry(self.bars[index]["titanite"])

    # ── Таблица ─────────────────────────────────────────────────────────────
    def _show_table_button(self):
        if self.table_shown:
            self.table_button.configure(text=self.text("st_graph"))
            self.table_button.set_icon("chart-no-axes-column")
        else:
            self.table_button.configure(text=self.text("st_table"))
            self.table_button.set_icon("table")

    def toggle_table(self):
        self.table_shown = not self.table_shown
        self._show_table_button()
        if self.table_shown:
            self.chart.grid_forget()
            self.table.grid(row=0, column=0, sticky="nsew")
            self._show_table()
        else:
            self.table.grid_forget()
            self.chart.grid(row=0, column=0, sticky="nsew")
            self.chart.show(self.bars, self.selected)

    def _show_table(self, force=False):
        """Таблица строится заново, только если поменялись цифры, период или язык."""
        key = (tuple((b["start"], b["end"]) + tuple(b[m] for m in stats_data.METRICS) for b in self.bars), self.lang)
        if key == self._table_key and not force:
            self._paint_table_selection()
            return
        self._table_key = key
        for child in self.table.winfo_children():
            child.destroy()
        cols = [("st_col_date", "w")] + [(TILE_KEYS[m], "e") for m in stats_data.METRICS]
        for c in range(len(cols)):
            self.table.grid_columnconfigure(c, weight=1, uniform="col")
        for c, (key_name, anchor) in enumerate(cols):
            PlainLabel(self.table, self.text(key_name), font=F["label"], color=C["text_muted"], anchor=anchor).grid(
                row=0, column=c, sticky="ew", ipadx=px(self, 8), pady=(px(self, 4), px(self, 6)))
        self.table_rows = []
        for r, bucket in enumerate(reversed(self.bars)):
            index = len(self.bars) - 1 - r
            title = bucket_title(bucket) + (f" · {self.text('st_today_mark')}" if bucket["kind"] == "day"
                                            and bucket["today"] else "")
            cells = [PlainLabel(self.table, title, font=F["label"], color=C["text_secondary"], anchor="w")]
            cells += [PlainLabel(self.table, stats_data.full(bucket[m]), font=F["mono"],
                                 color=C["text"] if bucket[m] else C["text_muted"], anchor="e")
                      for m in stats_data.METRICS]
            for c, cell in enumerate(cells):
                cell.grid(row=r + 1, column=c, sticky="ew", ipadx=px(self, 8), ipady=px(self, 2))
                cell.bind("<Button-1>", lambda _e, i=index: self.select(None if i == self.selected else i), add="+")
            self.table_rows.append((index, cells))
        tk.Frame(self.table, height=1, bg=C["border"]).grid(row=len(self.bars) + 1, column=0,
                                                            columnspan=len(cols), sticky="ew", pady=px(self, 4))
        totals = stats_data.totals(self.stats, self.period, self.today, bars=self.bars)
        cells = [PlainLabel(self.table, self.text("st_total"), font=F["label_bold"], color=C["text"], anchor="w")]
        cells += [PlainLabel(self.table, stats_data.full(totals[m]), font=(theme.MONO_FAMILY, 12, "bold"),
                             color=C["text"], anchor="e") for m in stats_data.METRICS]
        for c, cell in enumerate(cells):
            cell.grid(row=len(self.bars) + 2, column=c, sticky="ew", ipadx=px(self, 8), ipady=px(self, 2))
        self._paint_table_selection()

    def _paint_table_selection(self):
        for index, cells in getattr(self, "table_rows", []):
            bg = T["blue_on_surface"] if index == self.selected else BG
            for cell in cells:
                if cell.cget("bg") != bg:
                    cell.configure(bg=bg)

    # ── Ручная корректировка ────────────────────────────────────────────────
    def _fill_fix_days(self, extra=None):
        if self.today is None:
            return
        current = stats_data.parse_day(self.fix_day.get())
        days = stats_data.correction_days(self.today, extra or (current if current else None))
        items = []
        for i, day in enumerate(days):
            key = stats_data.day_key(day)
            if i == 0:
                items.append((key, self.text("st_fix_today").format(date=key)))
            elif i == 1:
                items.append((key, self.text("st_fix_yesterday").format(date=key)))
            else:
                items.append((key, key))
        self.fix_day.icons = {k: ("calendar", C["text_secondary"]) for k, _t in items}
        if items != self.fix_day.items:
            self.fix_day.set_items(items)
        if self.fix_day.get() not in [k for k, _t in items]:
            self.fix_day.set(items[0][0])
            self._set_entry(self._day_titanite(items[0][0]))

    def _day_titanite(self, key):
        return int(((self.stats or {}).get("daily") or {}).get(key, {}).get("titanite", 0) or 0)

    def _fix_day_chosen(self, key):
        self._set_entry(self._day_titanite(key))

    def _set_entry(self, value):
        self.fix_entry.delete(0, "end")
        self.fix_entry.insert(0, str(value))
        self._entry_error(False)

    def _entry_error(self, bad):
        if bad == self._entry_bad:
            return
        self._entry_bad = bad
        self.fix_entry.configure(border_color=C["danger"] if bad else C["border"],
                                 fg_color=T["field_error_bg"] if bad else C["bg_elevated"])

    def apply_fix(self):
        """«Применить» — как старая вкладка: титанит за день, комнаты, этажи и зелье по нему; не меньше, чем бот сам."""
        day = self.fix_day.get()
        total = stats_data.parse_total(self.fix_entry.get())
        if total is None:
            self._entry_error(True)
            Toast(self, self.text("st_fix_bad"), kind="error")
            return
        result, info = stats_data.correction(stats_manager.load_stats(), day, total)
        if result == "below_bot":
            self._entry_error(True)
            self.log(f"[СТАТИСТИКА] ОШИБКА: За {day} бот сам собрал {info} титанита. "
                     f"Нельзя указать значение меньше этой суммы!\n")
            Toast(self, self.text("st_fix_below").format(n=stats_data.full(info)), kind="error")
            return
        if result == "same":
            self.log("[СТАТИСТИКА] Синхронизация не требуется. Данные актуальны.\n")
            Toast(self, self.text("st_fix_same"), kind="info")
            return
        for metric, amount in info.items():
            stats_manager.add_metric(metric, amount, date_str=day)
        sign = "+" if info["titanite"] > 0 else ""
        self.log(f"[СТАТИСТИКА] Данные за {day} синхронизированы! Дельта: {sign}{info['titanite']} тит., "
                 f"{sign}{info.get('rooms', 0)} комн., {sign}{info.get('potions', 0)} зелий.\n")
        Toast(self, self.text("st_fix_done").format(date=day, total=stats_data.full(total)))
        self.refresh_data()

    def ask_reset(self):
        if self._dialog is not None and not self._dialog.done:
            self._dialog.lift()
            return
        self._dialog = ConfirmDialog(self, self.text("st_reset_title"), self.text("st_reset_text"),
                                     self.text("st_reset"), on_confirm=self.reset, kind="danger", lang=self.lang)

    def reset(self):
        stats_manager.reset_stats()
        self.log("[СТАТИСТИКА] Вся история полностью сброшена!\n")
        Toast(self, self.text("st_reset_done"), kind="deleted")
        self.selected = None
        self.refresh_data()

    def destroy(self):
        self.chart.cancel()
        super().destroy()
