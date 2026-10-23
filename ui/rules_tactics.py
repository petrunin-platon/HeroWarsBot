"""Мастер правил → «Авто-тактика и ХП» (задача 15, шаг 5б; макет design/mockups/03b_rules_tactics) — вместо окна «⚙️ Тактика».

Синяя плашка: что делает бот, когда бой плохой. «Бот решает сам» выключен — в плашке продолжение того же текста: запасные
паки и пак отхила тогда не работают, а остальное работает всегда (ваш ответ 22.10.2026; после проверки — тем же белым
текстом, без значка).
«Приоритет дверей» — 4 места, каждое — выпадающий список стихии; выбрали стихию, которая стоит на другом месте, —
они меняются местами (как в окне «Тактика»). «Критерии плохого боя и SOS» — сколько запасных паков пробовать (1–3),
через сколько минут без ответа на окно SOS бот решает сам, общие потери пака. «Авто-сборка пака отхила в Смешанной» —
с какого ХП лечить и кого убирать из пака ради раненого (3 места: щелчок — список титанов, ваш ответ). «Личные пороги
паники» — чипсы (щелчок — изменить, ✕ — убрать) и «Задать личный порог титану» — маленькое окно ThresholdDialog (ваш ответ).

Как «База и комнаты» (ui/rules_base.py): вкладка ничего не пишет сама, все значения — в форме страницы (page.form),
пишет их «Сохранить настройки»; ключи профиля — те же, что у окна «Тактика» (ui/rules_store.py: TACTICS_KEYS).
Поле с ошибкой (не число или не в пределах) — красная рамка и текст под ним, сохранить нельзя (page.field_errors).

Надписи, значки, стрелки и рамки внутри карточек — обычные Tk (PlainLabel, tk.Label с картинкой, tk.Frame): у каждого
элемента CustomTkinter свой холст, и в Windows вкладка дорисовывалась с задержкой (проверка шага 5б). CustomTkinter —
только там, где нужны скругления: карточки, поля, места «Кого убирать», чипсы, кнопка.
"""
import tkinter as tk

import customtkinter as ctk
from customtkinter.windows.widgets.core_widget_classes import DropdownMenu

import tactics
from i18n import get_text
from ui import rules_store, theme
from ui.widgets import (Button, Card, ClickFrame, Dropdown, Field, PlainLabel, TitanTile, Tooltip, anchor_area,
                        plain_icon, present_window, titan_name)

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

ENTRY_WIDTH = 64
CHIPS_PER_ROW = 5
ALL_TITANS = [name for names in theme.TITANS.values() for name in names] + theme.ELARITE_ONLY
# Новая колонка меню титанов — с первого титана каждой стихии (кроме первой): список из 29 имён иначе выше экрана
COLUMN_BREAKS = [names[0] for names in list(theme.TITANS.values())[1:]] + theme.ELARITE_ONLY[:1]
AUTO = None   # «— сам —» в «Кого убирать»
BG = C["bg_surface"]


def line(master):
    return tk.Frame(master, height=1, bg=C["border"])


def px(widget, value):
    """Размер в настоящих пикселях с учётом масштаба Windows (wraplength у надписей Tk — в пикселях)."""
    return round(value * ctk.ScalingTracker.get_widget_scaling(widget))


class Picture(tk.Label):
    """Значок обычной надписью Tk (картинка держится у самой надписи)."""

    def __init__(self, master, name, color, size, bg=BG):
        self.picture = plain_icon(master, name, color, size)
        super().__init__(master, image=self.picture, bg=bg, bd=0, highlightthickness=0, padx=0, pady=0)


def card_header(master, icon_name, color, text):
    head = tk.Frame(master, bg=BG)
    Picture(head, icon_name, color, 16).pack(side="left")
    PlainLabel(head, text, font=F["card_title"], color=C["text"]).pack(side="left", padx=(px(head, 8), 0))
    return head


