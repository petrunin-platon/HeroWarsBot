"""Страница «Мастер правил» нового окна (задача 15, шаг 5а; макеты 03a–03c, экран 8).

Сверху три вкладки (сегменты): «База и комнаты» (ui/rules_base.py), «Авто-тактика и ХП» (ui/rules_tactics.py, шаг 5б),
«Правила и перехваты» (ui/rules_intercepts.py, шаг 5в; окно «Новое правило» — ui/rule_editor.py). Ниже — вкладка,
внизу общий футер: «Все изменения сохранены» / «Есть несохранённые изменения», «Восстановить / Сброс» (с подтверждением),
«Сохранить настройки». Пока бот работает, в футере подсказка «Бот возьмёт новые настройки при следующем запуске»
(менять можно, как в старом окне: бот читает настройки при запуске).

Все значения — в форме страницы (form — profile.yml, teams — основные паки, rules — правила стихий), пишет их только
«Сохранить настройки» (ваш ответ, сверка 4.1), и только то, что поменялось (ui/rules_store.py, ui/rules_list.py;
ваше замечание: беречь диск). Правила, которые бот запомнил, пока окно было открыто, при сохранении не теряются.
Уйти со страницы (или закрыть окно) с несохранёнными изменениями — окно «Сохранить изменения?» (ask_leave).
Для старого кода страница по-прежнему frames["rules"] с open_tg_dialog() (точка Telegram в полоске): с шага 5б —
новое окно Telegram (ui/telegram_window.py) с кнопкой «Проверить Telegram».
"""
import copy

import tkinter as tk

import customtkinter as ctk

from i18n import get_text
from ui import rules_list, rules_store, theme
from ui.icons import icon
from ui.rules_base import BaseTab
from ui.rules_intercepts import InterceptsTab
from ui.rules_tactics import TacticsTab
from ui.widgets import Button, ConfirmDialog, Toast

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

TABS = ("base", "tactics", "rules")
TAB_ATTRS = {"base": "base", "tactics": "tactics", "rules": "intercepts"}   # где страница держит построенную вкладку
PREBUILD_MS = 500   # остальные вкладки строятся заранее, через столько мс после показа страницы
TAB_KEYS = {"base": "rb_tab_base", "tactics": "rb_tab_tactics", "rules": "rb_tab_rules"}


