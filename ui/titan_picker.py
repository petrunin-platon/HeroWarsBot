"""Окно «Собери состав» (задача 15, шаг 3; макет design/mockups/03e_titan_picker): выбрать от 3 до 5 титанов.

Сейчас открывается из окон вмешательства: «Откатить бой» и «Попробовать другой» (пак для переигровки) и
«Собрать новый пак». На шаге 5а это же окно откроет мастер правил (основной пак, условие).
Вместо старого ui/team_selector.py (его оставляем старому окну).

Как в макете: сверху 5 слотов (щелчок по титану убирает его), «Выбрано: N / 5» и состояние (жёлтое «Минимум 3 · нужно
ещё K», зелёное «Можно применять»), «Очистить»; ниже 5 колонок по стихиям; выбранный — зелёная рамка и галочка;
когда выбрано 5, остальные блокируются; «Применить» недоступна, пока выбрано меньше трёх.
Ваши ответы 22.10.2026: в комнату земли, воды и огня встают только титаны этой стихии (другие колонки серые), в смешанную —
все. Паллант, Орм и Алекто — эларитовые, но стоят в колонке своей стихии и встают в её комнату. Метида — только эларит:
отдельная строка «Эларит», выбрать её можно только для смешанной комнаты (ui/theme.py: room_titans).
Крестик окна и «Отмена» — on_cancel (окно вмешательства возвращается на экран).
"""
from functools import lru_cache

import customtkinter as ctk
from PIL import Image, ImageDraw

from i18n import get_text
from ui import theme
from ui.icons import dot, icon
from ui.widgets import Button, ClickFrame, TitanAvatar, titan_name

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

MIN_TITANS, MAX_TITANS = 3, 5
SLOT = 52
ROW_HEIGHT = 40
WINDOW = (900, 676)


