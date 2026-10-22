"""Мастер правил → «База и комнаты» (задача 15, шаг 5а; макет design/mockups/03a_rules_base).

«Параметры сессии»: карточка «Цели и лимиты» (цель — одна, час сброса дня, «Настроить Telegram» и его состояние) и
карточка «Безопасность и режим» (порог паники, дельта потерь, «Бот решает сам», ручная ульта Ангуса).
«Паки по комнатам»: строка на каждую комнату — основной пак (карандаш — окно «Собери состав»), «Запасные паки N шт.»
(раскрываются: удалить, «Добавить пак»), «+ Условие» (пока старое окно «Новое правило»: новое — шаг 5в).

Вкладка ничего не пишет сама: все значения лежат в форме страницы (ui/rules_page.py: page.form, page.teams),
пишет их кнопка «Сохранить настройки» (ваш ответ 22.10.2026). Любая правка зовёт page.changed().
Надписи — i18n.py (rb_*), смена языка — страница строит вкладку заново из формы.
"""
import tkinter as tk

import customtkinter as ctk

from i18n import get_text
from ui import rules_store, theme
from ui.icons import dot, icon
from ui.titan_picker import TitanPicker
from ui.widgets import Button, Card, ClickFrame, Dropdown, Field, IconButton, Switch, TitanAvatar

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

GOAL_TEXT_KEYS = {"titanite": "main_goal_titanite", "rooms": "main_goal_rooms", "floors": "main_goal_floors",
                  "time": "main_goal_time"}
LEFT_WIDTH = 300   # левая колонка строки комнаты (макет: grid-template-columns: 300px 1fr auto)
TOP_GAP = 24       # «Запасные паки» и «Условие» — вровень с квадратами пака (под названием стихии)


def line(master):
    """Разделительная линия 1 px (рамкой Tk: у CustomTkinter такая тонкая не рисуется)."""
    return tk.Frame(master, height=1, bg=C["border"])


def card_header(master, icon_name, text):
    head = ctk.CTkFrame(master, fg_color="transparent", width=10, height=10)
    ctk.CTkLabel(head, text="", image=icon(icon_name, C["blue_text"], 16), width=16, height=20).pack(side="left")
    ctk.CTkLabel(head, text=text, font=F["card_title"], text_color=C["text"], height=20).pack(side="left", padx=(8, 0))
    return head


class SwitchRow(ctk.CTkFrame):
    """Строка с тумблером: название, серая подпись под ним, тумблер справа."""

    def __init__(self, master, title, sub, value, command):
        super().__init__(master, fg_color="transparent", width=10, height=10)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=F["body_bold"], text_color=C["text"], anchor="w", height=18).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(self, text=sub, font=F["label"], text_color=C["text_muted"], anchor="w", height=16).grid(
            row=1, column=0, sticky="w", pady=(2, 0))
        self.switch = Switch(self, value=value, command=command)
        self.switch.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))


