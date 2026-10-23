"""«Аналитика» нового окна (задача 15, шаг 6; макет design/mockups/04_analytics) — вместо ui/analytics_tab.py.

Три плитки: всего боёв в истории, средний винрейт (с кольцом), найдено «золотых правил». Слева «Золотые правила» —
карточки с галочками (стихия, сколько боёв, враги → пак, винрейт) и «Выбрать все»; пока анализа не было —
«Золотых правил пока нет». Справа «Ход анализа»: что делает анализ и подробный отчёт старой вкладки — все паки против
каждого состава врагов (ваш ответ 5.1). Внизу «Последний анализ: …», «Запустить анализ логов» и
«Внедрить золотые правила (N)» — N отмеченных.

Что считать и что записывать — ui/analytics_data.py (без Tk): золотые правила — как у бота (ваш ответ 5.2).
Анализ — в фоновом потоке (история бывает большой), ответ окно забирает через after; кнопка на это время выключена.
Отчёт вставляется в «Ход анализа» одним куском (а не строками по одной). Внедрение пишет только файлы стихий,
где есть выбранные правила, по одному разу. Окно мастера правил увидит их при следующем показе (RulesPage._mapped).
"""
import queue
import threading
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

import data_paths
from i18n import get_text
from ui import analytics_data, theme
from ui.widgets import Button, Card, PlainLabel, TitanTile, Toast, plain_icon, scaled_font, titan_name

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES
BG = C["bg_surface"]
POLL_MS = 100
TAG_KEYS = {"system": "an_tag_system", "ml": "an_tag_ml", "done": "an_tag_done", "error": "an_tag_error"}
STATUS_KEYS = {"in_base": "an_st_in_base", "perfect": "an_st_perfect", "average": "an_st_average",
               "danger": "an_st_danger"}


def px(widget, value):
    return round(value * ctk.ScalingTracker.get_widget_scaling(widget))


def room_name(lang, room):
    return theme.plain_text(get_text(lang, f"elem_{room}"))


def names(lang, titans):
    return ", ".join(titan_name(lang, t) for t in titans)


class Ring(tk.Canvas):
    """Кольцо винрейта (макет: серое кольцо, зелёная дуга по проценту)."""

    def __init__(self, master, size=44):
        self.size = px(master, size)
        super().__init__(master, width=self.size, height=self.size, bg=BG, highlightthickness=0, bd=0)
        self.value = None
        self.set(0)

    def set(self, percent):
        if percent == self.value:
            return
        self.value = percent
        self.delete("all")
        w = px(self, 5)
        box = (w, w, self.size - w, self.size - w)
        self.create_oval(*box, outline=C["bg_elevated"], width=w)
        if percent > 0:
            self.create_arc(*box, start=90, extent=-min(359.9, 3.6 * percent), style="arc", outline=C["success"],
                            width=w)


class Check(tk.Label):
    """Галочка карточки: квадрат 18 px, отмечена — синяя с белой галочкой. Картинки — одни на окно."""

    def __init__(self, master, on, command):
        super().__init__(master, bg=master.cget("bg"), bd=0, highlightthickness=0, cursor="hand2")
        self.pictures = {True: plain_icon(self, "check", C["white"], 13, box=20, tint=C["blue_button"], bg=BG,
                                          radius=5),
                         False: plain_icon(self, "square", C["border_strong"], 20, bg=BG)}
        self.on = on
        self.command = command
        self.configure(image=self.pictures[on])
        self.bind("<Button-1>", lambda _e: self.toggle(), add="+")

    def toggle(self):
        self.set(not self.on)
        self.command()

    def set(self, on):
        if on != self.on:
            self.on = on
            self.configure(image=self.pictures[on])


