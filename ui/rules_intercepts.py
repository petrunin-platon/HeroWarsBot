"""Мастер правил → «Правила и перехваты» (задача 15, шаг 5в; макет design/mockups/03c_rules_intercepts) — вместо окна
«Активные правила» (ui/active_rules_dialog.py, его оставляем старому окну).

Сверху «Активные правила» и их число, справа подсказка о порядке; фильтры «Все / Земля / Вода / Огонь / Смешанная» и справа
«+ Новое правило» (окно ui/rule_editor.py). Ниже шапка колонок «№ · Условие · Действие · Вкл.» и список. В строке: номер
(и ↑↓, когда выбрана одна стихия — как в старом окне, ваш ответ: бот проверяет правила по порядку только внутри стихии),
значки стихии и типа, название и условие, действие (квадраты пака или значок), тумблер, карандаш и ✕.
Выключенное правило бледное, но не удалено (бот его пропускает: enabled: false). ✕ — уведомление «Правило удалено —
Вернуть». «Очистить все правила» удаляет то, что видно (ваш ответ), после вопроса; потом тоже можно «Вернуть».

Как остальные вкладки, эта ничего не пишет сама: список — в форме страницы (page.rules), пишет «Сохранить настройки».
Что и как показать — ui/rules_list.py (без Tk). Список может быть длинным (бот запоминает правила сам), поэтому в строке
нет ни одного элемента CustomTkinter: скругление — готовая картинка (RoundedBackdrop), внутри — обычные надписи
и картинки Tk (PlainLabel, ElidedLabel, pill_label, TitanTile, PlainSwitch, PlainIconButton), одинаковые картинки — одни
на окно (shared_photo). У каждого элемента CustomTkinter свой холст, и в Windows такие списки дорисовывались с задержкой
(проверка шага 5а). Строки строятся один раз; фильтр только показывает и прячет их, стрелки и тумблер меняют одну-две
строки.
"""
import tkinter as tk

import customtkinter as ctk

from i18n import get_text
from ui import rules_list, theme
from ui.icons import icon
from ui.widgets import (Button, Card, Chip, ConfirmDialog, ElidedLabel, PlainIconButton, PlainLabel, PlainSwitch,
                        RoundedBackdrop, TitanTile, Toast, pill_label, plain_icon)

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

BG = C["bg_surface"]          # карточка списка
ROW_BG = C["bg_elevated"]     # строка правила
COLUMNS = (34, 0, 280, 40, 66)   # макет: 34px · 1fr · 280px · 40px · 66px, между колонками 14px
GAP = 14
ROW_PAD = (10, 12)               # отступ строки слева и справа (макет: padding 8px 12px 8px 10px)
SCROLLBAR = 22                   # полоса прокрутки CTkScrollableFrame с её отступами
BUILD_CHUNK = 4                  # длинный список строится частями по столько строк: окно между ними отвечает
BUILD_GAP_MS = 1


def px(widget, value):
    return round(value * ctk.ScalingTracker.get_widget_scaling(widget))


def dimmed(color, on, bg=ROW_BG):
    return color if on else theme.blend(color, bg, theme.RULE_DIM)


def set_columns(frame):
    """Колонки строки и шапки «№ · Условие · Действие · Вкл.» одинаковые: ширина колонки — её место и промежуток
    до следующей (содержимое уже этого места), первая — с отступом строки слева, последняя — справа."""
    last = len(COLUMNS) - 1
    for col, width in enumerate(COLUMNS):
        size = width + (ROW_PAD[0] if col == 0 else 0) + (ROW_PAD[1] if col == last else GAP)
        if width:
            frame.grid_columnconfigure(col, minsize=px(frame, size))
        else:
            frame.grid_columnconfigure(col, weight=1)


