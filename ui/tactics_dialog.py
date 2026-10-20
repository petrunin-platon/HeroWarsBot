# ui/tactics_dialog.py
# Окно «Тактика» (задачи 9, 9б, 9в): настройки, с которыми бот решает сам. Всё задаётся мышкой, файлы руками править не нужно.
# Кнопка «Применить» сразу пишет настройки в profile.yml (остальные настройки профиля не трогает).
# Переключатель «Бот решает сам» — на вкладке настроек (ui/rules_tab.py), здесь его нет.
import os
import shutil

import customtkinter as ctk
import yaml

import data_paths
import tactics
from i18n import get_text
from ui.team_selector import ELEMENTS, TeamSelectorDialog

ROOMS = ["earth", "water", "fire", "mix"]
MAX_BACKUPS = 5  # запасных паков на стихию


def load_profile():
    """profile.yml словарём. {} — файла нет; None — файл повреждён."""
    if not os.path.exists("profile.yml"):
        return {}
    try:
        with open("profile.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_profile(profile):
    with open("profile.yml", "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)
    shutil.copy2("profile.yml", data_paths.profile_backup_file())


def digits(entry, limit):
    """Оставляет в поле только цифры, не больше limit."""
    val = entry.get()
    clean = "".join(filter(str.isdigit, val))
    if clean and int(clean) > limit:
        clean = str(limit)
    if val != clean:
        entry.delete(0, "end")
        entry.insert(0, clean)


class TacticsDialog(ctk.CTkToplevel):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.lang = getattr(controller, "current_lang", "RU")
        self.current_lang = self.lang  # окно выбора титанов берёт язык у родителя
        self.values = tactics.read_tactics(load_profile() or {})
        lang = self.lang

        self.title(get_text(lang, "tac_title"))
        self.geometry("820x640")
        self.transient(master)
        self.after(100, self.grab_set)

        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        bold = ctk.CTkFont(size=14, weight="bold")

        ctk.CTkLabel(body, text=get_text(lang, "tac_hint"), wraplength=740, justify="left").pack(anchor="w", pady=(0, 12))

        # 1. Сколько запасных паков пробовать
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(anchor="w", pady=4)
        ctk.CTkLabel(row, text=get_text(lang, "tac_tries")).pack(side="left", padx=(0, 10))
        self.opt_tries = ctk.CTkOptionMenu(row, values=[str(i) for i in range(1, tactics.MAX_TRIES + 1)], width=70)
        self.opt_tries.set(str(self.values["auto_rollback_tries"]))
        self.opt_tries.pack(side="left")

        # 1а. Через сколько минут без ответа на окно SOS бот решает сам (задача 9б)
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(anchor="w", pady=4)
        ctk.CTkLabel(row, text=get_text(lang, "tac_sos_timeout")).pack(side="left", padx=(0, 10))
        self.entry_sos_timeout = self._number_entry(row, self.values["sos_timeout_minutes"], tactics.MAX_SOS_TIMEOUT)
        self.entry_sos_timeout.pack(side="left")

        # 2. Общие потери пака
        ctk.CTkLabel(body, text=get_text(lang, "tac_group_title"), font=bold).pack(anchor="w", pady=(14, 4))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(anchor="w")
        ctk.CTkLabel(row, text=get_text(lang, "tac_group_titans")).pack(side="left", padx=(0, 6))
        self.entry_group_titans = self._number_entry(row, self.values["group_loss_titans"], 5)
        self.entry_group_titans.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(row, text=get_text(lang, "tac_group_percent")).pack(side="left", padx=(0, 6))
        self.entry_group_percent = self._number_entry(row, self.values["group_loss_percent"], 100)
        self.entry_group_percent.pack(side="left")

        # 3. Порядок дверей
        ctk.CTkLabel(body, text=get_text(lang, "tac_doors_title"), font=bold).pack(anchor="w", pady=(14, 4))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(anchor="w")
        self.room_by_text = {get_text(lang, f"elem_{r}"): r for r in tactics.DEFAULT_DOOR_ORDER}
        self.door_order = list(self.values["door_order"])
        self.door_menus = []
        for i, room in enumerate(self.door_order):
            ctk.CTkLabel(row, text=f"{i + 1}.").pack(side="left", padx=(8 if i else 0, 4))
            menu = ctk.CTkOptionMenu(row, values=list(self.room_by_text), width=150,
                                     command=lambda text, i=i: self._on_door(i, text))
            menu.set(get_text(lang, f"elem_{room}"))
            menu.pack(side="left")
            self.door_menus.append(menu)

        # 4. Запасные паки
        ctk.CTkLabel(body, text=get_text(lang, "tac_backup_title"), font=bold).pack(anchor="w", pady=(14, 4))
        self.backup_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.backup_frame.pack(anchor="w", fill="x")
        self._draw_backups()

        # 5. Личные пороги паники
        ctk.CTkLabel(body, text=get_text(lang, "tac_personal_title"), font=bold).pack(anchor="w", pady=(14, 4))
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(anchor="w")
        self.personal_entries = {}
        titans = [t for group in ELEMENTS.values() for t in group]
        for i, titan in enumerate(titans):
            r, c = divmod(i, 4)
            ctk.CTkLabel(grid, text=get_text(lang, f"titan_{titan}"), width=110, anchor="e").grid(row=r, column=c * 2, padx=(10, 4), pady=2)
            value = self.values["titan_critical_hp"].get(titan, "")
            entry = self._number_entry(grid, value, 100)
            entry.grid(row=r, column=c * 2 + 1, pady=2, sticky="w")
            self.personal_entries[titan] = entry

        # 6. Пак отхила в смешанной (задача 9в): с какого ХП лечить и кого убирать из пака ради раненого
        ctk.CTkLabel(body, text=get_text(lang, "tac_heal_title"), font=bold).pack(anchor="w", pady=(14, 4))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(anchor="w", pady=4)
        ctk.CTkLabel(row, text=get_text(lang, "tac_heal_hp")).pack(side="left", padx=(0, 10))
        self.entry_heal_hp = self._number_entry(row, self.values["heal_below_hp"], 100)
        self.entry_heal_hp.pack(side="left")
        ctk.CTkLabel(body, text=get_text(lang, "tac_heal_remove")).pack(anchor="w", pady=(4, 0))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(anchor="w", pady=4)
        auto = get_text(lang, "tac_heal_auto")
        self.titan_by_text = {get_text(lang, f"titan_{t}"): t for t in titans}
        order = self.values["heal_remove_order"]
        self.remove_menus = []
        for i in range(tactics.MAX_HEAL_REMOVE):
            ctk.CTkLabel(row, text=f"{i + 1}.").pack(side="left", padx=(8 if i else 0, 4))
            menu = ctk.CTkOptionMenu(row, values=[auto] + list(self.titan_by_text), width=130)
            menu.set(get_text(lang, f"titan_{order[i]}") if i < len(order) else auto)
            menu.pack(side="left")
            self.remove_menus.append(menu)

        # Кнопки
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(pady=12)
        ctk.CTkButton(footer, text=get_text(lang, "btn_apply"), fg_color="#28a745", hover_color="#218838",
                      command=self.on_apply).pack(side="left", padx=10)
        ctk.CTkButton(footer, text=get_text(lang, "btn_cancel"), fg_color="#6c757d", hover_color="#5a6268",
                      command=self.destroy).pack(side="left", padx=10)

    def _number_entry(self, parent, value, limit):
        entry = ctk.CTkEntry(parent, width=55)
        if value != "" and value is not None:
            entry.insert(0, str(value))
        entry.bind("<KeyRelease>", lambda e: digits(entry, limit))
        return entry

    def _on_door(self, index, text):
        """Выбрали стихию, которая уже стоит на другом месте, — меняем их местами (повторов не бывает)."""
        room = self.room_by_text.get(text)
        if room is None:
            return
        other = self.door_order.index(room)
        self.door_order[index], self.door_order[other] = room, self.door_order[index]
        for menu, r in zip(self.door_menus, self.door_order):
            menu.set(get_text(self.lang, f"elem_{r}"))

    # --- запасные паки ---
    def _draw_backups(self):
        for child in self.backup_frame.winfo_children():
            child.destroy()
        lang = self.lang
        teams = self.values["backup_teams"]
        for r, room in enumerate(ROOMS):
            ctk.CTkLabel(self.backup_frame, text=get_text(lang, f"elem_{room}"), width=130, anchor="w").grid(
                row=r * (MAX_BACKUPS + 1), column=0, sticky="w", pady=(6, 0))
            packs = teams.get(room, [])
            add = ctk.CTkButton(self.backup_frame, text=get_text(lang, "tac_backup_add"), width=100,
                                fg_color="#444444", hover_color="#555555",
                                command=lambda room=room: self._add_backup(room))
            add.grid(row=r * (MAX_BACKUPS + 1), column=1, sticky="w", pady=(6, 0))
            if len(packs) >= MAX_BACKUPS:
                add.configure(state="disabled")
            if not packs:
                ctk.CTkLabel(self.backup_frame, text=get_text(lang, "tac_backup_none"), text_color="gray").grid(
                    row=r * (MAX_BACKUPS + 1), column=2, sticky="w", padx=10, pady=(6, 0))
            for i, pack in enumerate(packs):
                line = r * (MAX_BACKUPS + 1) + i + 1
                names = ", ".join(get_text(lang, f"titan_{t}") for t in pack)
                ctk.CTkLabel(self.backup_frame, text=f"{i + 1}) {names}", text_color="#28a745").grid(
                    row=line, column=0, columnspan=2, sticky="w", padx=(20, 0))
                ctk.CTkButton(self.backup_frame, text="✕", width=30, fg_color="#dc3545", hover_color="#c82333",
                              command=lambda room=room, i=i: self._remove_backup(room, i)).grid(
                    row=line, column=2, sticky="w", padx=10)

    def _add_backup(self, room):
        def on_selected(team):
            self.after(100, self.grab_set)  # окно выбора титанов забирало фокус
            if not team or team == ["STOP_BOT"]:
                return
            packs = self.values["backup_teams"].setdefault(room, [])
            if sorted(team) not in [sorted(p) for p in packs]:
                packs.append(list(team))
            self._draw_backups()
        TeamSelectorDialog(self, on_selected, room_type=room, context="rule")

    def _remove_backup(self, room, index):
        packs = self.values["backup_teams"].get(room, [])
        if 0 <= index < len(packs):
            packs.pop(index)
        if not packs:
            self.values["backup_teams"].pop(room, None)
        self._draw_backups()

    # --- сохранение ---
    def _collect(self):
        def number(entry, default):
            text = entry.get().strip()
            return int(text) if text.isdigit() else default

        personal = {}
        for titan, entry in self.personal_entries.items():
            text = entry.get().strip()
            if text.isdigit():
                personal[titan] = int(text)
        return {
            "auto_rollback_tries": int(self.opt_tries.get()),
            "sos_timeout_minutes": number(self.entry_sos_timeout, self.values["sos_timeout_minutes"]),
            "group_loss_titans": number(self.entry_group_titans, self.values["group_loss_titans"]),
            "group_loss_percent": number(self.entry_group_percent, self.values["group_loss_percent"]),
            "titan_critical_hp": personal,
            "backup_teams": {room: packs for room, packs in self.values["backup_teams"].items() if packs},
            "door_order": tactics.door_order(self.door_order),
            "heal_below_hp": number(self.entry_heal_hp, self.values["heal_below_hp"]),
            "heal_remove_order": self._heal_remove_order(),
        }

    def _heal_remove_order(self):
        """Кого убирать из пака ради раненого: выбранные титаны по порядку, без повторов («— сам —» пропускается)."""
        order = []
        for menu in self.remove_menus:
            titan = self.titan_by_text.get(menu.get())
            if titan and titan not in order:
                order.append(titan)
        return order

    def on_apply(self):
        dash = self.controller.frames.get("dash") if hasattr(self.controller, "frames") else None
        profile = load_profile()
        if profile is None:
            if dash:
                dash.append_log(get_text(self.lang, "tac_err_profile"))
            return
        tactics.write_tactics(profile, self._collect())
        try:
            save_profile(profile)
        except Exception as e:
            if dash:
                dash.append_log(f"[ОШИБКА] Не удалось сохранить profile.yml: {e}\n")
            return
        if dash:
            dash.append_log(get_text(self.lang, "tac_saved"))
        self.grab_release()
        self.destroy()