class GoldenCard(tk.Frame):
    """Карточка золотого правила: галочка, стихия, «боёв: N», враги → пак, винрейт. Рамка синяя, пока отмечена."""

    def __init__(self, master, gold, lang, on, command):
        super().__init__(master, bg=BG, highlightthickness=1, highlightbackground=C["border"])
        self.gold = gold
        inner = tk.Frame(self, bg=BG)
        inner.pack(fill="x", padx=px(self, 12), pady=px(self, 10))
        inner.grid_columnconfigure(2, weight=1)
        self.check = Check(inner, on, lambda: (self._paint(), command()))
        self.check.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, px(self, 12)))
        room = gold["room"]
        style = theme.element_style(room)
        head = tk.Frame(inner, bg=BG)
        head.grid(row=0, column=1, columnspan=2, sticky="w")
        badge = tk.Label(head, text=room_name(lang, room), bg=theme.blend(style["color"], BG, 0.18),
                         fg=style["text"], font=scaled_font(self, F["small_bold"]), padx=px(self, 7), pady=px(self, 1))
        badge.pack(side="left")
        PlainLabel(head, get_text(lang, "an_fights").format(n=gold["battles"]), font=F["small"],
                   color=C["text_muted"]).pack(side="left", padx=(px(self, 8), 0))
        line = tk.Frame(inner, bg=BG)
        line.grid(row=1, column=1, columnspan=2, sticky="w", pady=(px(self, 8), 0))
        for titan in gold["enemies"]:
            TitanTile(line, titan, lang=lang, size=S["avatar_small"], bg=BG).pack(side="left", padx=(0, px(self, 3)))
        self._arrow = plain_icon(self, "arrow-right", C["text_muted"], 14)
        tk.Label(line, image=self._arrow, bg=BG, bd=0).pack(side="left", padx=px(self, 6))
        for titan in gold["team"]:
            TitanTile(line, titan, lang=lang, size=S["avatar_small"], bg=BG).pack(side="left", padx=(0, px(self, 3)))
        rate = tk.Frame(inner, bg=BG)
        rate.grid(row=0, column=3, rowspan=2, sticky="e", padx=(px(self, 8), 0))
        PlainLabel(rate, f"{gold['wins'] * 100 / gold['battles']:.0f}%", font=(theme.MONO_FAMILY, 18, "bold"),
                   color=C["gold"]).pack(anchor="e")
        PlainLabel(rate, get_text(lang, "an_winrate_short"), font=F["small"], color=C["text_muted"]).pack(anchor="e")
        for widget in (self, inner, head, line, rate):
            widget.bind("<Button-1>", lambda _e: self.check.toggle(), add="+")
        self._paint()

    def _paint(self):
        color = T["nav_active_border"] if self.check.on else C["border"]
        if self.cget("highlightbackground") != color:
            self.configure(highlightbackground=color)

    @property
    def on(self):
        return self.check.on

    def set(self, on):
        self.check.set(on)
        self._paint()


class AnalyticsPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.controller = controller
        self.lang = getattr(controller, "current_lang", "RU")
        self.result = None
        self.golden = []
        self.cards = []
        self.checked = set()     # отмеченные золотые правила (id записи)
        self.last_run = None
        self.running = False
        self._answers = queue.Queue()
        self._poll_id = None
        self._console_lines = [("system", "an_log_loaded", {}), ("system", "an_log_waiting", {})]
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_tiles()
        self._build_middle()
        self._build_footer()
        self.update_language(self.lang)

    def text(self, key):
        return get_text(self.lang, key)

    # ── Постройка ───────────────────────────────────────────────────────────
    def _build_tiles(self):
        row = tk.Frame(self, bg=C["bg_primary"])
        row.grid(row=0, column=0, sticky="ew", pady=(0, S["gap_l"]))
        self.tiles = {}
        specs = (("battles", "swords", C["blue_text"], T["blue_icon_bg"]), ("winrate", None, None, None),
                 ("golden", "star", C["gold"], T["gold_on_surface"]))
        for i, (name, icon_name, color, tint) in enumerate(specs):
            row.grid_columnconfigure(i, weight=1, uniform="tile")
            card = Card(row, width=10, height=10)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0 if i == 2 else 8))
            inner = tk.Frame(card, bg=BG)
            inner.pack(fill="x", padx=px(self, 18), pady=px(self, 16))
            if icon_name:
                picture = plain_icon(self, icon_name, color, 20, box=44, tint=tint, bg=BG, radius=10)
                art = tk.Label(inner, image=picture, bg=BG, bd=0)
                art.image = picture
            else:
                art = self.ring = Ring(inner)
            art.pack(side="left")
            text = tk.Frame(inner, bg=BG)
            text.pack(side="left", padx=(px(self, 14), 0), fill="x")
            title = PlainLabel(text, "", font=F["label"], color=C["text_secondary"], anchor="w")
            title.pack(anchor="w")
            value = PlainLabel(text, "0", font=(theme.MONO_FAMILY, 22, "bold"),
                               color=C["gold"] if name == "golden" else C["text"], anchor="w")
            value.pack(anchor="w", pady=(px(self, 4), 0))
            self.tiles[name] = (title, value)

    def _build_middle(self):
        middle = tk.Frame(self, bg=C["bg_primary"])
        middle.grid(row=1, column=0, sticky="nsew", pady=(0, S["gap_l"]))
        middle.grid_rowconfigure(0, weight=1)
        middle.grid_columnconfigure(0, weight=11, uniform="mid")
        middle.grid_columnconfigure(1, weight=9, uniform="mid")
        # «Золотые правила»
        left = Card(middle, width=10, height=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        head = tk.Frame(left, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=px(self, 16), pady=(px(self, 14), px(self, 10)))
        head.grid_columnconfigure(2, weight=1)
        self.golden_title = PlainLabel(head, "", font=F["card_title"], color=C["text"])
        self.golden_title.grid(row=0, column=0, sticky="w")
        self.golden_hint = PlainLabel(head, "", font=F["label"], color=C["text_muted"])
        self.golden_hint.grid(row=0, column=1, sticky="w", padx=(px(self, 8), 0))
        self.select_all = Button(head, "", kind="link", height=26, pad_x=6, command=self.toggle_all)
        self.select_all.grid(row=0, column=3, sticky="e")
        self.select_all.grid_remove()
        self.list_area = tk.Frame(left, bg=BG)
        self.list_area.grid(row=1, column=0, sticky="nsew", padx=px(self, 16), pady=(0, px(self, 16)))
        self.list_area.grid_rowconfigure(0, weight=1)
        self.list_area.grid_columnconfigure(0, weight=1)
        self.empty = tk.Frame(self.list_area, bg=BG, highlightthickness=1, highlightbackground=C["border_focus"])
        self.empty.grid(row=0, column=0, sticky="nsew")
        center = tk.Frame(self.empty, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")
        star = plain_icon(self, "star", C["gold"], 20, box=48, tint=T["gold_on_surface"], bg=BG, radius=10)
        art = tk.Label(center, image=star, bg=BG, bd=0)
        art.image = star
        art.pack()
        self.empty_title = PlainLabel(center, "", font=F["body_bold"], color=C["text"])
        self.empty_title.pack(pady=(px(self, 14), px(self, 6)))
        self.empty_text = PlainLabel(center, "", font=F["label"], color=C["text_secondary"], justify="center",
                                     wraplength=px(self, 360))
        self.empty_text.pack()
        self.scroll = ctk.CTkScrollableFrame(self.list_area, fg_color=BG, corner_radius=0,
                                             scrollbar_button_color=C["border_strong"],
                                             scrollbar_button_hover_color=C["border_focus"])
        self.scroll.grid_columnconfigure(0, weight=1)
        # «Ход анализа»
        right = Card(middle, width=10, height=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        head = tk.Frame(right, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=px(self, 16), pady=(px(self, 14), px(self, 10)))
        picture = plain_icon(self, "terminal", C["text_secondary"], 16)
        icon_label = tk.Label(head, image=picture, bg=BG, bd=0)
        icon_label.image = picture
        icon_label.pack(side="left")
        self.console_title = PlainLabel(head, "", font=F["card_title"], color=C["text"])
        self.console_title.pack(side="left", padx=(px(self, 8), 0))
        box = ctk.CTkTextbox(right, fg_color=C["bg_primary"], border_width=1, border_color=C["border"],
                             corner_radius=8, font=F["mono"], text_color=C["text"], wrap="word",
                             scrollbar_button_color=C["border_strong"], activate_scrollbars=True)
        box.grid(row=1, column=0, sticky="nsew", padx=px(self, 16), pady=(0, px(self, 16)))
        self.console = box
        box.tag_config("line", spacing1=2, spacing3=2)
        for key, color in theme.ANALYSIS_TAGS.items():
            box.tag_config(f"t_{key}", foreground=color)
        for key, color in theme.REPORT_STATUS_COLORS.items():
            box.tag_config(f"s_{key}", foreground=color)
        box.tag_config("muted", foreground=C["text_muted"])
        box.tag_config("head", foreground=C["text"])
        box.configure(state="disabled")

    def _build_footer(self):
        card = Card(self, width=10, height=10)
        card.grid(row=2, column=0, sticky="ew")
        inner = tk.Frame(card, bg=BG)
        inner.pack(fill="x", padx=px(self, 16), pady=px(self, 12))
        inner.grid_columnconfigure(2, weight=1)
        self.last_label = PlainLabel(inner, "", font=F["label"], color=C["text_secondary"])
        self.last_label.grid(row=0, column=0, sticky="w")
        self.last_value = PlainLabel(inner, "", font=F["label_bold"], color=C["text"])
        self.last_value.grid(row=0, column=1, sticky="w", padx=(px(self, 4), 0))
        self.run_button = Button(inner, "", kind="blue", icon_name="search", icon_size=15, height=38,
                                 command=self.run_analysis)
        self.run_button.grid(row=0, column=3, sticky="e", padx=(0, px(self, 10)))
        self.apply_button = Button(inner, "", kind="save", icon_name="check", icon_size=15, height=38,
                                   command=self.apply_golden)
        self.apply_button.grid(row=0, column=4, sticky="e")
        self.apply_button.set_enabled(False)

    # ── Язык и вид ──────────────────────────────────────────────────────────
    def update_language(self, lang):
        self.lang = lang
        for name, key in (("battles", "an_total"), ("winrate", "an_winrate"), ("golden", "an_golden")):
            self.tiles[name][0].configure(text=self.text(key))
        self.golden_title.configure(text=self.text("an_golden_title"))
        self.golden_hint.configure(text=self.text("an_golden_hint"))
        self.select_all.configure(text=self.text("an_select_all"))
        self.console_title.configure(text=self.text("an_console"))
        self.last_label.configure(text=self.text("an_last"))
        self._show_last()
        self._show_counts()
        self._show_buttons()
        self._show_golden()
        self._render_console()

    def _show_last(self):
        if self.last_run is None:
            text = self.text("an_never")
        elif self.last_run.date() == datetime.now().date():
            text = self.text("an_today_at").format(time=self.last_run.strftime("%H:%M"))
        else:
            text = self.last_run.strftime("%d.%m.%Y, %H:%M")
        self.last_value.configure(text=text)

    def _show_counts(self):
        result = self.result or {}
        battles = result.get("battles", 0)
        winrate = result.get("winrate", 0.0)
        self.tiles["battles"][1].configure(text=f"{battles:,}".replace(",", " "))
        self.tiles["winrate"][1].configure(text=f"{winrate:.1f}%")
        self.tiles["golden"][1].configure(text=str(len(self.golden)))
        self.ring.set(round(winrate, 1))

    def _chosen(self):
        return [g for g in self.golden if id(g) in self.checked]

    def _show_buttons(self):
        self.run_button.configure(text=self.text("an_running" if self.running else "an_run"))
        self.run_button.set_enabled(not self.running)
        count = len(self._chosen())
        self.apply_button.configure(text=self.text("an_apply") + (f" ({count})" if count else ""))
        self.apply_button.set_enabled(bool(count) and not self.running)

    def _show_golden(self):
        """Карточки золотых правил строятся заново только после анализа и смены языка (их немного)."""
        for card in self.cards:
            card.destroy()
        self.cards = []
        if not self.golden:
            self.scroll.grid_remove()
            self.select_all.grid_remove()
            self.empty.grid(row=0, column=0, sticky="nsew")
            done = self.result is not None
            self.empty_title.configure(text=self.text("an_none_title" if done else "an_empty_title"))
            self.empty_text.configure(text=self.text("an_none_text" if done else "an_empty_text"))
            return
        self.empty.grid_remove()
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.select_all.grid()
        for i, gold in enumerate(self.golden):
            card = GoldenCard(self.scroll, gold, self.lang, id(gold) in self.checked, self._card_toggled)
            card.grid(row=i, column=0, sticky="ew", pady=(0, px(self, 8)))
            self.cards.append(card)

    def _card_toggled(self):
        self.checked = {id(card.gold) for card in self.cards if card.on}
        self._show_buttons()

    def toggle_all(self):
        on = not all(card.on for card in self.cards)
        for card in self.cards:
            card.set(on)
        self._card_toggled()

    # ── «Ход анализа» ───────────────────────────────────────────────────────
    def _say(self, tag, key, **values):
        self._console_lines.append((tag, key, values))

    def _render_console(self):
        """Весь «Ход анализа» одним куском (и на новом языке): строки и отчёт хранятся как ключи и цифры."""
        chunks = []
        for tag, key, values in self._console_lines:
            if tag == "report":
                chunks.extend(self._report_chunks())
                continue
            chunks.append((f"[{self.text(TAG_KEYS[tag])}] ", f"t_{tag}"))
            chunks.append((self.text(key).format(**values) + "\n", "line"))
        box = self.console
        box.configure(state="normal")
        box.delete("1.0", "end")
        for text, tag in chunks:
            box.insert("end", text, (tag, "line") if tag != "line" else ("line",))
        box.configure(state="disabled")
        box.see("end")

    def _report_chunks(self):
        """Подробный отчёт старой вкладки: стихия и враги, под ними паки от лучших."""
        chunks = [("\n" + self.text("an_rep_title") + "\n", "head")]
        for scenario in self.result.get("scenarios", []):
            chunks.append(("\n" + room_name(self.lang, scenario["room"]).upper() + "\n", "head"))
            chunks.append((f'{self.text("an_rep_enemies")}: {names(self.lang, scenario["enemies"])}\n', "muted"))
            for pack in scenario["packs"]:
                chunks.append((f'  {self.text(STATUS_KEYS[pack["status"]])}', f's_{pack["status"]}'))
                chunks.append((f' | {self.text("an_rep_pack")}: {names(self.lang, pack["team"])}\n', "line"))
                hp = self.text("an_rep_hp").format(hp=f'{pack["avg_hp"]:.0f}')
                chunks.append((f'    {pack["winrate"]:.1f}% ({pack["wins"]}/{pack["attempts"]}) · {hp}\n', "muted"))
        return chunks

    # ── Анализ ──────────────────────────────────────────────────────────────
    def run_analysis(self):
        if self.running:
            return
        self.running = True
        self._show_buttons()
        self._console_lines = [("system", "an_log_loaded", {})]
        self._render_console()
        folder = data_paths.logs_dir()

        def work():
            try:
                self._answers.put(("ok", analytics_data.analyze(folder)))
            except Exception as e:  # окно не должно зависнуть из-за битого файла
                self._answers.put(("error", f"{type(e).__name__}: {e}"))

        threading.Thread(target=work, daemon=True, name="analytics").start()
        self._poll_id = self.after(POLL_MS, self._poll)

    def _poll(self):
        self._poll_id = None
        try:
            kind, value = self._answers.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(POLL_MS, self._poll)
            return
        self.running = False
        self.last_run = datetime.now()
        if kind == "error":
            self._say("error", "an_log_error", error=value)
        else:
            self._finish(value)
        self._show_last()
        self._show_counts()
        self._show_golden()
        self._show_buttons()
        self._render_console()

    def _finish(self, result):
        self.result = result
        self.golden = result["golden"]
        self.checked = {id(g) for g in self.golden}   # как в макете: найденные сразу отмечены
        if not result["files"]:
            self._say("error", "an_log_no_files", folder=data_paths.logs_dir())
            return
        self._say("ml", "an_log_read", records=result["records"], files=result["files"])
        self._say("ml", "an_log_battles", n=result["battles"])
        if result["scenarios"]:
            self._console_lines.append(("report", "", {}))
        if self.golden:
            self._say("done", "an_log_found", n=len(self.golden))
        else:
            self._say("done", "an_log_none")

    def apply_golden(self):
        chosen = self._chosen()
        if not chosen or self.running:
            return
        added, skipped, broken = analytics_data.apply_golden(chosen)
        for room, rule in added:
            self._say("done", "an_log_added", room=room_name(self.lang, room),
                      enemies=names(self.lang, rule["condition"]["enemies_contain"]))
        for room in broken:
            self._say("error", "an_log_broken", room=room_name(self.lang, room))
        for gold in skipped:
            if gold["room"] not in broken:
                self._say("system", "an_log_skipped", room=room_name(self.lang, gold["room"]),
                          enemies=names(self.lang, gold["enemies"]))
        self._say("done", "an_log_applied", n=len(added))
        if added:
            Toast(self, self.text("an_toast_applied").format(n=len(added)))
        used = {id(g) for g in chosen}
        self.golden = [g for g in self.golden if id(g) not in used]
        self.checked -= used
        self._show_counts()
        self._show_golden()
        self._show_buttons()
        self._render_console()

    def destroy(self):
        if self._poll_id:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
        super().destroy()
