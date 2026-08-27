import customtkinter as ctk
import os
import json
import glob
import yaml
from collections import defaultdict

EN_TO_RU = {
    "hyperion": "Гиперион", "sigurd": "Сигурд", "tidus": "Тидус", "nova": "Нова", "mairi": "Маири", "orm": "Орм",
    "angus": "Ангус", "avalon": "Авалон", "eden": "Эдем", "silva": "Сильва", "verdok": "Вердок", "pallant": "Паллант",
    "araji": "Араджи", "ignis": "Игнис", "acheron": "Ашерон", "vulcan": "Вулкан", "moloch": "Молох", "alecto": "Алекто",
    "rigel": "Ригель", "iyari": "Ияри", "lumira": "Люмира", "solaris": "Солярис", "amon": "Амон",
    "mor": "Мор", "tenebris": "Тенебрис", "brustar": "Брустар", "umbra": "Умбра", "keros": "Керос"
}

class AnalyticsFrame(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, corner_radius=10, fg_color="transparent", **kwargs)
        self.controller = controller
        self.golden_rules = []
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Терминал отчета тянется вниз
        
        # --- ЗАГОЛОВОК ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(15, 10), padx=5)
        ctk.CTkLabel(header_frame, text="Аналитика и Машинное обучение", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        
        # --- ПАНЕЛЬ СТАТИСТИКИ (КАРТОЧКИ) ---
        self.stats_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=8)
        self.stats_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 10))
        
        self.lbl_total_battles = ctk.CTkLabel(self.stats_frame, text="Всего боев (лог): 0", font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_total_battles.pack(side="left", padx=20, pady=15)
        
        self.lbl_winrate = ctk.CTkLabel(self.stats_frame, text="Средний Winrate: 0%", font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_winrate.pack(side="left", padx=20, pady=15)
        
        self.lbl_golden = ctk.CTkLabel(self.stats_frame, text="Найдено 'Золотых правил': 0", font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffc107")
        self.lbl_golden.pack(side="right", padx=20, pady=15)
        
        # --- ТЕРМИНАЛ ОТЧЕТА ---
        self.report_box = ctk.CTkTextbox(self, font=("Consolas", 13), wrap="word", fg_color="#2b2b2b", text_color="white")
        self.report_box.grid(row=2, column=0, sticky="nsew", padx=5, pady=(0, 10))
        self.report_box.insert("end", "Нажмите 'Запустить анализ логов', чтобы обработать всю историю боев (logs/*.jsonl)...\n")
        self.report_box.configure(state="disabled")
        
        # --- КНОПКИ УПРАВЛЕНИЯ ---
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 15))
        
        ctk.CTkButton(footer_frame, text="📊 Запустить анализ логов", height=40, font=ctk.CTkFont(weight="bold"), command=self.run_analysis).pack(side="left", padx=(0, 10))
        
        self.btn_apply = ctk.CTkButton(footer_frame, text="✨ Внедрить Золотые Правила", height=40, font=ctk.CTkFont(weight="bold"), fg_color="#28a745", hover_color="#218838", state="disabled", command=self.apply_golden_rules)
        self.btn_apply.pack(side="left")

    def append_text(self, text):
        self.report_box.configure(state="normal")
        self.report_box.insert("end", text + "\n")
        self.report_box.see("end")
        self.report_box.configure(state="disabled")

    def run_analysis(self):
        self.report_box.configure(state="normal")
        self.report_box.delete("1.0", "end")
        self.report_box.configure(state="disabled")
        self.golden_rules = []
        
        if not os.path.exists("logs"):
            self.append_text("[ОШИБКА] Папка logs/ не найдена. Проведите несколько боев!")
            return

        files = glob.glob("logs/*.jsonl")
        if not files:
            self.append_text("[ОШИБКА] Файлы логов (*.jsonl) не найдены в папке logs/. Проведите несколько боев!")
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
                            
        self.append_text(f"📁 Загружена история: {len(logs)} записей боев из {len(files)} лог-файлов.\n")
        
        # Словарь: Комната -> Враги -> Наш Пак -> {попытки, победы, ХП}
        stats = defaultdict(lambda: defaultdict(lambda: {"attempts": 0, "wins": 0, "avg_hp": []}))
        total_battles = 0
        total_wins = 0
        
        # 1. Парсинг и группировка
        for entry in logs:
            room = entry.get("room")
            if not room or room == "unknown": continue
            
            # Сортируем списки, чтобы идентичные паки не дублировались из-за разного порядка
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
                    
        # Обновление дашборда
        overall_wr = (total_wins / total_battles * 100) if total_battles > 0 else 0
        self.lbl_total_battles.configure(text=f"Всего боев (лог): {total_battles}")
        self.lbl_winrate.configure(text=f"Средний Winrate: {overall_wr:.1f}%")
        
        self.append_text("="*70)
        self.append_text("📊 АНАЛИТИЧЕСКИЙ ОТЧЕТ ПО ВИНРЕЙТАМ")
        self.append_text("="*70)
        
        # 2. Вывод результатов
        for (room, enemies), teams_data in stats.items():
            enemies_ru = ", ".join([EN_TO_RU.get(e, e) for e in enemies])
            self.append_text(f"\n🚪 КОМНАТА: {room.upper()}")
            self.append_text(f"⚔️ Враги: {enemies_ru}")
            self.append_text("-" * 60)
            
            # Сортировка: сначала по винрейту, затем по кол-ву попыток
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
                team_ru = ", ".join([EN_TO_RU.get(t, t) for t in team])
                
                # Аналитика цвета
                if winrate >= 80:
                    wr_color = "🟢 ИДЕАЛЬНО"
                elif winrate >= 50:
                    wr_color = "🟡 СРЕДНЕ"
                else:
                    wr_color = "🔴 ОПАСНО"
                    
                self.append_text(f"  {wr_color} | Пак: {team_ru}")
                self.append_text(f"     Винрейт: {winrate:.1f}% ({wins}/{attempts} побед) | Ср. ХП после боя: {avg_hp_val:.1f}%")
                
                # Добавление в список Золотых Правил (Винрейт >= 80% и хотя бы 2 боя)
                if winrate >= 80 and attempts >= 2:
                    self.golden_rules.append({
                        "room": room,
                        "enemies": list(enemies),
                        "team": list(team),
                        "winrate": winrate,
                        "avg_hp": avg_hp_val
                    })
                    
        self.lbl_golden.configure(text=f"Найдено 'Золотых правил': {len(self.golden_rules)}")
        
        # 3. Активация кнопки внедрения
        if self.golden_rules:
            self.btn_apply.configure(state="normal")
            self.append_text(f"\n[АЛГОРИТМ] 🤖 Найдено {len(self.golden_rules)} идеальных контр-паков! Готов к внедрению в базу знаний.")
        else:
            self.btn_apply.configure(state="disabled")
            self.append_text("\n[АЛГОРИТМ] 🤖 Идеальных связок пока не найдено (нужно >=80% винрейт и мин. 2 боя). Фармите дальше!")

    def apply_golden_rules(self):
        if not self.golden_rules: return
        
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
                    # Если правило против таких врагов уже есть
                    if sorted(cond["enemies_contain"]) == sorted(rule["enemies"]):
                        rule_exists = True
                        # Обновляем, если новый пак отличается от старого
                        if sorted(existing_rule.get("team", [])) != sorted(rule["team"]):
                            self.append_text(f"  [ОБНОВЛЕНИЕ] В {room}.yml улучшен пак против {rule['enemies']}")
                            existing_rule["team"] = rule["team"]
                            existing_rule["name"] = f"AI: Анти-пак (Винрейт: {rule['winrate']:.0f}%, ХП: {rule['avg_hp']:.0f}%)"
                            applied_count += 1
                        break
                        
            # Если такого правила еще не было - создаем новое
            if not rule_exists:
                self.append_text(f"  [СОЗДАНИЕ] В {room}.yml добавлена новая тактика против {rule['enemies']}")
                new_rule = {
                    "name": f"AI: Анти-пак (Винрейт: {rule['winrate']:.0f}%, ХП: {rule['avg_hp']:.0f}%)",
                    "condition": {"enemies_contain": rule["enemies"]},
                    "team": rule["team"]
                }
                # Подхватываем логику Ангуса
                if "angus" in rule["team"]: new_rule["special_ult"] = "angus"
                data["rules"].insert(0, new_rule) # Вставляем в самый верх (Приоритет!)
                applied_count += 1
                
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                
        self.append_text(f"\n[УСПЕХ] ✅ База Знаний (Rules Engine) успешно обновлена. Внедрено правил: {applied_count}.")
        self.btn_apply.configure(state="disabled")
        self.golden_rules = []