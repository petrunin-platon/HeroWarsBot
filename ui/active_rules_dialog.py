import customtkinter as ctk
import os
import yaml
from i18n import get_text
from ui.rule_builder_dialog import RuleBuilderDialog

class ActiveRulesDialog(ctk.CTkToplevel):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        lang = getattr(self.controller, 'current_lang', 'RU')
        
        self.title(get_text(lang, "ar_title"))
        self.geometry("800x480") 
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        self.after(100, self.grab_set)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=get_text(lang, "ar_list"), font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, pady=(15, 10), padx=20, sticky="w")

        self.rules_scroll = ctk.CTkScrollableFrame(self, fg_color="#1e1e1e")
        self.rules_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))

        self.btn_clear_all = ctk.CTkButton(self, text=get_text(lang, "ar_btn_clear"), font=ctk.CTkFont(weight="bold"), fg_color="#dc3545", hover_color="#c82333", command=self.clear_all_rules)
        self.btn_clear_all.grid(row=2, column=0, pady=(0, 15), padx=20, sticky="ew")

        self.refresh_rules_list()

    def generate_rule_name(self, rule, lang):
        base_name = get_text(lang, "ar_no_name")
        cond = rule.get("condition", {})
        
        if "name" in rule: 
            base_name = rule["name"]
        elif "titan_hp_below" in cond:
            for t, val in cond["titan_hp_below"].items(): 
                base_name = f"{get_text(lang, 'ar_if_hp')} {get_text(lang, f'titan_{t}')} < {val}%"
                break
        elif "titan_energy_below" in cond:
            for t, val in cond["titan_energy_below"].items(): 
                base_name = f"{get_text(lang, 'ar_if_energy')} {get_text(lang, f'titan_{t}')} < {val}%"
                break
        elif "enemies_contain" in cond:
            enemies_str = ", ".join([get_text(lang, f"titan_{e}") for e in cond['enemies_contain']])
            base_name = get_text(lang, "ar_enemies").format(enemies=enemies_str)
            
        if "require_fought" in cond:
            base_name += get_text(lang, "ar_req_fought_tag")
            
        return base_name

    def refresh_rules_list(self):
        lang = getattr(self.controller, 'current_lang', 'RU')
        for widget in self.rules_scroll.winfo_children():
            widget.destroy()
            
        self.rules_scroll.grid_columnconfigure(0, weight=1)
        
        rooms = ["earth", "water", "fire", "mix"]
        row_idx = 0
        
        for r_id in rooms:
            path = f"rules/{r_id}.yml"
            r_name = get_text(lang, f"elem_{r_id}")
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    rules = data.get("rules", [])
                    
                    for i, rule in enumerate(rules):
                        rule_name = self.generate_rule_name(rule, lang)
                        team = rule.get("team", [])
                        
                        if rule.get("action") == "skip":
                            action_text = get_text(lang, "ar_skip_room")
                        elif team == ["STOP"]:
                            action_text = get_text(lang, "ar_stop") 
                        else:
                            action_text = get_text(lang, "ar_change").format(count=len(team))
                        
                        lbl = ctk.CTkLabel(self.rules_scroll, text=f"[{r_name}] {rule_name} -> {action_text}", text_color="white")
                        lbl.grid(row=row_idx, column=0, padx=10, pady=5, sticky="w")
                        
                        btn_edit = ctk.CTkButton(self.rules_scroll, text="✏️", width=30, fg_color="#007bff", hover_color="#0056b3", command=lambda r=r_id, idx=i, d=rule: self.edit_rule(r, idx, d))
                        btn_edit.grid(row=row_idx, column=1, padx=(10, 2), pady=5, sticky="e")
                        
                        btn_del = ctk.CTkButton(self.rules_scroll, text="❌", width=30, fg_color="#dc3545", hover_color="#c82333", command=lambda r=r_id, idx=i: self.delete_rule(r, idx))
                        btn_del.grid(row=row_idx, column=2, padx=(2, 10), pady=5, sticky="e")
                        
                        row_idx += 1
                        
        if row_idx == 0:
            ctk.CTkLabel(self.rules_scroll, text=get_text(lang, "ar_no_rules"), text_color="gray").grid(row=0, column=0, padx=10, pady=10)

    def edit_rule(self, room_type, rule_index, rule_data):
        self.grab_release()
        
        def on_rule_saved(rule_name, r_type):
            self.after(100, self.grab_set)
            self.refresh_rules_list()
            
        RuleBuilderDialog(self, room_type, on_rule_saved, edit_index=rule_index, edit_data=rule_data)

    def delete_rule(self, room_type, rule_index):
        path = f"rules/{room_type}.yml"
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f: data = yaml.safe_load(f) or {}
            if "rules" in data and len(data["rules"]) > rule_index:
                del data["rules"][rule_index]
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                self.refresh_rules_list()

    def clear_all_rules(self):
        for r_id in ["earth", "water", "fire", "mix"]:
            path = f"rules/{r_id}.yml"
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f: data = yaml.safe_load(f) or {}
                if "rules" in data:
                    data["rules"] = []
                    with open(path, 'w', encoding='utf-8') as f:
                        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        self.refresh_rules_list()