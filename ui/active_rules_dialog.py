import customtkinter as ctk
import os
import yaml
import copy
from i18n import get_text
from ui.rule_builder_dialog import RuleBuilderDialog

class ActiveRulesDialog(ctk.CTkToplevel):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        lang = getattr(self.controller, 'current_lang', 'RU')
        
        self.title(get_text(lang, "ar_title"))
        self.geometry("950x550") 
        self.resizable(False, False)
        self.transient(master)
        
        self.after(100, self.grab_set)

        self.draft_rules = {"earth": [], "water": [], "fire": [], "mix": []}
        self.load_draft_from_disk()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        ctk.CTkLabel(header_frame, text=get_text(lang, "ar_list"), font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        self.tab_keys = ["all", "earth", "water", "fire", "mix"]
        self.tab_names = {
            "all": get_text(lang, "ar_tab_all"),
            "earth": get_text(lang, "elem_earth"),
            "water": get_text(lang, "elem_water"),
            "fire": get_text(lang, "elem_fire"),
            "mix": get_text(lang, "elem_mix")
        }
        
        self.current_tab = ctk.StringVar(value=self.tab_names["all"])
        self.segment = ctk.CTkSegmentedButton(
            self, 
            values=[self.tab_names[k] for k in self.tab_keys],
            variable=self.current_tab,
            command=self.on_tab_change
        )
        self.segment.grid(row=1, column=0, sticky="ew", padx=20, pady=5)

        self.rules_scroll = ctk.CTkScrollableFrame(self, fg_color="#1e1e1e")
        self.rules_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 15))
        footer.grid_columnconfigure((0, 1), weight=1)

        # Вызовы локализации для кнопок (смайлики можно склеивать с переводом)
        self.btn_save = ctk.CTkButton(footer, text="💾 " + get_text(lang, "ar_btn_save_draft"), fg_color="#28a745", hover_color="#218838", command=self.save_changes)
        self.btn_save.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.btn_clear_all = ctk.CTkButton(footer, text="🗑 " + get_text(lang, "ar_btn_clear_draft"), fg_color="#dc3545", hover_color="#c82333", command=self.clear_all_rules)
        self.btn_clear_all.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.refresh_rules_list()

    def load_draft_from_disk(self):
        for r_id in self.draft_rules.keys():
            path = f"rules/{r_id}.yml"
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                        self.draft_rules[r_id] = data.get("rules", [])
                except (yaml.YAMLError, Exception):
                    pass 

    def on_tab_change(self, selected_name):
        self.refresh_rules_list()

    def get_rule_badge(self, rule, lang):
        """Возвращает локализованный префикс (Бейдж) на основе логики правила"""
        cond = rule.get("condition", {})
        action = rule.get("action", "")
        team = rule.get("team", [])
        
        if action == "skip" or team == ["STOP"]:
            return get_text(lang, "badge_skip")
        elif "titan_hp_below" in cond or "titan_energy_below" in cond:
            return get_text(lang, "badge_heal")
        elif "enemies_contain" in cond:
            return get_text(lang, "badge_antipack")
        return get_text(lang, "badge_gear")

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
        
        active_tab_name = self.current_tab.get()
        active_key = "all"
        for k, v in self.tab_names.items():
            if v == active_tab_name:
                active_key = k
                break
                
        rooms_to_render = ["earth", "water", "fire", "mix"] if active_key == "all" else [active_key]
        row_idx = 0
        
        for r_id in rooms_to_render:
            r_name = get_text(lang, f"elem_{r_id}")
            rules = self.draft_rules[r_id]
            
            for i, rule in enumerate(rules):
                badge = self.get_rule_badge(rule, lang)
                rule_name = self.generate_rule_name(rule, lang)
                team = rule.get("team", [])
                
                if rule.get("action") == "skip":
                    action_text = get_text(lang, "ar_skip_room")
                elif team == ["STOP"]:
                    action_text = get_text(lang, "ar_stop") 
                else:
                    action_text = get_text(lang, "ar_change").format(count=len(team))
                
                lbl_text = f"[{r_name}] {badge}{rule_name} -> {action_text}"
                lbl = ctk.CTkLabel(self.rules_scroll, text=lbl_text, text_color="white")
                lbl.grid(row=row_idx, column=0, padx=10, pady=5, sticky="w")
                
                col_idx = 1
                
                if active_key != "all":
                    btn_up = ctk.CTkButton(self.rules_scroll, text="⬆️", width=30, fg_color="#6c757d", hover_color="#5a6268", command=lambda r=r_id, idx=i: self.move_rule_up(r, idx))
                    btn_up.grid(row=row_idx, column=col_idx, padx=2, pady=5)
                    if i == 0: btn_up.configure(state="disabled")
                    col_idx += 1
                    
                    btn_down = ctk.CTkButton(self.rules_scroll, text="⬇️", width=30, fg_color="#6c757d", hover_color="#5a6268", command=lambda r=r_id, idx=i: self.move_rule_down(r, idx))
                    btn_down.grid(row=row_idx, column=col_idx, padx=2, pady=5)
                    if i == len(rules) - 1: btn_down.configure(state="disabled")
                    col_idx += 1

                btn_edit = ctk.CTkButton(self.rules_scroll, text="✏️", width=30, fg_color="#007bff", hover_color="#0056b3", command=lambda r=r_id, idx=i, d=rule: self.edit_rule(r, idx, d))
                btn_edit.grid(row=row_idx, column=col_idx, padx=(10, 2), pady=5, sticky="e")
                col_idx += 1
                
                btn_del = ctk.CTkButton(self.rules_scroll, text="❌", width=30, fg_color="#dc3545", hover_color="#c82333", command=lambda r=r_id, idx=i: self.delete_rule(r, idx))
                btn_del.grid(row=row_idx, column=col_idx, padx=(2, 10), pady=5, sticky="e")
                
                row_idx += 1
                        
        if row_idx == 0:
            ctk.CTkLabel(self.rules_scroll, text=get_text(lang, "ar_no_rules"), text_color="gray").grid(row=0, column=0, padx=10, pady=10)

    def move_rule_up(self, room_type, idx):
        if idx > 0:
            rules = self.draft_rules[room_type]
            rules[idx], rules[idx-1] = rules[idx-1], rules[idx]
            self.refresh_rules_list()

    def move_rule_down(self, room_type, idx):
        rules = self.draft_rules[room_type]
        if idx < len(rules) - 1:
            rules[idx], rules[idx+1] = rules[idx+1], rules[idx]
            self.refresh_rules_list()

    def delete_rule(self, room_type, idx):
        del self.draft_rules[room_type][idx]
        self.refresh_rules_list()

    def clear_all_rules(self):
        self.draft_rules = {"earth": [], "water": [], "fire": [], "mix": []}
        self.refresh_rules_list()

    def edit_rule(self, room_type, rule_index, rule_data):
        self.grab_release()
        
        def on_rule_saved_draft(rule_obj, r_type, edit_idx=None):
            self.after(100, self.grab_set)
            if edit_idx is not None:
                self.draft_rules[r_type][edit_idx] = rule_obj
            else:
                self.draft_rules[r_type].insert(0, rule_obj)
            self.refresh_rules_list()
            
        RuleBuilderDialog(self, room_type, on_rule_saved_draft, edit_index=rule_index, edit_data=copy.deepcopy(rule_data), draft_mode=True)

    def save_changes(self):
        for r_id, rules_list in self.draft_rules.items():
            path = f"rules/{r_id}.yml"
            data = {"rules": []}
            
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        old_data = yaml.safe_load(f) or {}
                        if "default_team" in old_data:
                            data["default_team"] = old_data["default_team"]
                except Exception:
                    pass
            
            data["rules"] = rules_list
            
            temp_path = f"{path}.tmp"
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            os.replace(temp_path, path)
            
        lang = getattr(self.controller, 'current_lang', 'RU')
        msg = get_text(lang, "ar_saved_msg")
        if hasattr(self.controller, 'frames') and "dash" in self.controller.frames:
            self.controller.frames["dash"].append_log(msg)
            
        self.grab_release()
        self.destroy()