def titan_items(lang):
    """Пункты списка титанов: (имя, имя на языке окна), по стихиям, как в «Собери состав»."""
    return [(t, titan_name(lang, t)) for t in ALL_TITANS]


def titan_icons():
    styles = {t: theme.element_style(theme.element_of(t)) for t in ALL_TITANS}
    return {t: (style["icon"], style["color"]) for t, style in styles.items()}


def titan_order(titan):
    return ALL_TITANS.index(titan) if titan in ALL_TITANS else len(ALL_TITANS)


class Note(PlainLabel):
    """Серая подсказка под полем (или справа в строке); ошибка — красный текст со значком."""

    def __init__(self, master, sub, anchor="w"):
        super().__init__(master, sub, font=F["label"], color=C["text_muted"], anchor=anchor, compound="left")
        self.sub = sub
        self.error_picture = plain_icon(self, "triangle-alert", C["danger_text"], 13)
        self.shown = None

    def show(self, error_text):
        """error_text — текст ошибки или None (снова подсказка)."""
        if error_text == self.shown:
            return
        self.shown = error_text
        if error_text:
            self.configure(text=" " + error_text, fg=C["danger_text"], image=self.error_picture)
        else:
            self.configure(text=self.sub, fg=C["text_muted"], image="")
        self.fit()

    def fit(self):
        """Пустую подсказку (поле без подсказки и без ошибки) не показываем — под подписью нет пустой строки."""
        if self.cget("text"):
            self.grid()
        else:
            self.grid_remove()


class NumberEntry(ctk.CTkEntry):
    """Поле для числа (макет 03b: «3», «10», «60» справа от подписи). Ошибка — рамка 2 px красная (как Field)."""

    def __init__(self, master, value, width=ENTRY_WIDTH):
        super().__init__(master, width=width, height=S["control_height"], corner_radius=S["radius_control"],
                         border_width=1, border_color=C["border"], fg_color=C["bg_elevated"], text_color=C["text"],
                         font=F["mono_field"], justify="center", bg_color=BG)
        self.insert(0, str(value))
        self.error = False
        self._look = (1, C["border"], C["bg_elevated"])
        self.bind("<FocusIn>", lambda _e: self._paint(True), add="+")
        self.bind("<FocusOut>", lambda _e: self._paint(False), add="+")

    def _paint(self, focus=False):
        if self.error:
            look = (2, C["danger"], T["field_error_bg"])
        elif focus:
            look = (2, C["blue"], C["bg_elevated"])
        else:
            look = (1, C["border"], C["bg_elevated"])
        if look != self._look:   # толщина рамки перестраивает поле — только если вид правда поменялся
            self._look = look
            width, border, fg = look
            self.configure(border_width=width, border_color=border, fg_color=fg)

    def set_error(self, error):
        if error != self.error:
            self.error = error
            self._paint(focus=self.focus_get() is self._entry)

    def set(self, value):
        self.delete(0, "end")
        self.insert(0, str(value))