class RulesPage(ctk.CTkFrame):
    full_bleed = True   # без отступов окна: вкладки и футер — во всю ширину (макет 03a)

    def __init__(self, master, controller):
        super().__init__(master, corner_radius=0, fg_color=C["bg_primary"])
        self.controller = controller
        self.lang = getattr(controller, "current_lang", "RU")
        self.tab = "base"
        self.expanded = {}         # раскрытые «Запасные паки» по стихиям
        self.field_errors = {}     # поля с ошибкой: что в них введено
        self.bot_running = False
        self._dialog = None
        self._tg_window = None
        self._editor = None
        self.load()
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build()
        self.bind("<Map>", self._mapped, add="+")

    def text(self, key):
        return get_text(self.lang, key)

    def log(self, line):
        dash = self.controller.frames.get("dash") if hasattr(self.controller, "frames") else None
        if dash is not None:
            dash.append_log(line)

    # ── Чтение ──────────────────────────────────────────────────────────────
    def load(self):
        """Прочитать profile.yml и основные паки. Ошибки — в журнал, как в старой вкладке."""
        state, profile, where = rules_store.read_profile()
        if state == rules_store.BROKEN:
            loc = f" (строка:символ {where})" if where else ""
            self.log(f"[ОШИБКА] Файл profile.yml поврежден{loc}! Настройки показаны стандартные. "
                     f"Нажмите «Восстановить / Сброс».\n")
        elif state == rules_store.OK:
            rules_store.ensure_backup()
        self.profile_state = state
        self.form = rules_store.form_from_profile(profile)
        self.saved = copy.deepcopy(self.form)
        self.teams, broken = rules_store.read_default_teams()
        for room in broken:
            self.log(f"[ОШИБКА] Не удалось загрузить основной пак: bot_data/rules/{room}.yml поврежден.\n")
        self.saved_teams = copy.deepcopy(self.teams)
        self.rules, broken = rules_list.read_all()
        for room in broken:
            self.log(f"[ОШИБКА] Не удалось загрузить правила: bot_data/rules/{room}.yml поврежден. "
                     "Правила этой стихии не показаны и не сохраняются.\n")
        self.broken_rules = set(broken)
        self.saved_rules = copy.deepcopy(self.rules)
        self.field_errors = {}

    def reload_rules(self):
        """Перечитать правила с диска, если в форме их не меняли (бот мог запомнить новые, пока окно открыто).
        True — правила на диске поменялись."""
        if self.rules != self.saved_rules:
            return False
        fresh, broken = rules_list.read_all()
        self.broken_rules = set(broken)
        if fresh == self.saved_rules:
            return False
        self.rules = fresh
        self.saved_rules = copy.deepcopy(fresh)
        return True

    def dirty_tab(self):
        """На какой вкладке несохранённое (для «Сохранить изменения?»): открытая, если на ней, иначе первая."""
        keys = set(rules_store.changed_keys(self.saved, self.form)) | set(self.field_errors)
        tabs = []
        if keys & set(rules_store.BASE_KEYS) or self.teams != self.saved_teams:
            tabs.append("base")
        if keys & set(rules_store.TACTICS_KEYS):
            tabs.append("tactics")
        if self.rules != self.saved_rules:
            tabs.append("rules")
        return self.tab if self.tab in tabs else (tabs[0] if tabs else "base")

    def dirty(self):
        """Есть несохранённые изменения (в том числе поле с ошибкой)."""
        return bool(rules_store.changed_keys(self.saved, self.form) or self.teams != self.saved_teams
                    or self.rules != self.saved_rules or self.field_errors)

    # ── Части страницы ──────────────────────────────────────────────────────
    def _build(self):
        holder = ctk.CTkFrame(self, fg_color="transparent", width=10, height=10)
        holder.grid(row=0, column=0, sticky="ew", padx=24, pady=(14, 0))
        holder.grid_columnconfigure(0, weight=1)
        self.tabs = ctk.CTkSegmentedButton(
            holder, values=[self.text(TAB_KEYS[t]) for t in TABS], command=self._tab_chosen, height=40,
            corner_radius=8, border_width=3, fg_color=C["bg_surface"], selected_color=C["blue_button"],
            selected_hover_color=C["blue_button"], unselected_color=C["bg_surface"],
            unselected_hover_color=C["bg_elevated"], text_color=C["white"], font=F["button"], dynamic_resizing=False)
        self.tabs.grid(row=0, column=0, sticky="ew")
        self.tabs.set(self.text(TAB_KEYS[self.tab]))
        self._paint_tabs()

        self.body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0, width=10, height=10)
        self.body.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.base = None
        self.tactics = None
        self.intercepts = None
        # Вкладки лежат в одной ячейке, щелчок поднимает нужную наверх (lift): без новой раскладки и перерисовки
        # всей вкладки, поэтому переключение мгновенное и без артефактов (проверка шага 5б).
        self._prebuild_id = None
        self._show_tab()
        self._schedule_prebuild()

        tk.Frame(self, height=1, bg=C["border"]).grid(row=2, column=0, sticky="ew")
        footer = ctk.CTkFrame(self, height=S["footer_height"], corner_radius=0, fg_color=C["bg_surface"])
        footer.grid(row=3, column=0, sticky="ew")
        footer.grid_propagate(False)
        footer.grid_rowconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=1)
        self.state_label = ctk.CTkLabel(footer, text="", font=F["text"], text_color=C["text_secondary"], height=20,
                                        compound="left")
        self.state_label.grid(row=0, column=0, sticky="w", padx=(24, 0))
        self.bot_label = ctk.CTkLabel(footer, text="", font=F["label"], text_color=C["text_muted"], height=20,
                                      anchor="w")
        self.bot_label.grid(row=0, column=1, sticky="w", padx=(16, 10))
        self.restore_button = Button(footer, theme.plain_text(self.text("rules_btn_restore")), kind="danger",
                                     icon_name="rotate-ccw", icon_size=15, height=S["button_height_footer"],
                                     command=self.ask_restore)
        self.restore_button.grid(row=0, column=2, padx=(0, 10))
        self.save_button = Button(footer, self.text("rb_save"), kind="save", icon_name="save", icon_size=15,
                                  height=S["button_height_footer"], pad_x=18, font=F["body_bold"],
                                  command=self.save)
        self.save_button.grid(row=0, column=3, padx=(0, 24))
        self._state_shown = None
        self.changed()
        self._show_bot_hint()

    def _tab_chosen(self, text):
        tab = next((t for t in TABS if self.text(TAB_KEYS[t]) == text), "base")
        if tab != self.tab:
            self.tab = tab
            self._paint_tabs()
            self._show_tab()

    def _paint_tabs(self):
        """Выбранная вкладка — белый текст, остальные — серый (макет). У CTkSegmentedButton цвет текста общий,
        поэтому красим кнопки по одной — только при выборе вкладки, не при наведении."""
        for tab in TABS:
            button = self.tabs._buttons_dict.get(self.text(TAB_KEYS[tab]))
            if button is not None:
                color = C["white"] if tab == self.tab else C["text_secondary"]
                if button.cget("text_color") != color:
                    button.configure(text_color=color)

    def _tab_widget(self, tab):
        """Вкладка (строится один раз и кладётся в ячейку)."""
        attr = TAB_ATTRS[tab]
        if getattr(self, attr) is None:
            kind = {"base": BaseTab, "tactics": TacticsTab, "rules": InterceptsTab}[tab]
            widget = kind(self.body, self)
            widget.grid(row=0, column=0, sticky="nsew")
            setattr(self, attr, widget)
        return getattr(self, attr)

    def _show_tab(self):
        """Поднять выбранную вкладку наверх. «Авто-тактику» при показе обновляем: «Бот решает сам» и общий порог
        живут на «Базе и комнатах»; «Правила» — с диска, если бот за это время запомнил новые."""
        built = getattr(self, TAB_ATTRS[self.tab]) is not None
        widget = self._tab_widget(self.tab)
        if self.tab == "tactics" and built:
            self.tactics.refresh()
        if self.tab == "rules" and built:
            self._refresh_rules()
        widget.lift()

    def _mapped(self, event):
        """Страницу снова открыли (полоска слева): правила могли поменяться на диске."""
        if event.widget is self and self.tab == "rules" and self.intercepts is not None:
            self._refresh_rules()

    def _refresh_rules(self):
        if self.reload_rules() and self.intercepts is not None:
            self.intercepts.rebuild()

    def shown_tab_widget(self):
        """Вкладка, которая сейчас видна (для проверки): что под серединой области вкладок."""
        tabs = [w for w in (self.base, self.tactics, self.intercepts) if w is not None]
        frames = {str(getattr(w, "_parent_frame", w)): w for w in tabs}   # у CTkScrollableFrame наверху — его рамка
        x = self.body.winfo_rootx() + self.body.winfo_width() // 2
        y = self.body.winfo_rooty() + self.body.winfo_height() // 2
        widget = self.body.winfo_containing(x, y)
        while widget is not None and str(widget) not in frames:
            widget = widget.master
        return frames.get(str(widget)) if widget is not None else None

    def _schedule_prebuild(self):
        self._cancel_prebuild()
        if any(getattr(self, attr) is None for attr in TAB_ATTRS.values()):
            self._prebuild_id = self.after(PREBUILD_MS, self._prebuild)

    def _cancel_prebuild(self):
        if self._prebuild_id is not None:
            try:
                self.after_cancel(self._prebuild_id)
            except tk.TclError:
                pass
            self._prebuild_id = None

    def _prebuild(self):
        """Построить ещё не построенные вкладки заранее, под открытой: первый щелчок по ним тоже мгновенный."""
        self._prebuild_id = None
        missing = [tab for tab in TABS if getattr(self, TAB_ATTRS[tab]) is None]
        if missing:
            self._tab_widget(missing[0])
            self._tab_widget(self.tab).lift()
            self._schedule_prebuild()   # следующую — отдельно, чтобы окно между ними отвечало

    def destroy(self):
        self._cancel_prebuild()
        super().destroy()

    def rebuild_base(self):
        """Построить вкладки заново из формы («Восстановить», «Не сохранять»)."""
        for name in TAB_ATTRS.values():
            tab = getattr(self, name)
            if tab is not None:
                tab.destroy()
                setattr(self, name, None)
        self._show_tab()
        self._schedule_prebuild()

    def rebuild_room(self, room):
        if self.base is not None:
            self.base.rooms[room].build()

    def _room(self, room):
        return self.base.rooms[room] if self.base is not None else None

    # ── Состояние футера ────────────────────────────────────────────────────
    def changed(self):
        """Любая правка формы: обновить надпись футера (только если она правда поменялась)."""
        dirty = self.dirty()
        if dirty == self._state_shown:
            return
        self._state_shown = dirty
        if dirty:
            self.state_label.configure(text=" " + self.text("rb_unsaved_state"), text_color=C["warning"],
                                       image=icon("triangle-alert", C["warning"], 15))
        else:
            self.state_label.configure(text=" " + self.text("rb_saved_state"), text_color=C["text_secondary"],
                                       image=icon("check", C["success"], 15))

    def update_bot_state(self, running):
        """Бот запущен или нет (ui/app.py зовёт часто — меняем надпись, только если правда поменялось)."""
        if running != self.bot_running:
            self.bot_running = running
            self._show_bot_hint()

    def _show_bot_hint(self):
        self.bot_label.configure(text=self.text("rb_bot_hint") if self.bot_running else "")

    # ── Правки из вкладки ───────────────────────────────────────────────────
    def set_team(self, room, team):
        self.teams[room] = list(team)
        if self._room(room):
            self._room(room).show_team()    # только квадраты пака, не вся строка
        self.changed()

    def add_backup(self, room, team):
        if not rules_store.add_backup(self.form, room, team):
            Toast(self, self.text("rb_pack_exists"), kind="info")
            return
        self.expanded[room] = True
        if self._room(room):
            self._room(room).backups.refresh(expand=True)
        self.changed()

    def remove_backup(self, room, index):
        rules_store.remove_backup(self.form, room, index)
        if self._room(room):
            self._room(room).backups.refresh()
        self.changed()

    def open_tg_dialog(self):
        """«Настроить Telegram» (и точка Telegram в полоске) — окно ui/telegram_window.py (шаг 5б). Его «Применить»
        меняет форму, в profile.yml пишет «Сохранить настройки»."""
        from ui.telegram_window import TelegramWindow
        if self._tg_window is not None and not self._tg_window.done:
            self._tg_window.lift()
            return

        def on_save(data):
            self.form["telegram"] = {"active": bool(data.get("active")), "token": str(data.get("token", "")),
                                     "chat_id": str(data.get("chat_id", ""))}
            if self.base is not None:
                self.base.show_telegram()
            self.changed()
            self.log("[GUI] Настройки Telegram обновлены — нажмите «Сохранить настройки» в «Мастере правил».\n")
        self._tg_window = TelegramWindow(self, self.lang, dict(self.form["telegram"]), on_save)

    def add_condition(self, room):
        """«+ Условие» на «Базе и комнатах» — окно «Новое правило» с этой стихией (шаг 5в). Правило — в форму
        (во вкладку «Правила и перехваты»), в файл его пишет «Сохранить настройки»."""
        self.open_rule_editor(room, notify=True)

    def open_rule_editor(self, room, index=None, notify=False):
        """Окно «Новое правило» (index — изменить правило стихии room с этим номером). notify — после сохранения
        уведомление, куда попало правило (открывали не из вкладки правил)."""
        from ui.rule_editor import RuleEditor
        if self._editor is not None and not self._editor.done:
            self._editor.lift()
            return
        if room in self.broken_rules:
            Toast(self, self.text("ri_broken").format(room=room), kind="error")
            return
        original = self.rules[room][index] if index is not None else None

        def on_save(new_room, rule):
            # Пока окно было открыто, список мог обновиться (правила бота с диска) — правило ищем заново
            old_index = rules_list.locate(self.rules, room, original) if original is not None else None
            old_room = room if old_index is not None else None
            place = rules_list.put(self.rules, new_room, rule, old_room=old_room, index=old_index)
            if self.intercepts is not None:
                self.intercepts.rule_put(new_room, place, old_room, old_index)
            self.changed()
            if notify:
                title = rules_list.title_and_sub(rule, self.lang)[0]
                Toast(self, self.text("ri_added").format(name=title), kind="success")
        self._editor = RuleEditor(self, self.lang, room, on_save, rule=original)

    # ── Сохранение ──────────────────────────────────────────────────────────
    def save(self):
        """«Сохранить настройки». True — сохранено (или нечего было сохранять)."""
        if self.field_errors:
            Toast(self, self.text("rb_fix_fields"), kind="error")
            return False
        state, result = rules_store.save_profile(self.saved, self.form)
        if state == rules_store.BROKEN:
            loc = f" (строка:символ {result})" if result else ""
            self.log(f"[ОШИБКА] Сохранение прервано: profile.yml сломан{loc}. Нажмите «Восстановить / Сброс»!\n")
            Toast(self, self.text("rb_broken_toast"), kind="error")
            return False
        failed = []
        for room in rules_store.ROOMS:
            if self.teams[room] != self.saved_teams[room]:
                if rules_store.save_default_team(room, self.teams[room]):
                    self.saved_teams[room] = list(self.teams[room])
                else:
                    failed.append(room)
                    self.log(f"[ОШИБКА] Сохранение прервано: файл bot_data/rules/{room}.yml поврежден!\n")
        failed += self._save_rules()
        self.saved = copy.deepcopy(self.form)
        self.profile_state = rules_store.OK
        self.changed()
        if failed:
            Toast(self, self.text("rb_broken_toast"), kind="error")
            return False
        if result:
            self.log("[GUI] Профиль настроек сохранен!\n")
        Toast(self, self.text("rb_saved_toast"), kind="success")
        return True

    def _save_rules(self):
        """Правила стихий, где их поменяли (ui/rules_list.py: save_rules). Возвращает стихии с битым файлом."""
        written, broken, added = rules_list.save_rules(self.saved_rules, self.rules)
        for room in broken:
            self.log(f"[ОШИБКА] Правила не сохранены: файл bot_data/rules/{room}.yml поврежден!\n")
        if written:
            names = ", ".join(rules_list.ROOM_NAMES_RU[room] for room in written)
            self.log(f"[GUI] Правила сохранены: {names}.\n")
        if added:
            count = sum(len(rules) for rules in added.values())
            self.log(f"[GUI] Пока окно было открыто, бот запомнил правил: {count}. Они добавлены наверх списка.\n")
            if self.intercepts is not None:
                self.intercepts.rebuild()
        return broken

    def discard(self):
        """«Не сохранять»: форма — как в файлах."""
        self.form = copy.deepcopy(self.saved)
        self.teams = copy.deepcopy(self.saved_teams)
        self.rules = copy.deepcopy(self.saved_rules)
        self.field_errors = {}
        self.rebuild_base()
        self.changed()

    def ask_restore(self):
        if self._dialog_open():
            return
        self._dialog = ConfirmDialog(self, self.text("rb_restore_title"), self.text("rb_restore_text"),
                                     self.text("rb_restore_ok"), on_confirm=self.restore, kind="danger",
                                     lang=self.lang, confirm_kind="danger_solid", confirm_icon="rotate-ccw")

    def restore(self):
        """«Восстановить / Сброс» — как старая вкладка: profile.yml из копии, а без копии — удалить его."""
        try:
            done = rules_store.restore_profile()
        except OSError as e:
            self.log(f"[ОШИБКА] Не удалось восстановить профиль: {e}\n")
            return
        if done == "restored":
            self.log("[GUI] Профиль успешно восстановлен из резервной копии!\n")
        elif done == "reset":
            self.log("[GUI] Битый профиль удален. Выполнен сброс до заводских настроек!\n")
        self.load()
        self.rebuild_base()
        self._state_shown = None
        self.changed()

    # ── Уход со страницы ────────────────────────────────────────────────────
    def _dialog_open(self):
        if self._dialog is not None and not self._dialog.done:
            self._dialog.lift()
            return True
        return False

    def ask_leave(self, proceed):
        """Уйти со страницы или закрыть окно: есть несохранённые изменения — «Сохранить изменения?»
        (Сохранить / Не сохранять / Отмена); proceed() — когда можно уходить."""
        if not self.dirty():
            proceed()
            return
        if self._dialog_open():
            return

        def save_and_go():
            if self.save():
                proceed()

        def discard_and_go():
            self.discard()
            proceed()

        tab = self.text(TAB_KEYS[self.dirty_tab()])
        self._dialog = ConfirmDialog(self, self.text("rb_leave_title"), self.text("rb_leave_text").format(tab=tab),
                                     self.text("rb_leave_save"), on_confirm=save_and_go, kind="warning",
                                     lang=self.lang, discard_text=self.text("rb_leave_discard"),
                                     on_discard=discard_and_go)

    # ── Язык ────────────────────────────────────────────────────────────────
    def update_language(self, lang):
        if lang == self.lang:
            return
        self.lang = lang
        self._cancel_prebuild()
        for child in self.winfo_children():
            child.destroy()
        self.base = None
        self.tactics = None
        self.intercepts = None
        self._build()
