import customtkinter as ctk
import os
import yaml
from i18n import get_text
from ui.team_selector import TeamSelectorDialog, ELEMENTS, ALLOWED_ELEMENTS

DUNGEON_ENEMIES_EN = ["angus", "avalon", "eden", "silva", "verdok", "sigurd", "hyperion", "nova", "mairi", "araji", "ignis", "vulcan", "moloch"]

class RuleBuilderDialog(ctk.CTkToplevel):
    def __init__(self, master, room_type, callback, edit_index=None, edit_data=None):
        super().__init__(master)
        self.room_type = room_type
        self.callback = callback
        self.target_team = []
        self.require_fought_team = [] 
        self.action_is_stop = ctk.BooleanVar(value=False)
        self.action_is_skip = ctk.BooleanVar(value=False) 
        self.enemy_vars = {} 
        self.edit_index = edit_index 
        
        lang = 'RU'
        if hasattr(master, 'current_lang'): lang = master.current_lang
        elif hasattr(master, 'master') and hasattr(master.master, 'current_lang'): lang = master.master.current_lang
        self.lang = lang
        
        title_key = "rb_edit" if edit_data else "rb_create"
        self.title(get_text(self.lang, title_key).format(room=get_text(self.lang, f"elem_{room_type}")))
        self.geometry("650x700") 
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        self.after(100, self.grab_set)

        self.grid_columnconfigure(0, weight=1)

        self.lbl_title = ctk.CTkLabel(self, text=get_text(self.lang, "rb_title").format(room=get_text(self.lang, f"elem_{room_type}")), font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_title.grid(row=0, column=0, pady=(15, 10))

        self.entry_name = ctk.CTkEntry(self, placeholder_text=get_text(self.lang, "rb_name"), width=480)
        self.entry_name.grid(row=1, column=0, pady=5)

        self.segment_type = ctk.CTkSegmentedButton(
            self, 
            values=[get_text(self.lang, "rb_type_hp"), get_text(self.lang, "rb_type_energy"), get_text(self.lang, "rb_type_enemies")],
            command=self.on_type_change
        )
        self.segment_type.grid(row=2, column=0, pady=15)

        allowed_elements = ALLOWED_ELEMENTS.get(self.room_type, ALLOWED_ELEMENTS["all"])
        self.available_titans_en = []
        for elem, group in ELEMENTS.items():
            if elem in allowed_elements:
                self.available_titans_en.extend(group)
                
        if not self.available_titans_en: self.available_titans_en = ["araji"]
        display_titans = [get_text(self.lang, f"titan_{t}") for t in self.available_titans_en]

        self.hp_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.opt_titan_hp = ctk.CTkOptionMenu(self.hp_frame, values=display_titans)
        self.opt_titan_hp.grid(row=0, column=0, padx=10, pady=10)
        ctk.CTkLabel(self.hp_frame, text=get_text(self.lang, "rb_hp_below")).grid(row=0, column=1, padx=5, pady=10)
        self.entry_hp_val = ctk.CTkEntry(self.hp_frame, width=60)
        self.entry_hp_val.grid(row=0, column=2, padx=10, pady=10)

        self.energy_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.opt_titan_en = ctk.CTkOptionMenu(self.energy_frame, values=display_titans)
        self.opt_titan_en.grid(row=0, column=0, padx=10, pady=10)
        ctk.CTkLabel(self.energy_frame, text=get_text(self.lang, "rb_energy_below")).grid(row=0, column=1, padx=5, pady=10)
        self.entry_en_val = ctk.CTkEntry(self.energy_frame, width=60)
        self.entry_en_val.grid(row=0, column=2, padx=10, pady=10)

        self.enemies_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        ctk.CTkLabel(self.enemies_frame, text=get_text(self.lang, "rb_enemies_pick")).grid(row=0, column=0, columnspan=3, pady=(5, 5))
        
        row, col = 1, 0
        for enemy_en in DUNGEON_ENEMIES_EN:
            var = ctk.BooleanVar(value=False)
            self.enemy_vars[enemy_en] = var
            chk = ctk.CTkCheckBox(self.enemies_frame, text=get_text(self.lang, f"titan_{enemy_en}"), variable=var)
            chk.grid(row=row, column=col, padx=10, pady=5, sticky="w")
            col += 1
            if col > 2:
                col = 0
                row += 1

        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=4, column=0, pady=15)
        
        self.chk_stop = ctk.CTkCheckBox(self.action_frame, text=get_text(self.lang, "rb_action_stop"), variable=self.action_is_stop, command=self.toggle_action)
        self.chk_stop.pack(pady=(0, 5))

        self.chk_skip = ctk.CTkCheckBox(self.action_frame, text=get_text(self.lang, "rb_action_skip"), text_color="#ffc107", variable=self.action_is_skip, command=self.toggle_action)
        self.chk_skip.pack(pady=(0, 15))

        self.btn_req_fought = ctk.CTkButton(self.action_frame, text=get_text(self.lang, "rb_req_fought_btn"), fg_color="#17a2b8", hover_color="#138496", command=self.pick_req_fought)
        self.btn_req_fought.pack(pady=(0, 5))
        
        self.lbl_req_fought_preview = ctk.CTkLabel(self.action_frame, text=get_text(self.lang, "rb_req_fought_none"), text_color="gray")
        self.lbl_req_fought_preview.pack(pady=(0, 10))

        self.btn_pick_team = ctk.CTkButton(self.action_frame, text=get_text(self.lang, "rb_btn_pick"), fg_color="#007bff", hover_color="#0056b3", command=self.pick_team)
        self.btn_pick_team.pack(pady=(0, 5))
        
        self.lbl_team_preview = ctk.CTkLabel(self.action_frame, text=get_text(self.lang, "rb_team_preview_none"), text_color="yellow")
        self.lbl_team_preview.pack()

        self.btn_save = ctk.CTkButton(self, text=get_text(self.lang, "rb_btn_save"), fg_color="#28a745", hover_color="#218838", state="disabled", command=self.save_rule)
        self.btn_save.grid(row=5, column=0, pady=20, padx=60, sticky="ew")

        if edit_data:
            self.load_edit_data(edit_data)
        else:
            self.segment_type.set(get_text(self.lang, "rb_type_hp"))
            self.on_type_change(get_text(self.lang, "rb_type_hp"))
            self.entry_hp_val.insert(0, "35")
            self.entry_en_val.insert(0, "100")

    def _get_en_key(self, disp_text):
        for t in self.available_titans_en:
            if get_text(self.lang, f"titan_{t}") == disp_text: 
                return t
        return self.available_titans_en[0]

    def load_edit_data(self, data):
        self.entry_name.insert(0, data.get("name", ""))
        cond = data.get("condition", {})
        
        if "titan_hp_below" in cond:
            self.segment_type.set(get_text(self.lang, "rb_type_hp"))
            self.on_type_change(get_text(self.lang, "rb_type_hp"))
            for t, val in cond["titan_hp_below"].items():
                self.opt_titan_hp.set(get_text(self.lang, f"titan_{t}"))
                self.entry_hp_val.insert(0, str(val))
        elif "titan_energy_below" in cond:
            self.segment_type.set(get_text(self.lang, "rb_type_energy"))
            self.on_type_change(get_text(self.lang, "rb_type_energy"))
            for t, val in cond["titan_energy_below"].items():
                self.opt_titan_en.set(get_text(self.lang, f"titan_{t}"))
                self.entry_en_val.insert(0, str(val))
        elif "enemies_contain" in cond:
            self.segment_type.set(get_text(self.lang, "rb_type_enemies"))
            self.on_type_change(get_text(self.lang, "rb_type_enemies"))
            for e_en in cond["enemies_contain"]:
                if e_en in self.enemy_vars:
                    self.enemy_vars[e_en].set(True)

        if "require_fought" in cond:
            self.require_fought_team = cond["require_fought"]
            team_str = ", ".join([get_text(self.lang, f"titan_{t}") for t in self.require_fought_team])
            self.lbl_req_fought_preview.configure(text=get_text(self.lang, "rb_req_fought_team").format(team=team_str), text_color="#17a2b8")

        if data.get("action") == "skip":
            self.action_is_skip.set(True)
            self.toggle_action()
            return

        team = data.get("team", [])
        if team == ["STOP"]:
            self.action_is_stop.set(True)
            self.toggle_action()
        elif team:
            self.target_team = team
            team_str = ", ".join([get_text(self.lang, f"titan_{t}") for t in team])
            self.lbl_team_preview.configure(text=get_text(self.lang, "rb_team_preview").format(team=team_str), text_color="#28a745")
            self.btn_save.configure(state="normal")

    def toggle_action(self):
        if self.action_is_stop.get():
            self.action_is_skip.set(False)
            self.btn_pick_team.configure(state="disabled")
            self.btn_req_fought.configure(state="disabled")
            self.lbl_team_preview.configure(text=get_text(self.lang, "rb_action_stop_preview"), text_color="#dc3545")
            self.btn_save.configure(state="normal")
            self.target_team = ["STOP"]
            
        elif self.action_is_skip.get():
            self.action_is_stop.set(False)
            self.btn_pick_team.configure(state="disabled")
            self.btn_req_fought.configure(state="disabled")
            self.lbl_team_preview.configure(text=get_text(self.lang, "rb_action_skip_preview"), text_color="#ffc107")
            self.btn_save.configure(state="normal")
            self.target_team = []
            
        else:
            self.btn_pick_team.configure(state="normal")
            self.btn_req_fought.configure(state="normal")
            if not self.target_team or self.target_team == ["STOP"]:
                self.lbl_team_preview.configure(text=get_text(self.lang, "rb_team_preview_none"), text_color="yellow")
                self.btn_save.configure(state="disabled")
                self.target_team = []
            else:
                team_str = ", ".join([get_text(self.lang, f"titan_{t}") for t in self.target_team])
                self.lbl_team_preview.configure(text=get_text(self.lang, "rb_team_preview").format(team=team_str), text_color="#28a745")
                self.btn_save.configure(state="normal")

    def on_type_change(self, value):
        self.hp_frame.grid_forget()
        self.energy_frame.grid_forget()
        self.enemies_frame.grid_forget()
        if value == get_text(self.lang, "rb_type_hp"): self.hp_frame.grid(row=3, column=0, padx=40, pady=10, sticky="ew")
        elif value == get_text(self.lang, "rb_type_energy"): self.energy_frame.grid(row=3, column=0, padx=40, pady=10, sticky="ew")
        elif value == get_text(self.lang, "rb_type_enemies"): self.enemies_frame.grid(row=3, column=0, padx=40, pady=10, sticky="ew")

    def pick_team(self):
        selected_type = self.segment_type.get()
        preselect_titan = None
        
        if selected_type == get_text(self.lang, "rb_type_hp") and not self.action_is_skip.get():
            preselect_titan = self._get_en_key(self.opt_titan_hp.get())
        elif selected_type == get_text(self.lang, "rb_type_energy") and not self.action_is_skip.get():
            preselect_titan = self._get_en_key(self.opt_titan_en.get())
            
        self.grab_release()
            
        def on_selected(team):
            self.after(100, self.grab_set)
            
            if team is not None:
                self.target_team = team
                if team:
                    team_str = ", ".join([get_text(self.lang, f"titan_{t}") for t in team])
                    self.lbl_team_preview.configure(text=get_text(self.lang, "rb_team_preview").format(team=team_str), text_color="#28a745")
                    self.btn_save.configure(state="normal")
                else:
                    self.lbl_team_preview.configure(text=get_text(self.lang, "rb_team_preview_none"), text_color="yellow")
                    self.btn_save.configure(state="disabled")
            
        TeamSelectorDialog(self, on_selected, room_type=self.room_type, context="rule", preselect_titan=preselect_titan)

    def pick_req_fought(self):
        self.grab_release()
        
        def on_selected(team):
            self.after(100, self.grab_set)
            
            if team is not None:
                self.require_fought_team = team
                if team:
                    team_str = ", ".join([get_text(self.lang, f"titan_{t}") for t in team])
                    self.lbl_req_fought_preview.configure(text=get_text(self.lang, "rb_req_fought_team").format(team=team_str), text_color="#17a2b8")
                else:
                    self.lbl_req_fought_preview.configure(text=get_text(self.lang, "rb_req_fought_none"), text_color="gray")
                
        TeamSelectorDialog(self, on_selected, room_type="all", context="rule")

    def save_rule(self):
        rule_name = self.entry_name.get().strip() or "Auto Rule"
        selected_type = self.segment_type.get()
        condition = {}

        if selected_type == get_text(self.lang, "rb_type_hp"):
            t_en = self._get_en_key(self.opt_titan_hp.get())
            condition = {"titan_hp_below": {t_en: int(self.entry_hp_val.get() or 35)}}
        elif selected_type == get_text(self.lang, "rb_type_energy"):
            t_en = self._get_en_key(self.opt_titan_en.get())
            condition = {"titan_energy_below": {t_en: int(self.entry_en_val.get() or 100)}}
        else:
            enemies_list = [en for en, var in self.enemy_vars.items() if var.get()]
            condition = {"enemies_contain": enemies_list}

        if self.require_fought_team:
            condition["require_fought"] = self.require_fought_team

        rule_obj = {"name": rule_name, "condition": condition, "team": self.target_team}
        
        if self.action_is_skip.get():
            rule_obj["action"] = "skip"

        if not os.path.exists("rules"): os.makedirs("rules")
        file_path = f"rules/{self.room_type}.yml"
        
        with open(file_path, "r", encoding="utf-8") as f: data = yaml.safe_load(f) or {"rules": []}
        if "rules" not in data or data["rules"] is None: data["rules"] = []
        
        if self.edit_index is not None:
            data["rules"][self.edit_index] = rule_obj
        else:
            data["rules"].insert(0, rule_obj)
            
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        self.grab_release() 
        self.callback(rule_name, self.room_type)
        self.destroy()