class BaseTab(ctk.CTkScrollableFrame):
    def __init__(self, master, page):
        super().__init__(master, fg_color="transparent", corner_radius=0,
                         scrollbar_button_color=C["border_strong"], scrollbar_button_hover_color=C["border_focus"])
        self.page = page
        self.lang = page.lang
        self.fields = {}
        self.rooms = {}
        self.grid_columnconfigure(0, weight=1)
        self._build_session()
        self._build_rooms()

    def text(self, key):
        return get_text(self.lang, key)

    # ── Параметры сессии ────────────────────────────────────────────────────
    def _build_session(self):
        ctk.CTkLabel(self, text=self.text("rb_session"), font=F["section"], text_color=C["text"], anchor="w",
                     height=20).grid(row=0, column=0, sticky="w", padx=(24, 12), pady=(18, 12))
        cards = ctk.CTkFrame(self, fg_color="transparent", width=10, height=10)
        cards.grid(row=1, column=0, sticky="ew", padx=(24, 12))
        cards.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        goals = Card(cards, width=10, height=10)
        goals.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        safety = Card(cards, width=10, height=10)
        safety.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._build_goals(goals)
        self._build_safety(safety)

    def _build_goals(self, card):
        form = self.page.form
        card.grid_columnconfigure(0, weight=1)
        card_header(card, "target", self.text("rb_goals_title")).grid(row=0, column=0, sticky="w", padx=16,
                                                                       pady=(16, 14))
        caption = ctk.CTkFrame(card, fg_color="transparent", width=10, height=10)
        caption.grid(row=1, column=0, sticky="w", padx=16)
        ctk.CTkLabel(caption, text=self.text("rb_goal_label"), font=F["label"], text_color=C["text_secondary"],
                     height=16).pack(side="left")
        ctk.CTkLabel(caption, text=" " + self.text("rb_goal_zero"), font=F["label"], text_color=C["text_muted"],
                     height=16).pack(side="left")

        row = ctk.CTkFrame(card, fg_color="transparent", width=10, height=10)
        row.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 0))
        row.grid_columnconfigure(0, weight=1)
        kind, value = form["goal"]
        self.goal_kind = Dropdown(row, self._goal_items(), kind, command=self._goal_kind_chosen,
                                  icons={k: theme.GOAL_ICONS[k] for k in rules_store.GOAL_KINDS})
        self.goal_kind.grid(row=0, column=0, sticky="ew")
        self.goal_value = ctk.CTkEntry(row, width=84, height=S["control_height"], corner_radius=S["radius_control"],
                                       border_width=1, border_color=C["border"], fg_color=C["bg_elevated"],
                                       text_color=C["text"], font=F["mono_field"])
        self.goal_value.insert(0, str(value))
        self.goal_value.grid(row=0, column=1, padx=(8, 0))
        self.goal_value.bind("<KeyRelease>", self._goal_typed, add="+")
        self.goal_reset = IconButton(row, "rotate-ccw", size=S["control_height"], icon_size=15,
                                     fg_color=C["bg_elevated"], hover_color=T["hover_elevated"],
                                     tooltip=lambda: self.text("rb_goal_reset"), command=self._goal_reset)
        self.goal_reset.grid(row=0, column=2, padx=(8, 0))

        hour = ctk.CTkFrame(card, fg_color="transparent", width=10, height=10)
        hour.grid(row=3, column=0, sticky="ew", padx=16, pady=(14, 0))
        hour.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hour, text=self.text("rb_reset_hour"), font=F["text"], text_color=C["text_secondary"],
                     anchor="w", height=20).grid(row=0, column=0, sticky="w")
        self.reset_hour = Dropdown(hour, [(h, f"{h:02d}:00") for h in range(24)], form["reset_hour"],
                                   command=self._reset_hour_chosen, width=96, mono=True)
        self.reset_hour.grid(row=0, column=1, padx=(12, 0))

        line(card).grid(row=4, column=0, sticky="ew", padx=16, pady=(14, 12))
        tg = ctk.CTkFrame(card, fg_color="transparent", width=10, height=10)
        tg.grid(row=5, column=0, sticky="w", padx=16, pady=(0, 16))
        self.tg_button = Button(tg, self.text("rb_tg_button"), kind="secondary", icon_name="send", icon_size=15,
                                pad_x=12, command=self.page.open_tg_dialog)
        self.tg_button.configure(image=icon("send", C["blue_text"], 15))
        self.tg_button.pack(side="left")
        self.tg_state = ctk.CTkLabel(tg, text="", font=F["label"], text_color=C["text_secondary"], height=20,
                                     compound="left")
        self.tg_state.pack(side="left", padx=(12, 0))
        self.show_telegram()

    def _build_safety(self, card):
        form = self.page.form
        card.grid_columnconfigure(0, weight=1)
        card_header(card, "shield-check", self.text("rb_safety_title")).grid(row=0, column=0, sticky="w", padx=16,
                                                                              pady=(16, 14))
        fields = ctk.CTkFrame(card, fg_color="transparent", width=10, height=10)
        fields.grid(row=1, column=0, sticky="ew", padx=16)
        fields.grid_columnconfigure((0, 1), weight=1, uniform="fields")
        for col, key in enumerate(("critical_hp", "max_hp_delta")):
            field = Field(fields, label=self.text("rb_panic" if key == "critical_hp" else "rb_delta"),
                          value=form[key], width=10)
            field.grid(row=0, column=col, sticky="ew", padx=(0, 6) if col == 0 else (6, 0))
            field.entry.bind("<KeyRelease>", lambda _e, k=key: self._percent_typed(k), add="+")
            self.fields[key] = field
            error = self.page.field_errors.get(key)
            if error is not None:  # язык сменили, пока в поле ошибка: показываем снова то, что было введено
                field.set(error)
                field.set_error(self.text("rb_percent_error"))

        line(card).grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 12))
        self.auto = SwitchRow(card, self.text("rb_auto"), self.text("rb_auto_sub"), form["auto_rollback"],
                              lambda on: self._switched("auto_rollback", on))
        self.auto.grid(row=3, column=0, sticky="ew", padx=16)
        line(card).grid(row=4, column=0, sticky="ew", padx=16, pady=12)
        self.angus = SwitchRow(card, self.text("rb_angus"), self.text("rb_angus_sub"), form["angus_manual_control"],
                               lambda on: self._switched("angus_manual_control", on))
        self.angus.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 16))

    def _goal_items(self):
        return [(k, theme.plain_text(self.text(GOAL_TEXT_KEYS[k]))) for k in rules_store.GOAL_KINDS]

    # ── Правки ──────────────────────────────────────────────────────────────
    def _goal_kind_chosen(self, kind):
        """Другой вид цели: число остаётся то, что в поле (цель одна — остальные при сохранении станут нулями)."""
        self.page.form["goal"] = (kind, self.page.form["goal"][1])
        self.page.changed()

    def _goal_typed(self, _event=None):
        """В поле цели — только цифры (как в старой вкладке), пусто — 0."""
        text = self.goal_value.get()
        clean = "".join(ch for ch in text if ch.isdigit())[:len(str(rules_store.GOAL_MAX))]
        if clean != text:
            self.goal_value.delete(0, "end")
            self.goal_value.insert(0, clean)
        value = int(clean) if clean else 0
        if value != self.page.form["goal"][1]:
            self.page.form["goal"] = (self.page.form["goal"][0], value)
            self.page.changed()

    def _goal_reset(self):
        """«Сбросить цель» — 0, без лимита (старая «Сбросить все» тоже обнуляла цели)."""
        self.goal_value.delete(0, "end")
        self.goal_value.insert(0, "0")
        self._goal_typed()

    def _reset_hour_chosen(self, hour):
        self.page.form["reset_hour"] = hour
        self.page.changed()

    def _percent_typed(self, key):
        field = self.fields[key]
        value, error = rules_store.parse_number(field.get(), rules_store.PERCENT_MAX)
        if error:
            if self.page.field_errors.get(key) != field.get() or not field.error:
                field.set_error(self.text("rb_percent_error"))
            self.page.field_errors[key] = field.get()
        else:
            if field.error:
                field.set_error(None)
            self.page.field_errors.pop(key, None)
            self.page.form[key] = value
        self.page.changed()

    def _switched(self, key, on):
        self.page.form[key] = on
        self.page.changed()

    def show_telegram(self):
        on = rules_store.telegram_on(self.page.form["telegram"])
        color = C["success"] if on else C["text_muted"]
        self.tg_state.configure(text=" " + self.text("rb_tg_on" if on else "rb_tg_off"), image=dot(color, 7))

    # ── Паки по комнатам ────────────────────────────────────────────────────
    def _build_rooms(self):
        head = ctk.CTkFrame(self, fg_color="transparent", width=10, height=10)
        head.grid(row=2, column=0, sticky="ew", padx=(24, 12), pady=(22, 12))
        ctk.CTkLabel(head, text=self.text("rb_packs"), font=F["section"], text_color=C["text"], height=20).pack(
            side="left")
        ctk.CTkLabel(head, text=self.text("rb_packs_hint"), font=F["label"], text_color=C["text_muted"],
                     height=20).pack(side="left", padx=(12, 0))
        for i, room in enumerate(rules_store.ROOMS):
            row = RoomRow(self, self.page, room)
            row.grid(row=3 + i, column=0, sticky="ew", padx=(24, 12), pady=(0, 12 if i < 3 else 20))
            self.rooms[room] = row


