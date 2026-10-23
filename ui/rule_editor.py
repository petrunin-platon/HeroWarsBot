"""Окно «Новое правило» / «Изменить правило» (задача 15, шаг 5в; макет design/mockups/03d_rule_editor) — вместо старого
ui/rule_builder_dialog.py (его оставляем старому окну).

Всё, что умело старое окно: стихия, название, триггер «По ХП / По энергии / По врагам» (13 врагов, которых бот узнаёт),
«Остановиться и спросить меня», «Запретить вход (Skip)», «Требовать обкатку титанов», состав (окно «Собери состав»).
Ваши ответы 23.10.2026: пак [STOP] называется как есть — бот открывает окно «Нет подходящего пака» и ждёт ответа;
обкатка — от 1 до 5 титанов любых стихий (✕ — убрать); пустое название — составляется из условия.
Ошибки старого окна, которые здесь исправлены: «По врагам» без врагов срабатывало в каждой комнате — сохранить нельзя,
пока не выбран враг; «Запретить вход» по врагам бот не выполняет (врагов он видит уже после выбора двери) — для «По врагам»
галочка недоступна; не число в поле ХП роняло окно — ошибка под полем; при изменении правила терялись скрытые поля
(source, allowed_delta, special_ult) — теперь остаются (ui/rules_list.py: rule_from_editor).

Окно ничего не пишет в файл: «Сохранить правило» отдаёт правило странице (on_save(стихия, правило)), в файл его пишет
«Сохранить настройки» мастера правил. Окно модальное; пока открыто «Собери состав», оно его не держит (grab).
"""
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from i18n import get_text
from ui import rules_list, theme
from ui.rules_store import PERCENT_MAX, parse_number
from ui.rules_tactics import NumberEntry
from ui.titan_picker import MAX_TITANS, TitanPicker, _check_picture
from ui.widgets import (Button, ClickFrame, Dropdown, IconButton, PlainIconButton, PlainLabel, TitanTile, Tooltip,
                        anchor_area, plain_icon, present_window, titan_name)

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

WIDTH = 512            # содержимое окна (макет: 560 минус отступы 24 + 24)
BG = C["bg_primary"]   # фон окна (макет)
ENEMY_COLUMNS = 7
TRIGGER_KEYS = {"hp": "re_by_hp", "energy": "re_by_energy", "enemies": "re_by_enemies"}


def px(widget, value):
    return round(value * ctk.ScalingTracker.get_widget_scaling(widget))


def caption(master, text, bg=BG):
    return PlainLabel(master, text, font=F["label"], color=C["text_secondary"], bg=bg, anchor="w")


def checkbox(master, text, command):
    return ctk.CTkCheckBox(master, text=text, command=command, font=F["text"], text_color=C["text"],
                           text_color_disabled=C["text_muted"], fg_color=C["blue"], hover_color=C["blue"],
                           border_color=C["border_strong"], checkmark_color=C["white"], checkbox_width=16,
                           checkbox_height=16, corner_radius=4, border_width=1, bg_color=BG)


