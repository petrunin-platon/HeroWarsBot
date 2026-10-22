"""Витрина общих виджетов (задача 15, шаг 1): все детали нового интерфейса в одном окне, как экран 8 макета.

Запуск из папки проекта: python -m ui.demo        (язык титанов и кнопки «Отмена»: python -m ui.demo EN)
Это инструмент для проверки, в окно программы он не входит. Надписи здесь — образцы из макета (design/mockups),
как данные в renderVals; в настоящих экранах все надписи берутся из i18n.py.
"""
import sys

import customtkinter as ctk

from i18n import get_text
from ui import theme
from ui.icons import icon
from ui.widgets import (Button, Card, Chip, ConfirmDialog, DialogBody, Field, IconButton, TitanAvatar, Toast,
                        ToastBody, titan_name)

C = theme.COLORS
F = theme.FONTS
S = theme.SIZES

# Образцы надписей из design/mockups/08_states.dc.html и других макетов
SAMPLE = {
    "title": "Витрина виджетов",
    "cap_dialogs": "Подтверждения · «Очистить все правила», «Восстановить / Сброс», «Очистить журнал» "
                   "и уход с несохранёнными изменениями",
    "del_title": "Удалить все правила?",
    "del_text": "Будут удалены все 8 правил. Это действие нельзя отменить. Если правило мешает лишь временно, "
                "его можно просто выключить.",
    "del_ok": "Удалить все",
    "save_title": "Сохранить изменения?",
    "save_text": "Ты поменял настройки на вкладке «Авто-тактика и ХП», но не сохранил их. Если уйти сейчас, "
                 "изменения пропадут.",
    "save_ok": "Сохранить",
    "save_no": "Не сохранять",
    "open_del": "Открыть «Удалить все правила?»",
    "open_save": "Открыть «Сохранить изменения?»",
    "cap_fields": "Состояния полей ввода · ошибка пишется прямо под полем",
    "f_states": ("ОБЫЧНОЕ", "В ФОКУСЕ", "ОШИБКА", "НЕДОСТУПНО"),
    "f_label": "Порог паники ХП, %",
    "f_hint": "От 0 до 100",
    "f_error": "Введи число от 0 до 100",
    "f_disabled": "Нельзя менять во время фарма",
    "cap_toasts": "Короткие уведомления · появляются в правом нижнем углу на 4 секунды",
    "t_saved": "Настройки сохранены",
    "t_deleted": "Правило «Араджи ранен» удалено",
    "t_undo": "Вернуть",
    "open_toast": "Показать уведомление",
    "open_toast2": "Показать уведомление с «Вернуть»",
    "cap_buttons": "Кнопки · зелёная только старт и сохранение, синяя — выбранное",
    "b_secondary": "Сохранить лог",
    "b_blue": "Запустить анализ логов",
    "b_save": "Сохранить настройки",
    "b_cta": "Начать фарм",
    "b_danger": "Восстановить / Сброс",
    "b_ghost_danger": "Очистить",
    "b_link": "Изменить в мастере правил →",
    "b_disabled": "Внедрить золотые правила",
    "cap_icons": "Кнопки-иконки с подсказками (наведи мышь) · шапка и сайдбар",
    "tip_moon": "Выключить экран телефона", "tip_refresh": "Перезапустить scrcpy",
    "tip_size": "Сброс размера окна игры",
    "tip_home": "Главная", "tip_rules": "Мастер правил", "tip_analytics": "Аналитика",
    "cap_chips": "Фильтры-«таблетки»",
    "chips": ("Все", "Бои", "Правила", "Система", "Ошибки"),
    "cap_titans": "Титаны · квадрат 36×36 цветом стихии; нет картинки в assets/icons — две буквы имени",
}