class RoomRow(Card):
    """Строка комнаты: значок и название стихии, основной пак и карандаш; «Запасные паки N шт.»; «+ Условие»."""

    def __init__(self, master, page, room):
        super().__init__(master, width=10, height=10)
        self.page = page
        self.room = room
        self.lang = page.lang
        self.grid_columnconfigure(0, minsize=LEFT_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.build()

    def text(self, key):
        return get_text(self.lang, key)

    def build(self):
        for child in self.winfo_children():
            child.destroy()
        style = theme.element_style(self.room)
        left = ctk.CTkFrame(self, fg_color="transparent", width=10, height=10)
        left.grid(row=0, column=0, sticky="nw", padx=(16, 0), pady=14)
        badge = ctk.CTkFrame(left, width=40, height=40, corner_radius=8, fg_color=style["tint"])
        badge.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="", image=icon(style["icon"], style["color"], 20)).place(relx=0.5, rely=0.5,
                                                                                       anchor="center")
        title = ctk.CTkFrame(left, fg_color="transparent", width=10, height=10)
        title.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(title, text=theme.plain_text(self.text(f"elem_{self.room}")), font=F["card_title"],
                     text_color=style["text"], height=18).pack(side="left")
        ctk.CTkLabel(title, text=self.text("rb_main_pack"), font=F["label"], text_color=C["text_muted"],
                     height=18).pack(side="left", padx=(8, 0))
        pack = ctk.CTkFrame(left, fg_color="transparent", width=10, height=10)
        pack.grid(row=1, column=1, sticky="w", pady=(6, 0))
        team = self.page.teams[self.room]
        for titan in team:
            TitanAvatar(pack, titan, lang=self.lang).pack(side="left", padx=(0, 6))
        if not team:
            ctk.CTkLabel(pack, text=theme.plain_text(self.text("rules_no_pack")), font=F["label"],
                         text_color=C["text_muted"], height=36).pack(side="left", padx=(0, 10))
        self.edit = IconButton(pack, "pencil", size=32, icon_size=14, fg_color="transparent",
                               hover_color=C["bg_elevated"], tooltip=lambda: self.text("rb_edit_pack"),
                               command=self.edit_main)
        self.edit.pack(side="left")

        self.backups = BackupBox(self, self.page, self.room)
        self.backups.grid(row=0, column=1, sticky="new", padx=(20, 0), pady=(14 + TOP_GAP, 14))
        self.condition = Button(self, self.text("rb_condition"), kind="secondary", icon_name="plus", icon_size=14,
                                pad_x=12, fg_color="transparent", hover_color=C["bg_elevated"],
                                command=lambda: self.page.add_condition(self.room))
        self.condition.grid(row=0, column=2, sticky="ne", padx=(20, 16), pady=(14 + TOP_GAP, 14))

    def edit_main(self):
        """Карандаш — окно «Собери состав» (только титаны этой стихии; в смешанную — все)."""
        TitanPicker(self, self.lang, on_apply=lambda team: self.page.set_team(self.room, team), room=self.room,
                    selected=self.page.teams[self.room])


