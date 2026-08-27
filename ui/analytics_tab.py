# ui/analytics_tab.py
import customtkinter as ctk
import tkinter as tk
import os
import json
import glob
import yaml
from collections import defaultdict
from i18n import get_text

class AnalyticsFrame(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, corner_radius=10, fg_color="transparent", **kwargs)
        self.controller = controller
        self.golden_rules = []
        
        self.total_battles_count = 0
        self.winrate_val = 0.0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(15, 10), padx=5)
        self.lbl_title = ctk.CTkLabel(header_frame, text="", font=ctk.CTkFont(size=24, weight="bold"))
        self.lbl_title.pack(side="left")
        
        self.stats_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=8)
        self.stats_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 10))
        
        self.lbl_total_battles = ctk.CTkLabel(self.stats_frame, text="", font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_total_battles.pack(side="left", padx=20, pady=15)
        
        self.lbl_winrate = ctk.CTkLabel(self.stats_frame, text="", font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_winrate.pack(side="left", padx=20, pady=15)
        
        self.lbl_golden = ctk.CTkLabel(self.stats_frame, text="", font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffc107")
        self.lbl_golden.pack(side="right", padx=20, pady=15)
        
        self.report_box = ctk.CTkTextbox(self, font=("Consolas", 13), wrap="word", fg_color="#2b2b2b", text_color="white")
        self.report_box.grid(row=2, column=0, sticky="nsew", padx=5, pady=(0, 10))
        
        self.setup_readonly_and_menu(self.report_box)
        self.report_box.insert("end", "[СИСТЕМА] Интерфейс загружен...\n")
        
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 15))
        
        self.btn_run = ctk.CTkButton(footer_frame, text="", height=40, font=ctk.CTkFont(weight="bold"), command=self.run_analysis)
        self.btn_run.pack(side="left", padx=(0, 10))
        
        self.btn_apply = ctk.CTkButton(footer_frame, text="", height=40, font=ctk.CTkFont(weight="bold"), fg_color="#28a745", hover_color="#218838", state="disabled", command=self.apply_golden_rules)
        self.btn_apply.pack(side="left")

    def setup_readonly_and_menu(self, textbox):
        def prevent_edit(event):
            if event.state & 0x0004 or event.state & 0x0008:
                if event.keysym.lower() in ['c', 'a']:
                    return None
            if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End']:
                return None
            return "break"
            
        textbox.bind("<Key>", prevent_edit)
        textbox.bind("<<Paste>>", lambda e: "break")
        textbox.bind("<<Cut>>", lambda e: "break")

        self.context_menu = tk.Menu(self, tearoff=False, bg="#2b2b2b", fg="white", activebackground="#007bff")
        lang = getattr(self.controller, 'current_lang', 'RU')
        self.context_menu.add_command(label=get_text(lang, "ctx_copy"), command=lambda: self.copy_text(textbox))

        textbox.bind("<Button-3>", lambda event: self.show_context_menu(event, textbox))

    def show_context_menu(self, event, textbox):
        try:
            if textbox.get(tk.SEL_FIRST, tk.SEL_LAST):
                self.context_menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            pass

    def copy_text(self, textbox):
        try:
            selected_text = textbox.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.clipboard_clear()
            self.clipboard_append(selected_text)
        except tk.TclError:
            pass

    def update_language(self, lang):
        self.lbl_title.configure(text=get_text(lang, "analytics_title"))
        self.lbl_total_battles.configure(text=f"{get_text(lang, 'analytics_lbl_total')}{self.total_battles_count}")
        self.lbl_winrate.configure(text=f"{get_text(lang, 'analytics_lbl_winrate')}{self.winrate_val:.1f}%")
        self.lbl_golden.configure(text=f"{get_text(lang, 'analytics_lbl_golden')}{len(self.golden_rules)}")
        self.btn_run.configure(text=get_text(lang, "analytics_btn_run"))
        self.btn_apply.configure(text=get_text(lang, "analytics_btn_apply"))
        
        self.context_menu.entryconfigure(0, label=get_text(lang, "ctx_copy"))

    def append_text(self, text):
        self.report_box.insert("end", text + "\n")
        self.report_box.see("end")

    def run_analysis(self):
        lang = getattr(self.controller, 'current_lang', 'RU')
        self.report_box.delete("1.0", "end")
        self.golden_rules = []
        
        if not os.path.exists("logs"):
            err_msg = "[ОШИБКА] Папка logs/ не найдена. Проведите несколько боев!" if lang == "RU" else "[ERROR] logs/ folder not found. Run some battles!"
            self.append_text(err_msg)
            return

        files = glob.glob("logs/*.jsonl")
        if not files:
            err_msg = "[ОШИБКА] Файлы логов (*.jsonl) не найдены. Проведите несколько боев!" if lang == "RU" else "[ERROR] Log files (*.jsonl) not found. Run some battles!"
            self.append_text(err_msg)
            return
            
        logs = []
        for file in files:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                            
        load_msg = f"📁 Загружена история: {len(logs)} записей боев из {len(files)} лог-файлов.\n" if lang == "RU" else f"📁 History loaded: {len(logs)} battle records from {len(files)} log files.\n"
        self.append_text(load_msg)
        
        stats = defaultdict(lambda: defaultdict(lambda: {"attempts": 0, "wins": 0, "avg_hp": []}))
        total_battles = 0
        total_wins = 0
        
        for entry in logs:
            room = entry.get("room")
            if not room or room == "unknown": continue
            
            enemies = tuple(sorted(entry.get("enemies", [])))
            team = tuple(sorted(entry.get("team", [])))
            action = entry.get("action")
            
            if not enemies or not team or action not in ["SUCCESS", "ROLLBACK"]: continue
            
            total_battles += 1
            scenario_key = (room, enemies)
            stats[scenario_key][team]["attempts"] += 1
            
            if action == "SUCCESS":
                total_wins += 1
                stats[scenario_key][team]["wins"] += 1
                hp_status = entry.get("hp_status", {})
                hp_list = [v.get("hp", 0) for k, v in hp_status.items() if k in team and isinstance(v, dict)]
                if hp_list:
                    stats[scenario_key][team]["avg_hp"].append(sum(hp_list) / len(hp_list))
                    
        overall_wr = (total_wins / total_battles * 100) if total_battles > 0 else 0
        self.total_battles_count = total_battles
        self.winrate_val = overall_wr
        
        self.update_language(lang)
        
        self.append_text("="*70)
        title_msg = "📊 АНАЛИТИЧЕСКИЙ ОТЧЕТ ПО ВИНРЕЙТАМ" if lang == "RU" else "📊 WINRATE ANALYTICS REPORT"
        self.append_text(title_msg)
        self.append_text("="*70)
        
        for (room, enemies), teams_data in stats.items():
            enemies_str = ", ".join([get_text(lang, f"titan_{e}") for e in enemies])
            room_name = get_text(lang, f"elem_{room}")
            
            self.append_text(f"\n🚪 {room_name.upper()}")
            enemies_lbl = get_text(lang, "ar_enemies").split(":")[0] 
            self.append_text(f"⚔️ {enemies_lbl}: {enemies_str}")
            self.append_text("-" * 60)
            
            sorted_teams = sorted(
                teams_data.items(), 
                key=lambda x: (x[1]["wins"] / x[1]["attempts"] if x[1]["attempts"] > 0 else 0, x[1]["attempts"]), 
                reverse=True
            )
            
            for team, data in sorted_teams:
                attempts = data["attempts"]
                wins = data["wins"]
                winrate = (wins / attempts) * 100
                avg_hp_arr = data["avg_hp"]
                avg_hp_val = sum(avg_hp_arr) / len(avg_hp_arr) if avg_hp_arr else 0
                
                team_str = ", ".join([get_text(lang, f"titan_{t}") for t in team])
                
                # ИНТЕЛЛЕКТУАЛЬНАЯ ПРОВЕРКА: Есть ли уже это правило в Базе Знаний?
                is_implemented = False
                if winrate >= 80:
                    path = f"rules/{room}.yml"
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            yml_data = yaml.safe_load(f) or {}
                            for rule in yml_data.get("rules", []):
                                cond = rule.get("condition", {})
                                if "enemies_contain" in cond and sorted(cond["enemies_contain"]) == sorted(enemies):
                                    if sorted(rule.get("team", [])) == sorted(team):
                                        is_implemented = True
                                        break
                
                if winrate >= 80:
                    if is_implemented:
                        wr_color = "🔵 В БАЗЕ" if lang == "RU" else "🔵 IN KB"
                    else:
                        wr_color = "🟢 ИДЕАЛЬНО" if lang == "RU" else "🟢 PERFECT"
                elif winrate >= 50:
                    wr_color = "🟡 СРЕДНЕ" if lang == "RU" else "🟡 AVERAGE"
                else:
                    wr_color = "🔴 ОПАСНО" if lang == "RU" else "🔴 DANGER"
                    
                pack_lbl = "Пак" if lang == "RU" else "Team"
                winrate_lbl = "Винрейт" if lang == "RU" else "Winrate"
                hp_lbl = "Ср. ХП после боя" if lang == "RU" else "Avg HP left"
                
                self.append_text(f"  {wr_color} | {pack_lbl}: {team_str}")
                self.append_text(f"     {winrate_lbl}: {winrate:.1f}% ({wins}/{attempts}) | {hp_lbl}: {avg_hp_val:.1f}%")
                
                # Добавляем в кандидаты ТОЛЬКО если правила еще нет в YAML
                if winrate >= 80 and attempts >= 5 and not is_implemented:
                    self.golden_rules.append({
                        "room": room,
                        "enemies": list(enemies),
                        "team": list(team),
                        "winrate": winrate,
                        "avg_hp": avg_hp_val
                    })
                    
        self.update_language(lang)
        
        if self.golden_rules:
            self.btn_apply.configure(state="normal")
            msg = f"\n[АЛГОРИТМ] 🤖 Найдено {len(self.golden_rules)} новых идеальных связок! Готов к внедрению в базу знаний." if lang == "RU" else f"\n[ALGORITHM] 🤖 Found {len(self.golden_rules)} new perfect counter-packs! Ready to deploy to Knowledge Base."
            self.append_text(msg)
        else:
            self.btn_apply.configure(state="disabled")
            msg = "\n[АЛГОРИТМ] 🤖 Новых идеальных связок пока не найдено. Фармите дальше!" if lang == "RU" else "\n[ALGORITHM] 🤖 New perfect matches not found yet. Keep farming!"
            self.append_text(msg)

    def apply_golden_rules(self):
        if not self.golden_rules: return
        
        lang = getattr(self.controller, 'current_lang', 'RU')
        applied_count = 0
        
        for rule in self.golden_rules:
            room = rule["room"]
            path = f"rules/{room}.yml"
            data = {"rules": [], "default_team": []}
            
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {"rules": [], "default_team": []}
            
            if "rules" not in data or data["rules"] is None:
                data["rules"] = []
                
            rule_exists = False
            for existing_rule in data["rules"]:
                cond = existing_rule.get("condition", {})
                if "enemies_contain" in cond:
                    if sorted(cond["enemies_contain"]) == sorted(rule["enemies"]):
                        rule_exists = True
                        if sorted(existing_rule.get("team", [])) != sorted(rule["team"]):
                            enemies_str = ", ".join([get_text(lang, f"titan_{e}") for e in rule['enemies']])
                            msg = f"  [ОБНОВЛЕНИЕ] В {room}.yml улучшен пак против [{enemies_str}]" if lang == "RU" else f"  [UPDATE] In {room}.yml improved pack against [{enemies_str}]"
                            self.append_text(msg)
                            
                            existing_rule["team"] = rule["team"]
                            existing_rule["name"] = f"AI: Анти-пак (Винрейт: {rule['winrate']:.0f}%, ХП: {rule['avg_hp']:.0f}%)"
                            applied_count += 1
                        break
                        
            if not rule_exists:
                enemies_str = ", ".join([get_text(lang, f"titan_{e}") for e in rule['enemies']])
                msg = f"  [СОЗДАНИЕ] В {room}.yml добавлена новая тактика против [{enemies_str}]" if lang == "RU" else f"  [CREATE] In {room}.yml added new tactics against [{enemies_str}]"
                self.append_text(msg)
                
                new_rule = {
                    "name": f"AI: Анти-пак (Винрейт: {rule['winrate']:.0f}%, ХП: {rule['avg_hp']:.0f}%)",
                    "condition": {"enemies_contain": rule["enemies"]},
                    "team": rule["team"]
                }
                if "angus" in rule["team"]: new_rule["special_ult"] = "angus"
                data["rules"].insert(0, new_rule) 
                applied_count += 1
                
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                
        success_msg = f"\n[УСПЕХ] ✅ База Знаний (Rules Engine) успешно обновлена. Внедрено правил: {applied_count}." if lang == "RU" else f"\n[SUCCESS] ✅ Knowledge Base (Rules Engine) updated. Rules applied: {applied_count}."
        self.append_text(success_msg)
        self.btn_apply.configure(state="disabled")
        self.golden_rules = []