@lru_cache(maxsize=4)
def empty_slot_image(size=SLOT):
    """Пустой слот: пунктирная рамка 1,5 px со скруглением и плюс посередине (в Tk пунктирной рамки у виджетов нет)."""
    k = 4
    big = size * k
    width = round(1.5 * k)
    radius = 8 * k
    rgb = tuple(int(C["border_focus"][i:i + 2], 16) for i in (1, 3, 5))
    line = Image.new("L", (big, big), 0)
    ImageDraw.Draw(line).rounded_rectangle((0, 0, big - 1, big - 1), radius=radius, outline=255, width=width)
    dash = 5 * k
    mask = Image.new("L", (big, big), 0)
    pixels = mask.load()
    for y in range(big):
        for x in range(big):
            in_row = y < radius or y >= big - radius
            in_col = x < radius or x >= big - radius
            if in_row and in_col:
                pixels[x, y] = 255                      # скругления — сплошные
            elif y < width or y >= big - width:
                pixels[x, y] = 255 if (x // dash) % 2 == 0 else 0
            else:
                pixels[x, y] = 255 if (y // dash) % 2 == 0 else 0
    img = Image.new("RGBA", (big, big), rgb + (0,))
    img.putalpha(Image.composite(line, Image.new("L", (big, big), 0), mask))
    plus = icon_image("plus", C["text_muted"], 16 * k)
    img.alpha_composite(plus, ((big - plus.width) // 2, (big - plus.height) // 2))
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def icon_image(name, color, size):
    """Иконка как картинка PIL (для рисования поверх другой картинки)."""
    from ui.icons import _colored
    return _colored(name, color.upper()).resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=4)
def check_badge(size=18):
    """Зелёный кружок с белой галочкой — титан выбран."""
    k = 4
    img = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
    rgb = tuple(int(C["green"][i:i + 2], 16) for i in (1, 3, 5))
    ImageDraw.Draw(img).ellipse((0, 0, size * k - 1, size * k - 1), fill=rgb + (255,))
    mark = icon_image("check", C["white"], 11 * k)
    img.alpha_composite(mark, ((size * k - mark.width) // 2, (size * k - mark.height) // 2))
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


class TitanChoice(ClickFrame):
    """Строка титана в колонке: квадрат, имя, галочка у выбранного. Выбран — зелёная рамка и зелёный оттенок;
    нельзя выбрать (чужая стихия или уже выбрано 5) — бледная и не нажимается."""

    def __init__(self, master, titan, lang, command):
        super().__init__(master, command=lambda: command(titan), height=ROW_HEIGHT, corner_radius=8, border_width=1,
                         fg_color=C["bg_surface"], border_color=C["border"])
        self.titan = titan
        self.selected = False
        self._look = None
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.avatar = TitanAvatar(self, titan, lang=lang, size=28, tooltip=False)
        self.avatar.grid(row=0, column=0, padx=(6, 8))
        self.name = ctk.CTkLabel(self, text=titan_name(lang, titan), font=F["text"], text_color=C["text"], anchor="w",
                                 height=20)
        self.name.grid(row=0, column=1, sticky="w")
        self.check = ctk.CTkLabel(self, text="", image=check_badge(), width=18, height=18)
        self.bind_parts(self.avatar, self.avatar.label, self.name, self.check)
        self._paint()

    def _paint(self):
        if self.selected:
            look = (T["green_on_surface"], C["green"], C["text"], True)
        elif not self.enabled:
            look = (C["bg_surface"], C["border"], C["text_muted"], False)
        else:
            look = (C["bg_surface"], C["border_focus"] if self._hovering else C["border"], C["text"], False)
        if look == self._look:
            return
        old = self._look or (None, None, None, None)
        self._look = look
        fg, border, text, checked = look
        if (fg, border) != old[:2]:
            self.configure(fg_color=fg, border_color=border)
        if text != old[2]:
            self.name.configure(text_color=text)
            self.avatar.set_dim(text == C["text_muted"])
        if checked != old[3]:
            if checked:
                self.check.grid(row=0, column=2, padx=(4, 8))
            else:
                self.check.grid_remove()

    def set_state(self, selected, enabled):
        self.selected = selected
        self.enabled = enabled
        self._paint()

    def set_language(self, lang):
        self.name.configure(text=titan_name(lang, self.titan))
        self.avatar.set_language(lang)


class TitanPicker(ctk.CTkToplevel):
    """room — комната ("earth", "water", "fire", "mix" или None — все стихии); selected — кто выбран сразу
    (только те, кого можно в эту комнату). on_apply(список титанов) — «Применить», on_cancel() — крестик и «Отмена»."""

    def __init__(self, master, lang, on_apply, on_cancel=None, room=None, selected=(), apply_text=None,
                 apply_kind="save"):
        root = master.winfo_toplevel()
        super().__init__(root, fg_color=C["bg_primary"])
        self.withdraw()
        self.lang = lang
        self.room = room
        self.on_apply = on_apply
        self.on_cancel = on_cancel
        self.allowed = set(theme.room_titans(room))
        self.chosen = [t for t in selected if t in self.allowed][:MAX_TITANS]
        self.rows = {}
        self._done = False
        self.title(theme.plain_text(get_text(lang, "pick_title")))
        self.resizable(False, False)
        self.transient(root)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda _e: self.cancel())
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_header()
        self._build_slots()
        self._build_columns()
        self._build_footer(apply_text or get_text(lang, "pick_apply"), apply_kind)
        self._refresh()
        self.after(10, self._show_centered, root)

    # ── Части окна ──────────────────────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, corner_radius=0, fg_color=C["bg_primary"])
        header.grid(row=0, column=0, sticky="ew")
        badge = ctk.CTkFrame(header, width=36, height=36, corner_radius=8, fg_color=T["blue_icon_bg"])
        badge.grid(row=0, column=0, rowspan=2, padx=(24, 12), pady=18)
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="", image=icon("users", C["blue_text"], 18)).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(header, text=get_text(self.lang, "pick_title"), font=F["page_title"], text_color=C["text"],
                     anchor="w", height=22).grid(row=0, column=1, sticky="sw", pady=(18, 0))
        ctk.CTkLabel(header, text=get_text(self.lang, "pick_sub"), font=F["label"], text_color=C["text_secondary"],
                     anchor="w", height=16).grid(row=1, column=1, sticky="nw", pady=(3, 18))
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=C["border"]).grid(row=0, column=0, sticky="sew")

    def _build_slots(self):
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color=C["bg_surface"])
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_columnconfigure(2, weight=1)
        slots = ctk.CTkFrame(bar, fg_color="transparent")
        slots.grid(row=0, column=0, padx=(24, 24), pady=14)
        self.slot_cells = []
        for i in range(MAX_TITANS):
            cell = ctk.CTkFrame(slots, width=SLOT, height=SLOT, fg_color="transparent")
            cell.grid(row=0, column=i, padx=(0 if i == 0 else 10, 0))
            cell.grid_propagate(False)
            empty = ctk.CTkLabel(cell, text="", image=empty_slot_image(), width=SLOT, height=SLOT)
            empty.place(x=0, y=0)
            self.slot_cells.append({"cell": cell, "empty": empty, "avatar": None})
        info = ctk.CTkFrame(bar, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w")
        self.count_label = ctk.CTkLabel(info, text="", font=F["section"], text_color=C["text"], anchor="w", height=20)
        self.count_label.grid(row=0, column=0, sticky="w")
        self.status_label = ctk.CTkLabel(info, text="", font=F["label"], anchor="w", height=16, compound="left")
        self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        Button(bar, get_text(self.lang, "pick_clear"), kind="ghost", icon_name="rotate-ccw", icon_size=14, height=32,
               pad_x=10, command=self.clear).grid(row=0, column=3, padx=(0, 24))
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=C["border"]).grid(row=1, column=0, sticky="sew")

    def _build_columns(self):
        grid = ctk.CTkFrame(self, corner_radius=0, fg_color=C["bg_primary"])
        grid.grid(row=2, column=0, sticky="nsew", padx=24, pady=16)
        grid.grid_columnconfigure(tuple(range(len(theme.TITANS))), weight=1, uniform="col")
        for col, (element, titans) in enumerate(theme.TITANS.items()):
            allowed = any(t in self.allowed for t in titans)
            self._column_header(grid, element, len(titans), allowed).grid(
                row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0 if col == 4 else 8), pady=(0, 8))
            for row, titan in enumerate(titans, start=1):
                choice = TitanChoice(grid, titan, self.lang, self.toggle)
                choice.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0 if col == 4 else 8),
                            pady=(0, 6))
                self.rows[titan] = choice
        # Эларит: Метида встаёт только в смешанную комнату
        base = len(max(theme.TITANS.values(), key=len)) + 1
        allowed = any(t in self.allowed for t in theme.ELARITE_ONLY)
        header = self._column_header(grid, "elarite", len(theme.ELARITE_ONLY), allowed,
                                     note=get_text(self.lang, "pick_elarite_note"))
        header.grid(row=base, column=0, columnspan=3, sticky="ew", pady=(10, 8))
        for i, titan in enumerate(theme.ELARITE_ONLY):
            choice = TitanChoice(grid, titan, self.lang, self.toggle)
            choice.grid(row=base + 1, column=i, sticky="ew", padx=(0 if i == 0 else 8, 8), pady=(0, 6))
            self.rows[titan] = choice

    def _column_header(self, master, element, count, allowed, note=None):
        style = theme.element_style(element)
        color = style["text"] if allowed else C["text_muted"]
        frame = ctk.CTkFrame(master, fg_color="transparent", height=24)
        ctk.CTkLabel(frame, text="", image=icon(style["icon"], style["color"] if allowed else C["text_muted"], 16),
                     width=16).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(frame, text=theme.plain_text(get_text(self.lang, f"elem_{element}")), font=F["card_title"],
                     text_color=color, height=20).pack(side="left")
        if note:
            ctk.CTkLabel(frame, text=f"· {note}", font=F["label"], text_color=C["text_muted"], height=20).pack(
                side="left", padx=(8, 0))
        else:
            ctk.CTkLabel(frame, text=str(count), font=F["label"], text_color=C["text_muted"], height=20).pack(
                side="right")
        return frame

    def _build_footer(self, apply_text, apply_kind):
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=C["border"]).grid(row=3, column=0, sticky="new")
        footer = ctk.CTkFrame(self, corner_radius=0, fg_color=C["bg_surface"])
        footer.grid(row=3, column=0, sticky="ew", pady=(1, 0))
        footer.grid_columnconfigure(0, weight=1)
        if self.room in ("earth", "water", "fire"):
            hint = get_text(self.lang, "pick_hint_room").format(
                room=theme.plain_text(get_text(self.lang, f"elem_{self.room}")))
        else:
            hint = get_text(self.lang, "pick_hint")
        ctk.CTkLabel(footer, text=hint, font=F["label"], text_color=C["text_muted"], anchor="w").grid(
            row=0, column=0, sticky="w", padx=(24, 10), pady=14)
        Button(footer, get_text(self.lang, "btn_cancel"), kind="secondary", height=S["button_height_footer"],
               command=self.cancel).grid(row=0, column=1, padx=(0, 10))
        self.apply_button = Button(footer, apply_text, kind=apply_kind, icon_name="check", icon_size=14,
                                   height=S["button_height_footer"], pad_x=18, command=self.apply)
        self.apply_button.grid(row=0, column=2, padx=(0, 24))

    # ── Выбор ───────────────────────────────────────────────────────────────
    def toggle(self, titan):
        if titan in self.chosen:
            self.chosen.remove(titan)
        elif titan in self.allowed and len(self.chosen) < MAX_TITANS:
            self.chosen.append(titan)
        else:
            return
        self._refresh()

    def clear(self):
        self.chosen = []
        self._refresh()

    def _refresh(self):
        full = len(self.chosen) >= MAX_TITANS
        for titan, row in self.rows.items():
            chosen = titan in self.chosen
            row.set_state(chosen, chosen or (titan in self.allowed and not full))
        for i, slot in enumerate(self.slot_cells):
            titan = self.chosen[i] if i < len(self.chosen) else None
            avatar = slot["avatar"]
            if titan is None:
                if avatar is not None:
                    avatar.place_forget()
            else:
                if avatar is None:
                    avatar = TitanAvatar(slot["cell"], titan, lang=self.lang, size=SLOT, command=self.toggle)
                    slot["avatar"] = avatar
                elif avatar.titan != titan:
                    avatar.set_titan(titan)
                avatar.place(x=0, y=0)
        count = len(self.chosen)
        self.count_label.configure(text=get_text(self.lang, "pick_count").format(n=count))
        ok = MIN_TITANS <= count <= MAX_TITANS
        color = C["success"] if ok else C["warning"]
        text = get_text(self.lang, "pick_ok") if ok else \
            get_text(self.lang, "pick_need").format(k=MIN_TITANS - count)
        self.status_label.configure(text=" " + text, text_color=color, image=dot(color, 7))
        self.apply_button.set_enabled(ok)

    # ── Показ и закрытие ────────────────────────────────────────────────────
    def _show_centered(self, root):
        if self._done:
            return
        try:
            self.geometry(f"{WINDOW[0]}x{WINDOW[1]}")
            self.update_idletasks()
            w, h = WINDOW
            x = root.winfo_rootx() + (root.winfo_width() - w) // 2
            y = root.winfo_rooty() + (root.winfo_height() - h) // 3
            x = max(0, min(x, self.winfo_screenwidth() - w))
            y = max(0, min(y, self.winfo_screenheight() - h - 40))
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.deiconify()
            self.lift()
            self.focus_set()
        except Exception:
            pass

    def apply(self):
        if self._done or not (MIN_TITANS <= len(self.chosen) <= MAX_TITANS):
            return
        team = list(self.chosen)
        self._finish()
        self.on_apply(team)

    def cancel(self):
        if self._done:
            return
        self._finish()
        if self.on_cancel:
            self.on_cancel()

    def _finish(self):
        self._done = True
        try:
            self.destroy()
        except Exception:
            pass

    @property
    def closed(self):
        return self._done

    def close_silently(self):
        """Бот решил сам ([SOS_CLOSE]): окно закрывается без ответа."""
        if not self._done:
            self._finish()