class TacticsTab(ctk.CTkScrollableFrame):
    def __init__(self, master, page):
        super().__init__(master, fg_color="transparent", corner_radius=0,
                         scrollbar_button_color=C["border_strong"], scrollbar_button_hover_color=C["border_focus"])
        self.page = page
        self.lang = page.lang
        self.entries = {}       # ключ формы → NumberEntry
        self.notes = {}         # ключ формы → Note (подсказка или ошибка)
        self._banner_off = None
        self.grid_columnconfigure(0, weight=1)
        self._build_banner()
        self._build_doors()
        self._build_middle()
        self._build_personal()
        self.refresh()

    def text(self, key):
        return get_text(self.lang, key)

    # ── Плашка ──────────────────────────────────────────────────────────────
    def _build_banner(self):
        bg = T["info_banner_bg"]
        banner = Card(self, fg_color=bg, border_color=T["info_banner_border"], width=10, height=10)
        banner.grid(row=0, column=0, sticky="ew", padx=(24, 12), pady=(18, 0))
        banner.grid_columnconfigure(1, weight=1)
        Picture(banner, "info", C["blue_text"], 18, bg=bg).grid(row=0, column=0, sticky="n", padx=(16, 12),
                                                                  pady=(14, 0))
        self.banner_text = PlainLabel(banner, "", font=F["text"], color=C["text"], bg=bg, anchor="w",
                                      justify="left", wraplength=px(banner, 880))
        self.banner_text.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=12)
        banner.bind("<Configure>", self._wrap_banner, add="+")

    def _wrap_banner(self, event):
        """Текст плашки — по ширине плашки (иначе длинный немецкий текст вылезает за край)."""
        width = max(px(self, 300), event.width - px(self, 80))
        if self.banner_text.cget("wraplength") != width:
            self.banner_text.configure(wraplength=width)

    def refresh(self):
        """Вкладку снова показали: «Бот решает сам» и общий порог могли поменять на «Базе и комнатах»."""
        off = not self.page.form["auto_rollback"]
        if off != self._banner_off:
            self._banner_off = off
            text = self.text("rt_banner") + (" " + self.text("rt_banner_off") if off else "")
            self.banner_text.configure(text=text)
        rest = self.text("rt_personal_rest").format(n=self.page.form["critical_hp"])
        if self.personal_rest.cget("text") != rest:
            self.personal_rest.configure(text=rest)

    # ── Приоритет дверей ────────────────────────────────────────────────────
    def _build_doors(self):
        card = Card(self, width=10, height=10)
        card.grid(row=1, column=0, sticky="ew", padx=(24, 12), pady=(12, 0))
        card.grid_columnconfigure(0, weight=1)
        head = tk.Frame(card, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        head.grid_columnconfigure(1, weight=1)
        card_header(head, "door-open", C["blue_text"], self.text("rt_doors_title")).grid(row=0, column=0, sticky="w")
        PlainLabel(head, self.text("rt_doors_hint"), font=F["label"], color=C["text_muted"]).grid(
            row=0, column=1, sticky="e", padx=(12, 0))
        row = tk.Frame(card, bg=BG)
        row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        items, icons, colors = [], {}, {}
        for room in tactics.DEFAULT_DOOR_ORDER:
            style = theme.element_style(room)
            items.append((room, theme.plain_text(self.text(f"elem_{room}"))))
            icons[room] = (style["icon"], style["color"])
            colors[room] = style["text"]
        self.doors = []
        for i, room in enumerate(self.page.form["door_order"]):
            row.grid_columnconfigure(i * 2, weight=1, uniform="doors")
            menu = Dropdown(row, items, room, command=lambda r, i=i: self._door_chosen(i, r), icons=icons,
                            colors=colors, badge=i + 1, width=10, bg_color=BG)
            menu.grid(row=0, column=i * 2, sticky="ew")
            self.doors.append(menu)
            if i < 3:
                Picture(row, "arrow-right", C["text_muted"], 16).grid(row=0, column=i * 2 + 1, padx=10)

    def _door_chosen(self, place, room):
        order = rules_store.choose_door(self.page.form["door_order"], place, room)
        self.page.form["door_order"] = order
        for menu, r in zip(self.doors, order):
            if menu.get() != r:
                menu.set(r)
        self.page.changed()

    # ── Критерии плохого боя и отхил ────────────────────────────────────────
    def _build_middle(self):
        cards = tk.Frame(self, bg=C["bg_primary"])
        cards.grid(row=2, column=0, sticky="ew", padx=(24, 12), pady=(12, 0))
        cards.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        criteria = Card(cards, width=10, height=10, bg_color=C["bg_primary"])
        criteria.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        heal = Card(cards, width=10, height=10, bg_color=C["bg_primary"])
        heal.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._build_criteria(criteria)
        self._build_heal(heal)

    def _number_row(self, master, row, key, title, sub=""):
        """Подпись (и серая подсказка под ней) слева, поле справа."""
        frame = tk.Frame(master, bg=BG)
        frame.grid(row=row, column=0, sticky="ew", padx=16)
        frame.grid_columnconfigure(0, weight=1)
        PlainLabel(frame, title, font=F["text"], color=C["text_secondary"], anchor="w", justify="left").grid(
            row=0, column=0, sticky="w")
        note = Note(frame, sub)
        note.grid(row=1, column=0, sticky="w", pady=(px(frame, 2), 0))
        note.fit()
        entry = self._entry(frame, key, note)
        entry.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        return frame

    def _entry(self, master, key, note):
        entry = NumberEntry(master, self.page.form[key])
        entry.bind("<KeyRelease>", lambda _e, k=key: self._number_typed(k), add="+")
        self.entries[key] = entry
        self.notes[key] = note
        typed = self.page.field_errors.get(key)
        if typed is not None:   # язык сменили, пока в поле ошибка: показываем то, что было введено
            entry.set(typed)
            self._show_error(key, True)
        return entry

    def _number_typed(self, key):
        entry = self.entries[key]
        low, high = rules_store.LIMITS[key]
        value, error = rules_store.parse_number(entry.get(), high, low)
        if error:
            self.page.field_errors[key] = entry.get()
        else:
            self.page.field_errors.pop(key, None)
            self.page.form[key] = value
        self._show_error(key, bool(error))
        self.page.changed()

    def _show_error(self, key, error):
        self.entries[key].set_error(error)
        bad = key
        if key in GROUP_KEYS:   # одна подсказка на два поля
            bad = next((k for k in GROUP_KEYS if k in self.entries and self.entries[k].error), None)
            error = bad is not None
        if error:
            low, high = rules_store.LIMITS[bad]
            self.notes[key].show(self.text("rt_range_error").format(lo=low, hi=high))
        else:
            self.notes[key].show(None)

    def _build_criteria(self, card):
        card.grid_columnconfigure(0, weight=1)
        card_header(card, "triangle-alert", C["warning"], self.text("rt_criteria_title")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 14))
        self._number_row(card, 1, "auto_rollback_tries", self.text("rt_tries"))
        tk.Frame(card, height=px(card, 12), bg=BG).grid(row=2, column=0)
        self._number_row(card, 3, "sos_timeout_minutes", self.text("rt_sos_timeout"), self.text("rt_sos_timeout_sub"))
        line(card).grid(row=4, column=0, sticky="ew", padx=16, pady=14)
        # «Считать бой плохим, если» и справа в той же строке «0 титанов — не проверять» (замечание к шагу 5б)
        head = tk.Frame(card, bg=BG)
        head.grid(row=5, column=0, sticky="ew", padx=16)
        head.grid_columnconfigure(0, weight=1)
        PlainLabel(head, self.text("rt_group_label"), font=F["text"], color=C["text_secondary"], anchor="w").grid(
            row=0, column=0, sticky="w")
        note = Note(head, self.text("rt_group_sub"), anchor="e")
        note.grid(row=0, column=1, sticky="e", padx=(12, 0))
        group = tk.Frame(card, bg=BG)
        group.grid(row=6, column=0, sticky="w", padx=16, pady=(8, 16))
        for col, (key, label) in enumerate(((GROUP_KEYS[0], "rt_group_titans"), (GROUP_KEYS[1], "rt_group_percent"))):
            PlainLabel(group, self.text(label), font=F["text"], color=C["text"]).grid(
                row=0, column=col * 2, padx=(0 if col == 0 else 16, 8))
            self._entry(group, key, note).grid(row=0, column=col * 2 + 1)
        PlainLabel(group, self.text("rt_group_unit"), font=F["text"], color=C["text"]).grid(
            row=0, column=4, padx=(8, 0))

    def _build_heal(self, card):
        card.grid_columnconfigure(0, weight=1)
        card_header(card, "heart-pulse", C["success"], self.text("rt_heal_title")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 14))
        self._number_row(card, 1, "heal_below_hp", self.text("rt_heal_hp"), self.text("rt_heal_hp_sub"))
        line(card).grid(row=2, column=0, sticky="ew", padx=16, pady=14)
        PlainLabel(card, self.text("rt_remove_title"), font=F["text"], color=C["text_secondary"], anchor="w").grid(
            row=3, column=0, sticky="w", padx=16)
        self.remove_row = tk.Frame(card, bg=BG)
        self.remove_row.grid(row=4, column=0, sticky="w", padx=16, pady=(8, 0))
        PlainLabel(card, self.text("rt_remove_sub").format(auto=self.text("tac_heal_auto")), font=F["label"],
                   color=C["text_muted"], anchor="w", justify="left", wraplength=px(card, 400)).grid(
            row=5, column=0, sticky="w", padx=16, pady=(8, 16))
        self.remove_slots = []
        for i in range(tactics.MAX_HEAL_REMOVE):
            if i:
                Picture(self.remove_row, "arrow-right", C["text_muted"], 14).grid(row=0, column=i * 2 - 1, padx=6)
            slot = RemoveSlot(self.remove_row, self, i)
            slot.grid(row=0, column=i * 2)
            self.remove_slots.append(slot)
        self.show_remove()

    def show_remove(self):
        order = self.page.form["heal_remove_order"]
        for i, slot in enumerate(self.remove_slots):
            slot.show(order[i] if i < len(order) else AUTO)

    def remove_chosen(self, place, titan):
        self.page.form["heal_remove_order"] = rules_store.choose_remove(self.page.form["heal_remove_order"], place,
                                                                        titan)
        self.show_remove()
        self.page.changed()

    # ── Личные пороги ───────────────────────────────────────────────────────
    def _build_personal(self):
        card = Card(self, width=10, height=10)
        card.grid(row=3, column=0, sticky="ew", padx=(24, 12), pady=(12, 20))
        card.grid_columnconfigure(0, weight=1)
        head = tk.Frame(card, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        head.grid_columnconfigure(1, weight=1)
        card_header(head, "gauge", C["danger_text"], self.text("rt_personal_title")).grid(row=0, column=0, sticky="w")
        self.personal_rest = PlainLabel(head, "", font=F["label"], color=C["text_muted"])
        self.personal_rest.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.chips = tk.Frame(card, bg=BG)
        self.chips.grid(row=1, column=0, sticky="ew", padx=16)
        self.chips.grid_columnconfigure(tuple(range(CHIPS_PER_ROW)), weight=1, uniform="chips")
        self.add_threshold = Button(card, self.text("rt_personal_add"), kind="secondary", icon_name="plus",
                                    icon_size=14, height=34, fg_color="transparent", hover_color=C["bg_elevated"],
                                    border_color=C["border_focus"], text_color=C["text_secondary"],
                                    command=lambda: self.open_threshold(None))
        self.add_threshold.grid(row=2, column=0, sticky="w", padx=16, pady=(10, 16))
        self.show_personal()

    def show_personal(self):
        """Чипсы личных порогов — заново (только эта часть карточки)."""
        for child in self.chips.winfo_children():
            child.destroy()
        personal = self.page.form["titan_critical_hp"]
        if not personal:
            PlainLabel(self.chips, self.text("rt_personal_none"), font=F["label"], color=C["text_muted"]).grid(
                row=0, column=0, columnspan=CHIPS_PER_ROW, sticky="w", pady=(0, 2))
            return
        for i, titan in enumerate(sorted(personal, key=titan_order)):
            r, c = divmod(i, CHIPS_PER_ROW)
            chip = ThresholdChip(self.chips, self, titan, personal[titan])
            chip.grid(row=r, column=c, sticky="ew", padx=(0, 8), pady=(0, 8))

    def open_threshold(self, titan):
        if getattr(self, "_threshold", None) is not None and not self._threshold.done:
            self._threshold.lift()
            return
        self._threshold = ThresholdDialog(self, self.lang, self.page.form["titan_critical_hp"],
                                          self.page.form["critical_hp"], titan, self.threshold_set)

    def threshold_set(self, titan, value):
        rules_store.set_personal(self.page.form, titan, value)
        self.show_personal()
        self.page.changed()


GROUP_KEYS = ("group_loss_titans", "group_loss_percent")


class RemoveSlot(ClickFrame):
    """Место в «Кого убирать из пака ради раненого»: номер, квадрат и имя титана; пустое — «— сам —» в светлой
    рамке. Щелчок — список: «— сам —» и все титаны по стихиям (ваш ответ 22.10.2026)."""

    def __init__(self, master, tab, place):
        super().__init__(master, command=self.open, height=S["control_height"] + 4, width=10,
                         corner_radius=S["radius_control"], border_width=1, border_color=C["border"],
                         fg_color=C["bg_elevated"], bg_color=BG)
        self.tab = tab
        self.place_no = place
        self.titan = "?"
        self._look = None
        self._bg = C["bg_elevated"]
        self.grid_rowconfigure(0, weight=1)
        self.number = PlainLabel(self, str(place + 1), font=F["label"], color=C["text_muted"], bg=self._bg)
        self.number.grid(row=0, column=0, padx=(10, 6), pady=6)
        self.tile_box = tk.Frame(self, bg=self._bg)
        self.name_label = PlainLabel(self, "", font=F["text"], color=C["text"], bg=self._bg)
        self.name_label.grid(row=0, column=2, padx=(6, 12), pady=6)
        self.bind_parts(self.number, self.name_label, self.tile_box)
        auto = get_text(tab.lang, "tac_heal_auto")
        self.items = [(AUTO, auto)] + titan_items(tab.lang)
        self.menu = DropdownMenu(self.winfo_toplevel(), values=[t for _k, t in self.items], command=self._chosen,
                                 fg_color=C["bg_elevated"], hover_color=C["blue_button"], text_color=C["text"],
                                 font=F["text"], min_character_width=6)
        for i, (key, _t) in enumerate(self.items):
            if key in COLUMN_BREAKS:
                self.menu.entryconfigure(i, columnbreak=1)

    def show(self, titan):
        if titan == self.titan:
            return
        self.titan = titan
        for child in self.tile_box.winfo_children():
            child.destroy()
        if titan is AUTO:
            self.tile_box.grid_remove()
            self.name_label.configure(text=get_text(self.tab.lang, "tac_heal_auto"), fg=C["text_muted"])
            self.name_label.grid_configure(padx=(0, 12))
        else:
            tile = TitanTile(self.tile_box, titan, lang=self.tab.lang, size=S["avatar_small"], bg=C["bg_elevated"])
            tile.pack()
            self.bind_parts(tile)
            self.tile_box.grid(row=0, column=1, pady=6)
            self.name_label.configure(text=titan_name(self.tab.lang, titan), fg=C["text"])
            self.name_label.grid_configure(padx=(8, 12))
        self._paint()

    def _paint(self):
        empty = self.titan is AUTO
        if self._hovering:
            look = (T["hover_elevated"], C["border_focus"])
        else:
            look = (BG if empty else C["bg_elevated"], C["border_focus"] if empty else C["border"])
        if look != self._look:
            self._look = look
            fg, border = look
            self.configure(fg_color=fg, border_color=border)
            for part in (self.number, self.name_label, self.tile_box):
                part.configure(bg=fg)

    def open(self):
        self.menu.open(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 2)

    def _chosen(self, text):
        key = next((k for k, t in self.items if t == text), "?")
        if key != "?":
            self.tab.remove_chosen(self.place_no, key)

    def destroy(self):
        try:
            self.menu.destroy()
        except tk.TclError:
            pass
        super().destroy()


class ThresholdChip(ClickFrame):
    """Чипс личного порога: квадрат титана, имя, порог жёлтым, ✕ — убрать. Щелчок по чипсу — изменить порог.
    Внутри — обычные надписи Tk; наведение меняет только цвет фона."""

    def __init__(self, master, tab, titan, value):
        super().__init__(master, command=lambda: tab.open_threshold(titan), height=S["control_height"] + 4, width=10,
                         corner_radius=S["radius_control"], border_width=1, border_color=C["border"],
                         fg_color=C["bg_elevated"], bg_color=BG)
        self.titan = titan
        self._look = None
        bg = C["bg_elevated"]
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.tile = TitanTile(self, titan, lang=tab.lang, size=S["avatar_small"], bg=bg)
        self.tile.grid(row=0, column=0, padx=(6, 8))
        self.name_label = PlainLabel(self, titan_name(tab.lang, titan), font=F["text"], color=C["text"], bg=bg,
                                     anchor="w")
        self.name_label.grid(row=0, column=1, sticky="ew")
        self.value_label = PlainLabel(self, f"{value}%", font=F["mono"], color=C["warning"], bg=bg)
        self.value_label.grid(row=0, column=2, padx=(6, 6))
        self.remove_button = Picture(self, "x", C["text_muted"], 13, bg=bg)
        self.remove_button.configure(cursor="hand2", padx=px(self, 4), pady=px(self, 4))
        self.remove_button.grid(row=0, column=3, padx=(0, 6))
        self.remove_button.bind("<Button-1>", lambda _e: tab.threshold_set(titan, None), add="+")
        self.remove_button.bind("<Enter>", self._frame_enter, add="+")
        self.remove_button.bind("<Leave>", self._frame_leave, add="+")
        self.remove_tip = Tooltip(self.remove_button, lambda: get_text(tab.lang, "rt_personal_remove"))
        self.bind_parts(self.tile, self.name_label, self.value_label)
        self.tooltip = Tooltip(self.name_label, lambda: get_text(tab.lang, "rt_personal_edit"))
        self._paint()

    def _paint(self):
        look = T["hover_elevated"] if self._hovering else C["bg_elevated"]
        if look != self._look:
            self._look = look
            self.configure(fg_color=look)
            for part in (self.name_label, self.value_label, self.remove_button):
                part.configure(bg=look)


class ThresholdDialog(ctk.CTkToplevel):
    """«Задать личный порог титану» (макета нет — в стиле окон подтверждения, ваш ответ 22.10.2026): титан из списка
    (по стихиям), порог 0–100 % ХП, «Применить» — on_apply(титан, порог). titan — изменить порог этого титана
    (список тогда не меняется). Крестик, Esc и «Отмена» — просто закрыть. В файл пишет «Сохранить настройки».
    Раскладка (замечание к шагу 5б): заголовок и пояснение рядом, вместе — по центру значка; список и поле — во всю
    ширину, от левого края значка до правого края окна (минус отступ)."""

    def __init__(self, master, lang, personal, common, titan, on_apply):
        root = master.winfo_toplevel()
        super().__init__(root, fg_color=BG)
        self.withdraw()
        self.lang = lang
        self.on_apply = on_apply
        self._done = False
        self.title(get_text(lang, "rt_pt_title"))
        self.resizable(False, False)
        self.transient(root)
        self.grid_columnconfigure(0, weight=1, minsize=DIALOG_WIDTH)

        head = tk.Frame(self, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 0))
        head.grid_columnconfigure(1, weight=1)
        self.badge_picture = plain_icon(self, "gauge", C["danger_text"], 20, box=40, tint=T["danger_on_surface"],
                                        bg=BG, radius=10)
        tk.Label(head, image=self.badge_picture, bg=BG, bd=0, highlightthickness=0).grid(row=0, column=0,
                                                                                        padx=(0, 14))
        words = tk.Frame(head, bg=BG)
        words.grid(row=0, column=1, sticky="w")    # по центру значка по высоте (так ставит grid)
        PlainLabel(words, get_text(lang, "rt_pt_title"), font=F["dialog_title"], color=C["text"], anchor="w").pack(
            anchor="w")
        PlainLabel(words, get_text(lang, "rt_pt_sub"), font=F["label"], color=C["text_secondary"], anchor="w",
                   justify="left", wraplength=px(self, DIALOG_WIDTH - 94)).pack(anchor="w", pady=(px(self, 2), 0))

        body = tk.Frame(self, bg=BG)
        body.grid(row=1, column=0, sticky="ew", padx=20, pady=(18, 0))
        body.grid_columnconfigure(0, weight=1)
        PlainLabel(body, get_text(lang, "rt_pt_titan"), font=F["label"], color=C["text_secondary"], anchor="w").grid(
            row=0, column=0, sticky="w", pady=(0, 6))
        free = [t for t in ALL_TITANS if t not in personal]
        start = titan or (free[0] if free else ALL_TITANS[0])
        self.titans = Dropdown(body, titan_items(lang), start, icons=titan_icons(), breaks=COLUMN_BREAKS, width=10,
                               bg_color=BG)
        self.titans.grid(row=1, column=0, sticky="ew")
        if titan:
            self.titans.set_enabled(False)
        value = personal.get(start, common)
        self.field = Field(body, label=get_text(lang, "rt_pt_value"), value=value, width=10,
                           hint=get_text(lang, "rt_pt_hint").format(n=common))
        self.field.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.field.entry.bind("<Return>", lambda _e: self.apply(), add="+")

        row = tk.Frame(self, bg=BG)
        row.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        self.apply_button = Button(row, get_text(lang, "btn_apply"), kind="blue", icon_name="check", icon_size=14,
                                   height=S["button_height_footer"], command=self.apply)
        self.apply_button.pack(side="right")
        self.cancel_button = Button(row, get_text(lang, "btn_cancel"), kind="secondary",
                                    height=S["button_height_footer"], command=self.close)
        self.cancel_button.pack(side="right", padx=(0, 10))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        present_window(self, lambda: self._place_centered(root), hidden=lambda: self._done,
                       on_shown=lambda: self._grab_when_visible(20))

    @property
    def done(self):
        return self._done

    def _place_centered(self, root):
        """Только место, не размер: окно растёт само, когда под полем появляется ошибка."""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        ax, ay, aw, ah = anchor_area(root)
        self.geometry(f"+{max(0, ax + (aw - w) // 2)}+{max(0, ay + (ah - h) // 3)}")

    def _grab_when_visible(self, tries):
        """Как ConfirmDialog: модальное, когда уже на экране, без wait_visibility."""
        if self._done:
            return
        try:
            if self.winfo_viewable():
                self.grab_set()
                self.field.entry.focus_set()
            elif tries > 0:
                self.after(50, self._grab_when_visible, tries - 1)
        except tk.TclError:
            pass

    def apply(self):
        value, error = rules_store.parse_number(self.field.get(), rules_store.PERCENT_MAX)
        if error:
            self.field.set_error(get_text(self.lang, "rt_range_error").format(lo=0, hi=rules_store.PERCENT_MAX))
            return
        titan = self.titans.get()
        self.close()
        self.on_apply(titan, value)

    def close(self):
        if self._done:
            return
        self._done = True
        try:
            self.grab_release()
            self.titans.destroy()   # меню списка живёт у окна
            self.destroy()
        except tk.TclError:
            pass


DIALOG_WIDTH = 440   # содержимое окна личного порога (без отступов 20 + 20)
