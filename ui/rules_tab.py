# ui/rules_tab.py
import customtkinter as ctk
import os
import yaml
from ui.team_selector import TeamSelectorDialog
from ui.rule_builder_dialog import RuleBuilderDialog
from ui.active_rules_dialog import ActiveRulesDialog
from ui.telegram_dialog import TelegramDialog # ИМПОРТ НОВОГО ОКНА
from i18n import get_text

class RulesFrame(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, corner_radius=10, fg_color="transparent", **kwargs)
        self.controller = controller 
        self.team_labels = {} 
        self.room_btns = {}
        self.cond_btns = []
        
        # Хранилище настроек телеграма до сохранения профиля
        self.tg_settings = {"active": False, "token": "", "chat_id": ""}
        
        self.goals_data = {"titanite": 0, "rooms": 0, "floors": 0, "time": 0}
        self.current_goal_key = "titanite" 

        self.grid_columnconfigure(0, weight=0) 
        self.grid_columnconfigure(1, weight=1) 
        self.grid_columnconfigure(2, weight=0) 

        self.lbl_title_base = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title_base.grid(row=0, column=0, columnspan=3, pady=(0, 15), sticky="w")
        
        self.goal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.goal_frame.grid(row=1, column=0, columnspan=3, sticky="w", pady=5)
        
        self.lbl_goal = ctk.CTkLabel(self.goal_frame, text="")
        self.lbl_goal.grid(row=0, column=0, padx=(5, 10))
        
        self.current_goal_var = ctk.StringVar()
        self.opt_goal = ctk.CTkOptionMenu(self.goal_frame, values=[], variable=self.current_goal_var, command=self.on_goal_switch)
        self.opt_goal.grid(row=0, column=1, padx=5)
        
        self.entry_goal_val = ctk.CTkEntry(self.goal_frame, width=80)
        self.entry_goal_val.grid(row=0, column=2, padx=10)
        self.entry_goal_val.bind("<KeyRelease>", self.on_goal_type)

        self.btn_reset_goals = ctk.CTkButton(self.goal_frame, text="", width=100, fg_color="#6c757d", hover_color="#5a6268", command=self.reset_goals)
        self.btn_reset_goals.grid(row=0, column=3, padx=15)

        self.hp_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.hp_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=5)
        
        self.lbl_hp = ctk.CTkLabel(self.hp_frame, text="")
        self.lbl_hp.grid(row=0, column=0, padx=5)
        self.entry_hp = ctk.CTkEntry(self.hp_frame, width=60)
        self.entry_hp.grid(row=0, column=1, padx=10)
        
        self.lbl_delta = ctk.CTkLabel(self.hp_frame, text="")
        self.lbl_delta.grid(row=0, column=2, padx=(15, 5))
        self.entry_delta = ctk.CTkEntry(self.hp_frame, width=60)
        self.entry_delta.grid(row=0, column=3, padx=10)

        self.time_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.time_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=5)
        
        self.lbl_reset_hour = ctk.CTkLabel(self.time_frame, text="")
        self.lbl_reset_hour.grid(row=0, column=0, padx=5)
        
        hours_list = [f"{i:02d}:00" for i in range(24)]
        self.opt_reset_hour = ctk.CTkOptionMenu(self.time_frame, values=hours_list, width=90)
        self.opt_reset_hour.grid(row=0, column=1, padx=10)

        # НОВЫЙ БЛОК: Ангус + Кнопка Telegram в одной строке
        self.misc_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.misc_frame.grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 10))

        self.switch_angus_var = ctk.StringVar(value="off")
        self.switch_angus = ctk.CTkSwitch(self.misc_frame, text="", variable=self.switch_angus_var, onvalue="on", offvalue="off")
        self.switch_angus.pack(side="left", padx=5)
        
        self.btn_tg_setup = ctk.CTkButton(self.misc_frame, text="", fg_color="#17a2b8", hover_color="#138496", command=self.open_tg_dialog)
        self.btn_tg_setup.pack(side="left", padx=30)

        self.lbl_title_rooms = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title_rooms.grid(row=5, column=0, columnspan=3, pady=(20, 10), sticky="w")

        self.create_room_row("earth", 6)
        self.create_room_row("water", 7)
        self.create_room_row("fire", 8)
        self.create_room_row("mix", 9)

        self.btn_show_rules = ctk.CTkButton(self, text="", fg_color="#444444", hover_color="#555555", command=self.open_active_rules)
        self.btn_show_rules.grid(row=10, column=0, columnspan=3, pady=(20, 5), sticky="ew")

        self.btn_save_rules = ctk.CTkButton(self, text="", fg_color="#6f42c1", hover_color="#59359a", command=self.save_profile)
        self.btn_save_rules.grid(row=11, column=0, columnspan=3, pady=(5, 10), sticky="ew")

        self.load_profile_to_gui()

    def update_language(self, lang):
        self.lbl_title_base.configure(text=get_text(lang, "rules_title_base"))
        self.lbl_goal.configure(text=get_text(lang, "rules_goal"))
        self.btn_reset_goals.configure(text=get_text(lang, "rules_btn_reset"))
        self.lbl_hp.configure(text=get_text(lang, "rules_hp_panic"))
        self.lbl_delta.configure(text=get_text(lang, "rules_hp_delta"))
        self.lbl_reset_hour.configure(text=get_text(lang, "rules_reset_hour"))
        self.switch_angus.configure(text=get_text(lang, "rules_angus"))
        self.btn_tg_setup.configure(text=get_text(lang, "rules_btn_tg"))
        
        self.lbl_title_rooms.configure(text=get_text(lang, "rules_title_rooms"))
        self.btn_show_rules.configure(text=get_text(lang, "rules_btn_active"))
        self.btn_save_rules.configure(text=get_text(lang, "rules_btn_save"))

        values = [get_text(lang, "goal_titanite"), get_text(lang, "goal_rooms"), get_text(lang, "goal_floors"), get_text(lang, "goal_time")]
        self.opt_goal.configure(values=values)
        self.current_goal_var.set(get_text(lang, f"goal_{self.current_goal_key}"))

        for r_type in ["earth", "water", "fire", "mix"]:
            self.room_btns[r_type].configure(text=get_text(lang, f"elem_{r_type}"))
            self.team_labels[r_type].configure(text=self.get_yaml_team(r_type))

        for btn in self.cond_btns:
            btn.configure(text=get_text(lang, "rules_btn_cond"))

    def open_tg_dialog(self):
        def on_save(data):
            self.tg_settings = data
            self.controller.frames["dash"].append_log("[GUI] Настройки Telegram обновлены (не забудьте сохранить профиль)!\n")
        TelegramDialog(self.controller, self.controller, self.tg_settings, on_save)

    def on_goal_switch(self, selected_text):
        lang = getattr(self.controller, 'current_lang', 'RU')
        for key in ["titanite", "rooms", "floors", "time"]:
            if get_text(lang, f"goal_{key}") == selected_text:
                self.current_goal_key = key
                break
        
        self.entry_goal_val.delete(0, 'end')
        self.entry_goal_val.insert(0, str(self.goals_data[self.current_goal_key]))

    def on_goal_type(self, event):
        val = self.entry_goal_val.get()
        if val.isdigit():
            self.goals_data[self.current_goal_key] = int(val)

    def reset_goals(self):
        for k in self.goals_data:
            self.goals_data[k] = 0
        self.entry_goal_val.delete(0, 'end')
        self.entry_goal_val.insert(0, "0")
        self.controller.frames["dash"].append_log("[GUI] Target reset!\n")

    def open_active_rules(self):
        ActiveRulesDialog(self.controller, self.controller)

    def create_room_row(self, room_type, row_idx):
        btn_pack = ctk.CTkButton(self, text="", width=140, command=lambda: self.set_default_pack(room_type))
        btn_pack.grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        self.room_btns[room_type] = btn_pack
        
        lbl_team = ctk.CTkLabel(self, text="", text_color="#28a745")
        lbl_team.grid(row=row_idx, column=1, padx=(10, 5), pady=5, sticky="w")
        self.team_labels[room_type] = lbl_team 
        
        btn_rule = ctk.CTkButton(self, text="", width=100, fg_color="#444444", hover_color="#555555", command=lambda: self.add_custom_rule(room_type))
        btn_rule.grid(row=row_idx, column=2, padx=5, pady=5, sticky="e")
        self.cond_btns.append(btn_rule)

    def get_yaml_team(self, room_type):
        path = f"rules/{room_type}.yml"
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                team = data.get("default_team", [])
                if team:
                    lang = getattr(self.controller, 'current_lang', 'RU')
                    return ", ".join([get_text(lang, f"titan_{t}") for t in team])
        return get_text(getattr(self.controller, 'current_lang', 'RU'), "rules_no_pack")

    def set_default_pack(self, room_type):
        def on_team_selected(new_team):
            self.save_default_pack_to_yaml(room_type, new_team)
            lang = getattr(self.controller, 'current_lang', 'RU')
            loc_team_str = ", ".join([get_text(lang, f"titan_{t}") for t in new_team])
            self.team_labels[room_type].configure(text=loc_team_str)
        TeamSelectorDialog(self.controller, on_team_selected, room_type=room_type, context="rule")

    def add_custom_rule(self, room_type):
        def on_rule_saved(rule_name, r_type):
            self.controller.frames["dash"].append_log(f"[GUI] Rule '{rule_name}' added!\n")
        RuleBuilderDialog(self.controller, room_type, on_rule_saved)

    def save_default_pack_to_yaml(self, room_type, team):
        if not os.path.exists("rules"): os.makedirs("rules")
        file_path = f"rules/{room_type}.yml"
        data = {"rules": []}
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f: data = yaml.safe_load(f) or {}
        data["default_team"] = team
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def load_profile_to_gui(self):
        if not os.path.exists("profile.yml"): return
        with open("profile.yml", 'r', encoding='utf-8') as f: profile = yaml.safe_load(f) or {}
        settings = profile.get("settings", {})
        
        self.goals_data["titanite"] = settings.get("target_titanite", 0)
        self.goals_data["rooms"] = settings.get("target_rooms", 0)
        self.goals_data["floors"] = settings.get("target_floors", 0)
        self.goals_data["time"] = settings.get("target_time", 0)
        
        self.entry_goal_val.delete(0, 'end')
        self.entry_goal_val.insert(0, str(self.goals_data[self.current_goal_key]))
        
        thresholds = profile.get("global_thresholds", {})
        self.entry_hp.insert(0, str(thresholds.get("critical_hp", 40)))
        self.entry_delta.insert(0, str(thresholds.get("max_hp_delta", 30)))
        
        reset_hour = settings.get("reset_hour", 5)
        self.opt_reset_hour.set(f"{reset_hour:02d}:00")
        
        if settings.get("angus_manual_control", False): self.switch_angus.select()
        else: self.switch_angus.deselect()
            
        tg_data = settings.get("telegram", {})
        self.tg_settings = {
            "active": tg_data.get("active", False),
            "token": tg_data.get("token", ""),
            "chat_id": str(tg_data.get("chat_id", ""))
        }

    def save_profile(self):
        if not os.path.exists("profile.yml"): profile = {}
        else:
            with open("profile.yml", 'r', encoding='utf-8') as f: profile = yaml.safe_load(f) or {}
            
        if "settings" not in profile: profile["settings"] = {}
        if "global_thresholds" not in profile: profile["global_thresholds"] = {}
        
        try:
            profile["settings"]["target_titanite"] = self.goals_data["titanite"]
            profile["settings"]["target_rooms"] = self.goals_data["rooms"]
            profile["settings"]["target_floors"] = self.goals_data["floors"]
            profile["settings"]["target_time"] = self.goals_data["time"]
            
            profile["global_thresholds"]["critical_hp"] = int(self.entry_hp.get() or 40)
            profile["global_thresholds"]["max_hp_delta"] = int(self.entry_delta.get() or 30)
            
            hour_str = self.opt_reset_hour.get().split(":")[0]
            profile["settings"]["reset_hour"] = int(hour_str)
        except ValueError:
            return
            
        profile["settings"]["angus_manual_control"] = (self.switch_angus_var.get() == "on")
        profile["settings"]["telegram"] = self.tg_settings
        
        with open("profile.yml", 'w', encoding='utf-8') as f:
            yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)
            
        self.controller.frames["dash"].append_log("[GUI] Профиль настроек сохранен!\n")