class BackupBox(ctk.CTkFrame):
    """«Запасные паки N шт.»: щелчок раскрывает список (номер, пак, ✕ удалить) и «Добавить пак» (до 5 паков)."""

    def __init__(self, master, page, room):
        super().__init__(master, fg_color="transparent", width=10, height=10)
        self.page = page
        self.room = room
        self.lang = page.lang
        self.grid_columnconfigure(0, weight=1)
        packs = page.form["backup_teams"].get(room, [])
        expanded = page.expanded.get(room, False)
        self.toggle = BackupToggle(self, get_text(self.lang, "rb_backups"),
                                   get_text(self.lang, "rb_pcs").format(n=len(packs)), expanded, self.flip)
        self.toggle.grid(row=0, column=0, sticky="ew")
        self.rows = []
        if not expanded:
            return
        for i, pack in enumerate(packs):
            row = ctk.CTkFrame(self, fg_color=C["bg_primary"], border_width=1, border_color=C["border"],
                               corner_radius=S["radius_control"], width=10, height=10)
            row.grid(row=1 + i, column=0, sticky="ew", pady=(8, 0))
            ctk.CTkLabel(row, text=f"#{i + 1}", font=F["mono"], text_color=C["text_muted"], width=22,
                         anchor="w").pack(side="left", padx=(10, 6), pady=6)
            for titan in pack:
                TitanAvatar(row, titan, lang=self.lang).pack(side="left", padx=(0, 6), pady=6)
            IconButton(row, "x", size=32, icon_size=14, fg_color="transparent", hover_color=C["bg_elevated"],
                       border_width=0, icon_color=C["text_muted"],
                       tooltip=lambda: get_text(self.lang, "rb_remove_pack"),
                       command=lambda i=i: self.page.remove_backup(self.room, i)).pack(side="right", padx=6)
            self.rows.append(row)
        if len(packs) < rules_store.MAX_BACKUPS:
            self.add = Button(self, get_text(self.lang, "rb_add_pack"), kind="secondary", icon_name="plus",
                              icon_size=14, height=34, fg_color="transparent", hover_color=C["bg_elevated"],
                              border_color=C["border_focus"], text_color=C["text_secondary"], command=self.add_pack)
            self.add.grid(row=1 + len(packs), column=0, sticky="ew", pady=(8, 0))

    def flip(self):
        self.page.expanded[self.room] = not self.page.expanded.get(self.room, False)
        self.page.rebuild_room(self.room)

    def add_pack(self):
        TitanPicker(self, self.lang, on_apply=lambda team: self.page.add_backup(self.room, team), room=self.room)