class InterceptsTab(tk.Frame):
    def __init__(self, master, page):
        super().__init__(master, bg=C["bg_primary"])
        self.page = page
        self.lang = page.lang
        self.room_filter = None      # None — «Все»
        self.rows = {room: [] for room in rules_list.ROOMS}
        self._pending = []           # строки, которые ещё строятся: [(стихия, номер)]
        self._build_id = None
        self._dialog = None
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        card = Card(self, width=10, height=10, bg_color=C["bg_primary"])
        card.grid(row=0, column=0, sticky="nsew", padx=24, pady=(18, 20))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(3, weight=1)
        self.card = card
        self._build_head(card)
        self._build_filters(card)
        self._build_columns(card)
        self.list = ctk.CTkScrollableFrame(card, fg_color=BG, corner_radius=0,
                                           scrollbar_button_color=C["border_strong"],
                                           scrollbar_button_hover_color=C["border_focus"])
        self.list.grid(row=3, column=0, sticky="nsew", padx=(16, 8), pady=(6, 0))
        self.list.grid_columnconfigure(0, weight=1)
        self.empty = PlainLabel(self.list, self.text("ri_empty"), font=F["text"], color=C["text_muted"], bg=BG,
                                anchor="w", justify="left")
        bottom = tk.Frame(card, bg=BG)
        bottom.grid(row=4, column=0, sticky="ew", padx=16, pady=(10, 14))
        self.clear_button = Button(bottom, self.text("ri_clear"), kind="ghost_danger", icon_name="trash-2",
                                   icon_size=15, height=32, pad_x=10, command=self.ask_clear)
        self.clear_button.pack(side="left")
        self.rebuild()

    def text(self, key):
        return get_text(self.lang, key)

    # ── Шапка ───────────────────────────────────────────────────────────────
    def _build_head(self, card):
        head = tk.Frame(card, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        head.grid_columnconfigure(2, weight=1)
        PlainLabel(head, self.text("ri_title"), font=F["section"], color=C["text"]).grid(row=0, column=0)
        self.count_box = tk.Frame(head, bg=BG)
        self.count_box.grid(row=0, column=1, padx=(px(head, 10), 0))
        self.count_pill = None
        self.hint = PlainLabel(head, "", font=F["label"], color=C["text_muted"])
        self.hint.grid(row=0, column=2, sticky="e", padx=(12, 0))

    def _build_filters(self, card):
        row = tk.Frame(card, bg=BG)
        row.grid(row=1, column=0, sticky="ew", padx=16)
        row.grid_columnconfigure(5, weight=1)
        self.chips = {}
        for col, room in enumerate((None,) + rules_list.ROOMS):
            if room is None:
                chip = Chip(row, self.text("ri_all"), selected=True, command=lambda: self.choose(None),
                            bg_color=BG)
            else:
                chip = Chip(row, theme.plain_text(self.text(f"elem_{room}")), command=lambda r=room: self.choose(r),
                            dot_color=theme.element_style(room)["color"], bg_color=BG)
            chip.grid(row=0, column=col, padx=(0, 6))
            self.chips[room] = chip
        self.new_button = Button(row, self.text("ri_new"), kind="secondary", icon_name="plus", icon_size=14,
                                 height=30, pad_x=10, border_color=C["border_strong"], font=F["button_bold"],
                                 command=lambda: self.page.open_rule_editor(self.room_filter or "mix"))
        self.new_button.configure(image=icon("plus", C["blue_text"], 14))
        self.new_button.grid(row=0, column=6, sticky="e")

    def _build_columns(self, card):
        """Шапка колонок — над строками: слева рамка строки (1 px), справа ещё и полоса прокрутки списка."""
        head = tk.Frame(card, bg=BG)
        head.grid(row=2, column=0, sticky="ew", padx=(16 + 1, 8 + SCROLLBAR + 1), pady=(12, 0))
        set_columns(head)
        for col, key in enumerate(("ri_col_num", "ri_col_cond", "ri_col_action", "ri_col_on")):
            PlainLabel(head, self.text(key), font=F["label"], color=C["text_muted"], anchor="w").grid(
                row=0, column=col, sticky="w", padx=(px(head, ROW_PAD[0]) if col == 0 else 0, 0))

    # ── Список ──────────────────────────────────────────────────────────────
    def rebuild(self):
        """Все строки заново (свежие правила с диска, «Вернуть» после «Очистить»). Первые строки — сразу, остальные —
        частями через after: 48 строк строились ~0,7 с, и окно на это время замирало бы."""
        self._cancel_build()
        for rows in self.rows.values():
            for row in rows:
                row.destroy()
        self.rows = {room: [] for room in rules_list.ROOMS}
        shown_first = sorted(rules_list.ROOMS, key=lambda room: self.room_filter not in (None, room))
        self._pending = [(room, i) for room in shown_first for i in range(len(self.page.rules[room]))]
        self._build_step()

    def _build_step(self):
        self._build_id = None
        for room, index in self._pending[:BUILD_CHUNK]:
            self.rows[room].append(RuleRow(self.list, self, room, index, self.page.rules[room][index]))
        del self._pending[:BUILD_CHUNK]
        self.show()
        if self._pending:
            self._build_id = self.after(BUILD_GAP_MS, self._build_step)

    def finish_building(self):
        """Достроить список сразу (перед правкой: стрелка или «Вернуть» могут задеть ещё не построенную строку)."""
        self._cancel_build()
        while self._pending:
            self._build_step()
        self._cancel_build()

    def _cancel_build(self):
        if self._build_id is not None:
            try:
                self.after_cancel(self._build_id)
            except tk.TclError:
                pass
            self._build_id = None

    def destroy(self):
        self._cancel_build()
        super().destroy()

    def show(self):
        """Показать строки выбранной стихии (или все), по порядку: стихии подряд, внутри — как в файле."""
        place = 0
        for room in rules_list.ROOMS:
            for row in self.rows[room]:
                if self.room_filter in (None, room):
                    row.grid(row=place, column=0, sticky="ew", pady=(0, 8))
                    row.show_arrows(self.room_filter is not None)
                    place += 1
                else:
                    row.grid_remove()
        count = len(rules_list.visible(self.page.rules, self.room_filter))
        if count:
            self.empty.grid_remove()
        else:
            self.empty.grid(row=0, column=0, sticky="w", pady=(4, 0))
        self._show_count(count)
        hint = self.text("ri_hint_room" if self.room_filter else "ri_hint_all")
        if self.hint.cget("text") != hint:
            self.hint.configure(text=hint)
        self.clear_button.set_enabled(count > 0)

    def _show_count(self, count):
        if self.count_pill is not None and self.count_pill.cget("text") == str(count):
            return
        if self.count_pill is not None:
            self.count_pill.destroy()
        self.count_pill = pill_label(self.count_box, str(count), F["label"], C["text_secondary"], C["bg_elevated"],
                                     BG, height=18, radius=9, pad_x=8)
        self.count_pill.pack()

    def choose(self, room):
        if room == self.room_filter:
            return
        self.room_filter = room
        for key, chip in self.chips.items():
            chip.set_selected(key == room)
        self.show()

    def renumber(self, room):
        for i, row in enumerate(self.rows[room]):
            row.set_index(i)

    # ── Правки ──────────────────────────────────────────────────────────────
    def move(self, room, index, delta):
        self.finish_building()
        if not rules_list.move(self.page.rules, room, index, delta):
            return
        rows = self.rows[room]
        rows[index], rows[index + delta] = rows[index + delta], rows[index]
        for i in (index, index + delta):
            rows[i].set_index(i)
        self.show()
        self.page.changed()

    def toggled(self, room, index, on):
        self.finish_building()
        rules_list.set_enabled(self.page.rules[room][index], on)
        self.rows[room][index].draw_content()
        self.page.changed()

    def edit(self, room, index):
        self.page.open_rule_editor(room, index)

    def delete(self, room, index):
        self.finish_building()
        removed = rules_list.remove(self.page.rules, room, index)
        title = rules_list.title_and_sub(removed[2], self.lang)[0]
        self.rows[room].pop(index).destroy()
        self.renumber(room)
        self.show()
        self.page.changed()
        Toast(self, self.text("ri_deleted").format(name=title), kind="deleted", action_text=self.text("ri_undo"),
              on_action=lambda: self.put_back([removed]))

    def put_back(self, removed):
        """«Вернуть»: одно правило — одна новая строка, после «Очистить» — список заново (частями)."""
        self.finish_building()
        if len(removed) == 1:
            room, index, rule = removed[0]
            index = min(index, len(self.page.rules[room]))   # туда же его вставит rules_list.put_back
            rules_list.put_back(self.page.rules, removed)
            self.rows[room].insert(index, RuleRow(self.list, self, room, index, rule))
            self.renumber(room)
            self.show()
        else:
            rules_list.put_back(self.page.rules, removed)
            self.rebuild()
        self.page.changed()

    def rule_put(self, room, place, old_room=None, old_index=None):
        """Правило из окна «Новое правило» уже в форме (rules_list.put): поменять только его строки."""
        self.finish_building()
        if old_room == room and old_index == place:
            self.rows[room][place].draw_content()
            return
        if old_room is not None:
            self.rows[old_room].pop(old_index).destroy()
            self.renumber(old_room)
        self.rows[room].insert(place, RuleRow(self.list, self, room, place, self.page.rules[room][place]))
        self.renumber(room)
        self.show()

    def ask_clear(self):
        if self._dialog is not None and not self._dialog.done:
            self._dialog.lift()
            return
        shown = rules_list.visible(self.page.rules, self.room_filter)
        if not shown:
            return
        where = (theme.plain_text(self.text(f"elem_{self.room_filter}")) if self.room_filter
                 else self.text("ri_where_all"))
        self._dialog = ConfirmDialog(self, self.text("ri_clear_title"),
                                     self.text("ri_clear_text").format(n=len(shown), where=where),
                                     self.text("ri_clear_ok"), on_confirm=self.clear, kind="danger", lang=self.lang)

    def clear(self):
        self.finish_building()
        removed = rules_list.clear(self.page.rules, self.room_filter)
        for room in {room for room, _i, _r in removed}:
            for row in self.rows[room]:
                row.destroy()
            self.rows[room] = []
        self.show()
        self.page.changed()
        if removed:
            Toast(self, self.text("ri_cleared").format(n=len(removed)), kind="deleted",
                  action_text=self.text("ri_undo"), on_action=lambda: self.put_back(removed))


class RuleRow(tk.Frame):
    """Строка правила (макет 03c): № и ↑↓ · значки, название, условие · действие · тумблер · карандаш и ✕.
    Скругление и рамка — готовая картинка под содержимым (RoundedBackdrop), а не холст CustomTkinter: с ним
    48 строк строились почти 2 с."""

    def __init__(self, master, tab, room, index, rule):
        super().__init__(master, bg=BG)
        self.backdrop = RoundedBackdrop(self, ROW_BG, C["border"], BG, radius=8)
        self.tab = tab
        self.room = room
        self.index = index
        self.lang = tab.lang
        set_columns(self)
        self.grid_rowconfigure(0, weight=1)

        num = tk.Frame(self, bg=ROW_BG)
        num.grid(row=0, column=0, padx=(px(self, ROW_PAD[0]), 0), pady=px(self, 8))
        self.up = PlainIconButton(num, "chevron-up", command=lambda: tab.move(self.room, self.index, -1), size=14,
                                  bg=ROW_BG, tooltip=lambda: get_text(self.lang, "ri_up"), pad=6, pad_y=2)
        self.number = PlainLabel(num, "", font=F["mono"], color=C["text_muted"], bg=ROW_BG)
        self.number.grid(row=1, column=0)
        self.down = PlainIconButton(num, "chevron-down", command=lambda: tab.move(self.room, self.index, 1), size=14,
                                    bg=ROW_BG, tooltip=lambda: get_text(self.lang, "ri_down"), pad=6, pad_y=2)
        self.arrows_shown = None

        self.words = tk.Frame(self, bg=ROW_BG)
        self.words.grid(row=0, column=1, sticky="ew", padx=(0, px(self, GAP)), pady=px(self, 8))
        self.words.grid_columnconfigure(0, weight=1)
        self.action = tk.Frame(self, bg=ROW_BG)
        self.action.grid(row=0, column=2, sticky="w")

        self.switch = PlainSwitch(self, command=lambda on: tab.toggled(self.room, self.index, on), bg=ROW_BG,
                                  tooltip=lambda: get_text(self.lang, "ri_switch"))
        self.switch.grid(row=0, column=3, sticky="w")
        tools = tk.Frame(self, bg=ROW_BG)
        tools.grid(row=0, column=4, sticky="e", padx=(0, px(self, ROW_PAD[1] - 6)))
        self.edit_button = PlainIconButton(tools, "pencil", command=lambda: tab.edit(self.room, self.index),
                                           size=14, bg=ROW_BG, tooltip=lambda: get_text(self.lang, "ri_edit"))
        self.edit_button.pack(side="left")
        self.delete_button = PlainIconButton(tools, "x", command=lambda: tab.delete(self.room, self.index), size=14,
                                             bg=ROW_BG, color=C["text_muted"],
                                             tooltip=lambda: get_text(self.lang, "ri_delete"))
        self.delete_button.pack(side="left")
        self.set_index(index)
        self.draw_content()

    @property
    def rule(self):
        return self.tab.page.rules[self.room][self.index]

    def set_index(self, index):
        """Номер в своей стихии; ↑ недоступна у первого, ↓ — у последнего."""
        self.index = index
        self.number.configure(text=str(index + 1))
        self.up.set_enabled(index > 0)
        self.down.set_enabled(index < len(self.tab.page.rules[self.room]) - 1)

    def show_arrows(self, shown):
        """↑↓ — только когда выбрана одна стихия (как в старом окне)."""
        if shown == self.arrows_shown:
            return
        self.arrows_shown = shown
        if shown:
            self.up.grid(row=0, column=0)
            self.down.grid(row=2, column=0)
        else:
            self.up.grid_remove()
            self.down.grid_remove()

    def draw_content(self):
        """Значки, название, условие и действие. Выключенное правило — бледное (макет: opacity 0.45)."""
        for child in self.words.winfo_children() + self.action.winfo_children():
            child.destroy()
        info = rules_list.summary(self.rule, self.lang)
        on = info["enabled"]
        self.switch.set_on(on)
        line = tk.Frame(self.words, bg=ROW_BG)
        line.grid(row=0, column=0, sticky="ew")
        line.grid_columnconfigure(2, weight=1)
        fg, fill = theme.rule_room_badge(self.room)
        pill_label(line, theme.plain_text(get_text(self.lang, f"elem_{self.room}")), F["small"], dimmed(fg, on),
                   dimmed(fill, on), ROW_BG).grid(row=0, column=0, padx=(0, px(self, 6)))
        if info["tag"]:
            fg, fill = theme.RULE_TAG_COLORS[info["tag"]]
            pill_label(line, get_text(self.lang, f"ri_tag_{info['tag']}"), F["small_bold"], dimmed(fg, on),
                       dimmed(fill, on), ROW_BG).grid(row=0, column=1, padx=(0, px(self, 6)))
        self.title = ElidedLabel(line, info["title"], font=F["body_bold"], color=dimmed(C["text"], on), bg=ROW_BG)
        self.title.grid(row=0, column=2, sticky="ew")
        self.sub = ElidedLabel(self.words, info["sub"], font=F["label"], color=dimmed(C["text_secondary"], on),
                               bg=ROW_BG)
        self.sub.grid(row=1, column=0, sticky="ew", pady=(px(self, 5), 0))

        self.arrow_picture = plain_icon(self.action, "arrow-right", dimmed(C["text_muted"], on), 14)
        tk.Label(self.action, image=self.arrow_picture, bg=ROW_BG, bd=0, highlightthickness=0).pack(
            side="left", padx=(0, px(self, 8)))
        if info["action"] == rules_list.PACK:
            tiles = tk.Frame(self.action, bg=ROW_BG)
            tiles.pack(side="left")
            for titan in info["team"]:
                TitanTile(tiles, titan, lang=self.lang, size=S["avatar_small"], bg=ROW_BG, dim=not on).pack(
                    side="left", padx=(0, px(self, 3)))
            PlainLabel(self.action, get_text(self.lang, "ri_act_pack"), font=F["label"],
                       color=dimmed(C["text_secondary"], on), bg=ROW_BG).pack(side="left", padx=(px(self, 5), 0))
        else:
            fg, fill = theme.RULE_ACTION_COLORS[info["action"]]
            pill_label(self.action, get_text(self.lang, f"ri_act_{info['action']}"), F["label"], dimmed(fg, on),
                       dimmed(fill, on), ROW_BG, height=26, radius=13, pad_x=10).pack(side="left")