class RuleEditor(ctk.CTkToplevel):
    """room — стихия, с которой открыть; rule — правило, которое меняем (None — новое).
    on_save(стихия, правило) — «Сохранить правило»."""

    def __init__(self, master, lang, room, on_save, rule=None):
        root = master.winfo_toplevel()
        super().__init__(root, fg_color=BG)
        self.withdraw()
        self.lang = lang
        self.on_save = on_save
        self.original = rule
        self.values = rules_list.editor_values(rule, room)
        self._done = False
        self._picker = None
        self.title(self.text("re_title_edit" if rule else "re_title_new"))
        self.resizable(False, False)
        self.transient(root)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        self.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_body()
        self._build_footer()
        self._show_trigger()
        self._show_action()
        self._check()
        present_window(self, lambda: self._place_centered(root), hidden=lambda: self._done,
                       on_shown=lambda: self._grab_when_visible(20))

    def text(self, key):
        return get_text(self.lang, key)

    # ── Части окна ──────────────────────────────────────────────────────────
    def _build_header(self):
        head = tk.Frame(self, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 16))
        head.grid_columnconfigure(1, weight=1)
        self.badge_picture = plain_icon(self, "sliders-vertical", C["blue_text"], 18, box=36, tint=T["blue_icon_bg"],
                                        bg=BG, radius=8)
        tk.Label(head, image=self.badge_picture, bg=BG, bd=0, highlightthickness=0).grid(
            row=0, column=0, rowspan=2, sticky="n", padx=(0, 12))
        PlainLabel(head, self.text("re_title_edit" if self.original else "re_title_new"), font=F["page_title"],
                   color=C["text"], bg=BG, anchor="w").grid(row=0, column=1, sticky="w")
        PlainLabel(head, self.text("re_sub"), font=F["label"], color=C["text_secondary"], bg=BG, anchor="w").grid(
            row=1, column=1, sticky="w", pady=(px(head, 4), 0))
        IconButton(head, "x", size=32, icon_size=16, fg_color=BG, bg_color=BG, hover_color=C["bg_elevated"],
                   border_width=0, tooltip=lambda: self.text("re_close"), command=self.close).grid(
            row=0, column=2, rowspan=2, sticky="ne")
        tk.Frame(self, height=1, bg=C["border"]).grid(row=1, column=0, sticky="ew")

    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.grid(row=2, column=0, sticky="ew", padx=24, pady=20)
        body.grid_columnconfigure(0, weight=1, minsize=px(self, WIDTH))
        self.body = body
        v = self.values

        top = tk.Frame(body, bg=BG)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure((0, 1), weight=1, uniform="top")
        caption(top, self.text("re_room")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        caption(top, self.text("re_name")).grid(row=0, column=1, sticky="w", padx=(12, 0), pady=(0, 6))
        items, icons = [], {}
        for room in rules_list.ROOMS:
            style = theme.element_style(room)
            items.append((room, theme.plain_text(self.text(f"elem_{room}"))))
            icons[room] = (style["icon"], style["text"])
        self.room_menu = Dropdown(top, items, v["room"], command=self._room_chosen, icons=icons, width=10,
                                  bg_color=BG)
        self.room_menu.grid(row=1, column=0, sticky="ew")
        self.name_entry = ctk.CTkEntry(top, height=S["control_height"], corner_radius=S["radius_control"],
                                       border_width=1, border_color=C["border"], fg_color=C["bg_elevated"],
                                       text_color=C["text"], font=F["body"], bg_color=BG,
                                       placeholder_text=self.text("re_name_hint"),
                                       placeholder_text_color=C["text_muted"])
        if v["name"]:
            self.name_entry.insert(0, v["name"])
        self.name_entry.grid(row=1, column=1, sticky="ew", padx=(12, 0))

        caption(body, self.text("re_trigger")).grid(row=1, column=0, sticky="w", pady=(16, 6))
        self.trigger_names = {t: self.text(TRIGGER_KEYS[t]) for t in rules_list.TRIGGERS}
        self.triggers = ctk.CTkSegmentedButton(
            body, values=[self.trigger_names[t] for t in rules_list.TRIGGERS], command=self._trigger_chosen,
            height=38, corner_radius=8, border_width=3, fg_color=C["bg_surface"], selected_color=C["blue_button"],
            selected_hover_color=C["blue_button"], unselected_color=C["bg_surface"],
            unselected_hover_color=C["bg_elevated"], text_color=C["white"], font=F["button"],
            dynamic_resizing=False, bg_color=BG)
        self.triggers.grid(row=2, column=0, sticky="ew")
        self.triggers.set(self.trigger_names[v["trigger"]])

        # Условие по ХП или энергии: титан и число
        self.number_panel = tk.Frame(body, bg=BG)
        self.number_panel.grid_columnconfigure(0, weight=1)
        caption(self.number_panel, self.text("re_titan")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.value_caption = caption(self.number_panel, "")
        self.value_caption.grid(row=0, column=1, sticky="w", padx=(12, 0), pady=(0, 6))
        self.titan_menu = Dropdown(self.number_panel, self._titan_items(), v["titan"], command=self._titan_chosen,
                                   titans=True, lang=self.lang, breaks=self._titan_breaks(), width=10, bg_color=BG)
        self.titan_menu.grid(row=1, column=0, sticky="ew")
        self.value_entry = NumberEntry(self.number_panel, v["value"], width=120)
        self.value_entry.configure(bg_color=BG)
        self.value_entry.grid(row=1, column=1, padx=(12, 0))
        self.value_entry.bind("<KeyRelease>", lambda _e: self._value_typed(), add="+")
        self.value_error = PlainLabel(self.number_panel, "", font=F["label"], color=C["danger_text"], bg=BG,
                                      anchor="e")

        # Условие по врагам: сетка 7 колонок
        self.enemy_panel = tk.Frame(body, bg=BG)
        self.enemy_panel.grid_columnconfigure(tuple(range(ENEMY_COLUMNS)), weight=1, uniform="enemy")
        head = tk.Frame(self.enemy_panel, bg=BG)
        head.grid(row=0, column=0, columnspan=ENEMY_COLUMNS, sticky="w", pady=(0, 8))
        caption(head, self.text("re_enemies")).pack(side="left")
        self.enemy_count = PlainLabel(head, "", font=F["label"], color=C["text_muted"], bg=BG)
        self.enemy_count.pack(side="left", padx=(px(head, 8), 0))
        self.enemy_tiles = {}
        for i, enemy in enumerate(rules_list.ENEMIES):
            r, c = divmod(i, ENEMY_COLUMNS)
            tile = EnemyTile(self.enemy_panel, enemy, self.lang, self._enemy_toggled)
            tile.grid(row=1 + r, column=c, sticky="ew", padx=(0 if c == 0 else 4, 0 if c == ENEMY_COLUMNS - 1 else 4),
                      pady=(0, 8))
            self.enemy_tiles[enemy] = tile
        self._show_enemies()

        extra = rules_list.condition_parts(v["extra"], self.lang)
        self.extra_note = None
        if extra:
            self.extra_note = PlainLabel(body, self.text("re_extra").format(text=" · ".join(extra)), font=F["label"],
                                         color=C["text_muted"], bg=BG, anchor="w", justify="left",
                                         wraplength=px(self, WIDTH))
            self.extra_note.grid(row=4, column=0, sticky="w", pady=(10, 0))

        tk.Frame(body, height=1, bg=C["border"]).grid(row=5, column=0, sticky="ew", pady=(16, 14))
        PlainLabel(body, self.text("re_action"), font=F["button_bold"], color=C["text"], bg=BG, anchor="w").grid(
            row=6, column=0, sticky="w")
        self.ask_box = checkbox(body, self.text("re_ask"), lambda: self._action_ticked(rules_list.ASK))
        self.ask_box.grid(row=7, column=0, sticky="w", pady=(10, 0))
        self.skip_box = checkbox(body, self.text("re_skip"), lambda: self._action_ticked(rules_list.SKIP))
        self.skip_box.grid(row=8, column=0, sticky="w", pady=(10, 0))
        self.skip_note = PlainLabel(body, self.text("re_skip_enemies"), font=F["label"], color=C["text_muted"], bg=BG,
                                    anchor="w", justify="left", wraplength=px(self, WIDTH - 26))
        self.fought_row = FoughtRow(body, self)
        self.fought_row.grid(row=10, column=0, sticky="ew", pady=(10, 0))

        caption(body, self.text("re_pack")).grid(row=11, column=0, sticky="w", pady=(16, 6))
        pack = tk.Frame(body, bg=BG)
        pack.grid(row=12, column=0, sticky="ew")
        pack.grid_columnconfigure(0, weight=1)
        self.pack_tiles = tk.Frame(pack, bg=BG)
        self.pack_tiles.grid(row=0, column=0, sticky="w")
        self.pack_button = Button(pack, self.text("re_pack_pick"), kind="secondary", command=self._pick_pack)
        self.pack_button.grid(row=0, column=1, sticky="e")

    def _build_footer(self):
        tk.Frame(self, height=1, bg=C["border"]).grid(row=3, column=0, sticky="ew")
        footer = tk.Frame(self, bg=C["bg_surface"])
        footer.grid(row=4, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self.problem_label = PlainLabel(footer, "", font=F["label"], color=C["text_muted"], bg=C["bg_surface"],
                                        anchor="w", justify="left", wraplength=px(self, 240))
        self.problem_label.grid(row=0, column=0, sticky="w", padx=(24, 10), pady=14)
        self.cancel_button = Button(footer, self.text("btn_cancel"), kind="secondary",
                                    height=S["button_height_footer"], command=self.close)
        self.cancel_button.grid(row=0, column=1, padx=(0, 10), pady=14)
        self.save_button = Button(footer, self.text("re_save"), kind="save", icon_name="save", icon_size=15,
                                  height=S["button_height_footer"], pad_x=18, font=F["body_bold"], command=self.save)
        self.save_button.grid(row=0, column=2, padx=(0, 24), pady=14)

    # ── Списки титанов ──────────────────────────────────────────────────────
    def _titan_items(self):
        return [(t, titan_name(self.lang, t)) for t in theme.room_titans(self.values["room"])]

    def _titan_breaks(self):
        """Длинный список (смешанная) — колонками по стихиям, как в «Авто-тактике»."""
        if self.values["room"] in ("earth", "water", "fire"):
            return ()
        return [names[0] for names in list(theme.TITANS.values())[1:]] + theme.ELARITE_ONLY[:1]

    # ── Правки ──────────────────────────────────────────────────────────────
    def _room_chosen(self, room):
        rules_list.fit_room(self.values, room)
        self.titan_menu.destroy()
        self.titan_menu = Dropdown(self.number_panel, self._titan_items(), self.values["titan"],
                                   command=self._titan_chosen, titans=True, lang=self.lang,
                                   breaks=self._titan_breaks(), width=10, bg_color=BG)
        self.titan_menu.grid(row=1, column=0, sticky="ew")
        self._show_pack()
        self._check()

    def _trigger_chosen(self, text):
        trigger = next((t for t, name in self.trigger_names.items() if name == text), "hp")
        if trigger == self.values["trigger"]:
            return
        self.values["trigger"] = trigger
        if trigger == "enemies" and self.values["action"] == rules_list.SKIP:
            self.values["action"] = rules_list.PACK   # по врагам вход не запретить (бот их видит после выбора двери)
        self._show_trigger()
        self._show_action()
        self._check()

    def _show_trigger(self):
        trigger = self.values["trigger"]
        if trigger == "enemies":
            self.number_panel.grid_remove()
            self.enemy_panel.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        else:
            self.enemy_panel.grid_remove()
            self.number_panel.grid(row=3, column=0, sticky="ew", pady=(16, 0))
            self.value_caption.configure(text=self.text("re_hp_below" if trigger == "hp" else "re_energy_below"))

    def _titan_chosen(self, titan):
        self.values["titan"] = titan

    def _value_typed(self):
        value, error = parse_number(self.value_entry.get(), PERCENT_MAX)
        self.values["value"] = value
        self.value_entry.set_error(bool(error))
        if error:
            self.value_error.configure(text=self.text("rt_range_error").format(lo=0, hi=PERCENT_MAX))
            self.value_error.grid(row=2, column=0, columnspan=2, sticky="e", pady=(4, 0))
        else:
            self.value_error.grid_remove()
        self._check()

    def _enemy_toggled(self, enemy):
        chosen = set(self.values["enemies"])
        chosen.symmetric_difference_update({enemy})
        self.values["enemies"] = [e for e in rules_list.ENEMIES if e in chosen] + \
                                 [e for e in self.values["enemies"] if e in chosen and e not in rules_list.ENEMIES]
        self._show_enemies()
        self._check()

    def _show_enemies(self):
        for enemy, tile in self.enemy_tiles.items():
            tile.set_selected(enemy in self.values["enemies"])
        text = self.text("re_enemies_count").format(n=len(self.values["enemies"]))
        if self.enemy_count.cget("text") != text:
            self.enemy_count.configure(text=text)

    def _action_ticked(self, kind):
        box = self.ask_box if kind == rules_list.ASK else self.skip_box
        self.values["action"] = kind if box.get() else rules_list.PACK
        self._show_action()
        self._check()

    def _show_action(self):
        """Галочки (одна исключает другую, как в старом окне); пак и обкатка — только когда правило ставит пак."""
        action = self.values["action"]
        for box, kind in ((self.ask_box, rules_list.ASK), (self.skip_box, rules_list.SKIP)):
            if action == kind and not box.get():
                box.select()
            elif action != kind and box.get():
                box.deselect()
        by_enemies = self.values["trigger"] == "enemies"
        # Старое правило «Skip по врагам» (его давало сделать старое окно): галочку можно только снять
        self.skip_box.configure(state="disabled" if by_enemies and action != rules_list.SKIP else "normal")
        if by_enemies:
            self.skip_note.grid(row=9, column=0, sticky="w", padx=(26, 0), pady=(4, 0))
        else:
            self.skip_note.grid_remove()
        self.fought_row.set_enabled(action == rules_list.PACK)
        self._show_pack()

    def _show_pack(self):
        for child in self.pack_tiles.winfo_children():
            child.destroy()
        needs_pack = self.values["action"] == rules_list.PACK
        team = self.values["team"]
        if needs_pack and team:
            for titan in team:
                TitanTile(self.pack_tiles, titan, lang=self.lang, bg=BG).pack(side="left", padx=(0, 6))
        else:
            PlainLabel(self.pack_tiles, self.text("re_pack_none" if needs_pack else "re_pack_not_needed"),
                       font=F["label"], color=C["text_muted"], bg=BG).pack(side="left", pady=px(self, 9))
        self.pack_button.set_enabled(needs_pack)

    def _check(self):
        """Можно ли сохранять; если нет — почему (в футере)."""
        problem = rules_list.editor_problem(self.values)
        self.save_button.set_enabled(problem is None)
        text = self.text(problem) if problem and problem != "re_skip_enemies" else ""
        if self.problem_label.cget("text") != text:
            self.problem_label.configure(text=text)

    # ── «Собери состав» ─────────────────────────────────────────────────────
    def _picker_open(self):
        return self._picker is not None and not self._picker.closed

    def _open_picker(self, on_pick, **kwargs):
        if self._picker_open():
            self._picker.lift()
            return
        try:
            self.grab_release()   # пока открыт выбор титанов, окно правила его не держит
        except tk.TclError:
            pass

        def back():
            self._picker = None
            self._grab_when_visible(20)

        def applied(team):
            back()
            on_pick(team)
        self._picker = TitanPicker(self, self.lang, on_apply=applied, on_cancel=back, **kwargs)

    def _pick_pack(self):
        v = self.values
        selected = v["team"] or ([v["titan"]] if v["trigger"] != "enemies" else [])   # как старое окно: титан условия
        self._open_picker(room=v["room"], selected=selected, on_pick=self._pack_picked)

    def _pack_picked(self, team):
        self.values["team"] = list(team)
        self._show_pack()
        self._check()

    def pick_fought(self):
        self._open_picker(room=None, selected=self.values["fought"], min_titans=rules_list.MIN_FOUGHT,
                          title=self.text("pick_fought_title"), sub=self.text("pick_fought_sub"),
                          on_pick=self._fought_picked)

    def _fought_picked(self, team):
        self.values["fought"] = list(team)
        self.fought_row.show()

    def clear_fought(self):
        self.values["fought"] = []
        self.fought_row.show()

    # ── Показ и закрытие ────────────────────────────────────────────────────
    @property
    def done(self):
        return self._done

    def _place_centered(self, root):
        """Только место: высота окна — по содержимому (у «По врагам» оно выше)."""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        ax, ay, aw, ah = anchor_area(root)
        y = max(0, min(ay + (ah - h) // 3, self.winfo_screenheight() - h - 40))
        self.geometry(f"+{max(0, ax + (aw - w) // 2)}+{y}")

    def _grab_when_visible(self, tries):
        if self._done or self._picker_open():
            return
        try:
            if self.winfo_viewable():
                self.grab_set()
            elif tries > 0:
                self.after(50, self._grab_when_visible, tries - 1)
        except tk.TclError:
            pass

    def save(self):
        if self._done or rules_list.editor_problem(self.values) is not None:
            return
        self.values["name"] = self.name_entry.get()
        room = self.values["room"]
        rule = rules_list.rule_from_editor(self.values, self.original, self.lang)
        self.close()
        self.on_save(room, rule)

    def close(self):
        if self._done:
            return
        self._done = True
        if self._picker_open():
            self._picker.close_silently()
        try:
            self.grab_release()
            for menu in (self.room_menu, self.titan_menu):
                menu.destroy()   # меню списков живут у окна
            self.destroy()
        except tk.TclError:
            pass


class EnemyTile(ClickFrame):
    """Враг в сетке «Опасные враги в комнате»: квадрат титана, имя, у выбранного — зелёная рамка, оттенок и галочка.
    Наведение меняет только цвет рамки; выбор (щелчок) — фон и квадрат (у его картинки уголки цвета фона)."""

    def __init__(self, master, enemy, lang, command):
        super().__init__(master, command=lambda: command(enemy), height=66, width=10, corner_radius=8,
                         border_width=1, border_color=C["border"], fg_color=C["bg_surface"], bg_color=BG)
        self.enemy = enemy
        self.lang = lang
        self.selected = None
        self._look = None
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.tile_box = tk.Frame(self, bg=C["bg_surface"])
        self.tile_box.grid(row=0, column=0, pady=(5, 0))
        self.name_label = PlainLabel(self, titan_name(lang, enemy), font=F["small"], color=C["text_secondary"],
                                     bg=C["bg_surface"])
        self.name_label.grid(row=1, column=0, pady=(2, 5))
        side = px(self, 16)
        self.check_photo = ImageTk.PhotoImage(_check_picture(16).resize((side, side), Image.LANCZOS), master=self)
        self.check = tk.Label(self, image=self.check_photo, bd=0, highlightthickness=0, bg=C["bg_surface"])
        self.tooltip = Tooltip(self.name_label, lambda: titan_name(self.lang, self.enemy))
        self.bind_parts(self.tile_box, self.name_label, self.check)
        self.set_selected(False)

    def set_selected(self, selected):
        if selected == self.selected:
            return
        self.selected = selected
        bg = T["green_on_surface"] if selected else C["bg_surface"]
        for child in self.tile_box.winfo_children():
            child.destroy()
        tile = TitanTile(self.tile_box, self.enemy, lang=self.lang, bg=bg)
        tile.pack()
        self.bind_parts(tile)
        for part in (self.tile_box, self.name_label, self.check):
            part.configure(bg=bg)
        self.configure(fg_color=bg)
        if selected:
            self.check.place(relx=1.0, x=-px(self, 3), y=px(self, 3), anchor="ne")
        else:
            self.check.place_forget()
        self._look = None
        self._paint()

    def _paint(self):
        if self.selected:
            look = C["green"]
        else:
            look = C["border_focus"] if self._hovering else C["border"]
        if look != self._look:
            self._look = look
            self.configure(border_color=look)


class FoughtRow(ClickFrame):
    """«Требовать обкатку титанов … не выбрано ›»: щелчок — «Собери состав» (1–5 титанов), выбранные — именами справа,
    ✕ — убрать. Недоступна, когда правило не ставит пак (как в старом окне; выбранное при этом остаётся в правиле).
    Наведение — только цвет рамки."""

    def __init__(self, master, editor):
        super().__init__(master, command=editor.pick_fought, height=S["control_height"], width=10,
                         corner_radius=S["radius_control"], border_width=1, border_color=C["border"],
                         fg_color=BG, bg_color=BG)
        self.editor = editor
        self._look = None
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.title = PlainLabel(self, editor.text("re_fought"), font=F["text"], color=C["text"], bg=BG)
        self.title.grid(row=0, column=0, padx=(10, 8))
        self.value = PlainLabel(self, "", font=F["text"], color=C["text_muted"], bg=BG, anchor="e")
        self.value.grid(row=0, column=1, sticky="ew")
        self.clear = PlainIconButton(self, "x", command=editor.clear_fought, size=13, bg=BG,
                                     hover=C["bg_elevated"], color=C["text_muted"],
                                     tooltip=lambda: editor.text("re_fought_clear"), pad=4)
        self.arrow_picture = plain_icon(self, "chevron-right", C["text_muted"], 14)
        self.arrow = tk.Label(self, image=self.arrow_picture, bg=BG, bd=0, highlightthickness=0)
        self.arrow.grid(row=0, column=3, padx=(4, 10))
        self.bind_parts(self.title, self.value, self.arrow)
        self.tooltip = Tooltip(self.title, lambda: editor.text("re_fought_tip"))
        self.show()

    def show(self):
        fought = self.editor.values["fought"]
        text = rules_list.names(self.editor.lang, fought) if fought else self.editor.text("re_fought_none")
        if self.value.cget("text") != text:
            self.value.configure(text=text, fg=C["blue_text"] if fought else C["text_muted"])
        if fought:
            self.clear.grid(row=0, column=2, padx=(6, 0))
        else:
            self.clear.grid_remove()

    def set_enabled(self, enabled):
        super().set_enabled(enabled)
        self.title.configure(fg=C["text"] if enabled else C["text_muted"])
        self.clear.set_enabled(enabled)

    def _paint(self):
        look = C["border_focus"] if self._hovering and self.enabled else C["border"]
        if look != self._look:
            self._look = look
            self.configure(border_color=look)