class BackupToggle(ClickFrame):
    """Кнопка «Запасные паки [N шт.] ▾» (раскрыта — рамка светлее и стрелка вверх). Наведение — только цвет фона."""

    def __init__(self, master, text, count, expanded, command):
        super().__init__(master, command=command, height=S["control_height"], width=10,
                         corner_radius=S["radius_control"], border_width=1,
                         border_color=C["border_focus"] if expanded else C["border"], fg_color=C["bg_elevated"])
        self._look = None
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)
        label = ctk.CTkLabel(self, text=text, font=F["button"], text_color=C["text"], height=20)
        label.grid(row=0, column=0, padx=(12, 8))
        pill = ctk.CTkLabel(self, text=count, font=F["label"], text_color=C["text_secondary"], height=18,
                            corner_radius=9, fg_color=C["bg_primary"])
        pill.grid(row=0, column=1)
        arrow = ctk.CTkLabel(self, text="", image=icon("chevron-up" if expanded else "chevron-down",
                                                       C["text_muted"], 16), width=16, height=20)
        arrow.grid(row=0, column=3, padx=(0, 10))
        self.bind_parts(label, pill, arrow)
        self._paint()

    def _paint(self):
        look = T["hover_elevated"] if self._hovering else C["bg_elevated"]
        if look != self._look:
            self._look = look
            self.configure(fg_color=look)