class Demo(ctk.CTk):
    def __init__(self, lang="RU"):
        super().__init__(fg_color=C["bg_primary"])
        self.lang = lang
        self.title(SAMPLE["title"])
        self.geometry("1100x720")
        self.minsize(*S["window_min"])
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg_primary"])
        self.scroll.pack(fill="both", expand=True)
        body = self.scroll
        body.grid_columnconfigure(0, weight=1)
        self.row = 0

        # ── Подтверждения
        self._caption(body, SAMPLE["cap_dialogs"])
        dialogs = ctk.CTkFrame(body, fg_color="transparent")
        dialogs.grid(row=self._next(), column=0, sticky="ew", padx=40)
        dialogs.grid_columnconfigure((0, 1), weight=1, uniform="d")
        cancel = get_text(lang, "btn_cancel")
        DialogBody(dialogs, SAMPLE["del_title"], SAMPLE["del_text"], SAMPLE["del_ok"], cancel, kind="danger",
                   border_width=1, border_color=C["border"]).grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        DialogBody(dialogs, SAMPLE["save_title"], SAMPLE["save_text"], SAMPLE["save_ok"], cancel, kind="warning",
                   discard_text=SAMPLE["save_no"], border_width=1, border_color=C["border"]).grid(
            row=0, column=1, sticky="nsew", padx=(20, 0))
        opener = ctk.CTkFrame(body, fg_color="transparent")
        opener.grid(row=self._next(), column=0, sticky="w", padx=40, pady=(10, 0))
        Button(opener, SAMPLE["open_del"], command=self.open_delete).pack(side="left")
        Button(opener, SAMPLE["open_save"], command=self.open_save).pack(side="left", padx=10)

        # ── Поля ввода
        self._caption(body, SAMPLE["cap_fields"])
        card = Card(body)
        card.grid(row=self._next(), column=0, sticky="ew", padx=40)
        card.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="f")
        self.fields = []
        for col, state in enumerate(SAMPLE["f_states"]):
            cell = ctk.CTkFrame(card, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=(20 if col == 0 else 10, 20 if col == 3 else 10),
                      pady=20)
            cell.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(cell, text=state, font=F["small_bold"], text_color=C["text_muted"], height=16).grid(
                row=0, column=0, sticky="w", pady=(0, 6))
            field = Field(cell, label=SAMPLE["f_label"], hint=SAMPLE["f_hint"], value=(30, 35, 130, 30)[col])
            field.grid(row=1, column=0, sticky="ew")
            self.fields.append(field)
        self.fields[1].show_focus()
        self.fields[2].set_error(SAMPLE["f_error"])
        self.fields[3].set_enabled(False, hint=SAMPLE["f_disabled"])

        # ── Уведомления
        self._caption(body, SAMPLE["cap_toasts"])
        toasts = ctk.CTkFrame(body, fg_color="transparent")
        toasts.grid(row=self._next(), column=0, sticky="w", padx=40)
        ToastBody(toasts, SAMPLE["t_saved"], kind="success", bg_color=C["bg_primary"]).pack(side="left")
        ToastBody(toasts, SAMPLE["t_deleted"], kind="deleted", action_text=SAMPLE["t_undo"],
                  bg_color=C["bg_primary"]).pack(side="left", padx=20)
        opener = ctk.CTkFrame(body, fg_color="transparent")
        opener.grid(row=self._next(), column=0, sticky="w", padx=40, pady=(10, 0))
        Button(opener, SAMPLE["open_toast"], command=lambda: Toast(self, SAMPLE["t_saved"])).pack(side="left")
        Button(opener, SAMPLE["open_toast2"], command=lambda: Toast(
            self, SAMPLE["t_deleted"], kind="deleted", action_text=SAMPLE["t_undo"],
            on_action=lambda: Toast(self, SAMPLE["t_saved"]))).pack(side="left", padx=10)

        # ── Кнопки
        self._caption(body, SAMPLE["cap_buttons"])
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=self._next(), column=0, sticky="w", padx=40)
        Button(row, SAMPLE["b_secondary"], icon_name="save").pack(side="left")
        Button(row, SAMPLE["b_blue"], kind="blue", icon_name="search").pack(side="left", padx=10)
        Button(row, SAMPLE["b_save"], kind="save", icon_name="save", height=S["button_height_footer"]).pack(
            side="left")
        Button(row, SAMPLE["b_danger"], kind="danger", icon_name="rotate-ccw",
               height=S["button_height_footer"]).pack(side="left", padx=10)
        Button(row, SAMPLE["b_ghost_danger"], kind="ghost_danger", icon_name="trash-2").pack(side="left")
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=self._next(), column=0, sticky="w", padx=40, pady=(10, 0))
        Button(row, SAMPLE["b_cta"], kind="cta", icon_name="play-filled", icon_size=20, pad_x=60).pack(side="left")
        Button(row, SAMPLE["b_link"], kind="link", height=24, pad_x=4).pack(side="left", padx=10)
        disabled = Button(row, SAMPLE["b_disabled"], kind="save", icon_name="check")
        disabled.pack(side="left")
        disabled.set_enabled(False)

        # ── Кнопки-иконки
        self._caption(body, SAMPLE["cap_icons"])
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=self._next(), column=0, sticky="w", padx=40)
        for name, tip in (("moon", "tip_moon"), ("refresh-cw", "tip_refresh"), ("maximize-2", "tip_size")):
            IconButton(row, name, tooltip=SAMPLE[tip]).pack(side="left", padx=(0, 10))
        rail = ctk.CTkFrame(row, fg_color=C["bg_primary"], border_width=1, border_color=C["border"])
        rail.pack(side="left", padx=(30, 0))
        self.nav = []
        for name, tip in (("house", "tip_home"), ("sliders-vertical", "tip_rules"), ("activity", "tip_analytics")):
            button = IconButton(rail, name, kind="nav", tooltip=SAMPLE[tip], tooltip_side="right")
            button.configure(command=lambda b=button: self.select_nav(b))
            button.pack(side="left", padx=10, pady=10)
            self.nav.append(button)
        self.select_nav(self.nav[0])

        # ── Фильтры
        self._caption(body, SAMPLE["cap_chips"])
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=self._next(), column=0, sticky="w", padx=40)
        self.chips = []
        for i, text in enumerate(SAMPLE["chips"]):
            chip = Chip(row, text, selected=(i == 0), count=1 if i == 4 else None)
            chip.command = lambda c=chip: self.select_chip(c)
            chip.pack(side="left", padx=(0, 6))
            self.chips.append(chip)
        for element in ("earth", "water", "fire", "mix"):
            label = theme.plain_text(get_text(lang, f"elem_{element}"))
            chip = Chip(row, label, dot_color=theme.ELEMENTS[element]["color"])
            chip.command = lambda c=chip: self.select_chip(c)
            chip.pack(side="left", padx=(0, 6))
            self.chips.append(chip)

        # ── Титаны
        self._caption(body, SAMPLE["cap_titans"])
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.grid(row=self._next(), column=0, sticky="w", padx=40, pady=(0, 40))
        for r, (element, titans) in enumerate(theme.TITANS.items()):
            style = theme.ELEMENTS[element]
            ctk.CTkLabel(grid, text=" " + theme.plain_text(get_text(lang, f"elem_{element}")), compound="left",
                         image=icon(style["icon"], style["color"], 16), font=F["card_title"],
                         text_color=style["text"], width=110, anchor="w").grid(row=r, column=0, sticky="w", pady=4)
            for c, titan in enumerate(titans):
                TitanAvatar(grid, titan, lang=lang, command=self.titan_clicked).grid(row=r, column=1 + c, padx=4,
                                                                                    pady=4)
                TitanAvatar(grid, titan, lang=lang, size=S["avatar_small"]).grid(row=r, column=8 + c, padx=3)
        TitanAvatar(grid, "metis", lang=lang).grid(row=0, column=15, padx=(30, 0))

    def _next(self):
        self.row += 1
        return self.row

    def _caption(self, body, text):
        ctk.CTkLabel(body, text=text, font=(theme.FONT_FAMILY, 13, "bold"), text_color=C["text_secondary"],
                     anchor="w").grid(row=self._next(), column=0, sticky="w", padx=40, pady=(32, 10))

    def select_nav(self, chosen):
        for button in self.nav:
            button.set_active(button is chosen)

    def select_chip(self, chosen):
        for chip in self.chips:
            chip.set_selected(chip is chosen)

    def titan_clicked(self, titan):
        Toast(self, titan_name(self.lang, titan), kind="info")

    def open_delete(self):
        ConfirmDialog(self, SAMPLE["del_title"], SAMPLE["del_text"], SAMPLE["del_ok"], kind="danger", lang=self.lang,
                      on_confirm=lambda: Toast(self, SAMPLE["t_deleted"], kind="deleted"))

    def open_save(self):
        ConfirmDialog(self, SAMPLE["save_title"], SAMPLE["save_text"], SAMPLE["save_ok"], kind="warning",
                      lang=self.lang, discard_text=SAMPLE["save_no"],
                      on_confirm=lambda: Toast(self, SAMPLE["t_saved"]))


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    Demo(sys.argv[1].upper() if len(sys.argv) > 1 else "RU").mainloop()
