import yaml
import os

class RulesEngine:
    def __init__(self):
        self.rules_cache = {}
        self.global_settings = {}
        self.global_thresholds = {}
        self.load_profile()
        self.load_rules()

    def load_profile(self):
        if os.path.exists("profile.yml"):
            with open("profile.yml", 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                self.global_settings = data.get("settings", {})
                self.global_thresholds = data.get("global_thresholds", {}) 

    def get_global_setting(self, key, default=None):
        self.load_profile()
        if key in self.global_thresholds:
            return self.global_thresholds[key]
        return self.global_settings.get(key, default)

    def load_rules(self):
        rooms = ["earth", "water", "fire", "mix"]
        for r in rooms:
            path = f"rules/{r}.yml"
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.rules_cache[r] = yaml.safe_load(f) or {}
            else:
                self.rules_cache[r] = {}

    def is_room_forbidden(self, room_type, current_state=None):
        """
        Проверяет, запрещен ли вход в эту комнату по состоянию здоровья титанов.
        Вызывается из combat.py на этапе выбора из двух дверей.
        """
        if current_state is None:
            current_state = {}
            
        room_data = self.rules_cache.get(room_type, {})
        rules = room_data.get("rules", [])
        
        for rule in rules:
            if rule.get("action") == "skip":
                condition = rule.get("condition", {})
                if self._evaluate_condition(condition, [], current_state):
                    return True
                    
        return False

    def _get_forbidden_titans(self, rules, enemies, current_state):
        """
        Собирает "Черный список" титанов для текущей комнаты на основе сработавших правил Skip.
        """
        forbidden = set()
        for rule in rules:
            if rule.get("action") == "skip":
                condition = rule.get("condition", {})
                if self._evaluate_condition(condition, enemies, current_state):
                    # Если сработал скип по ХП, добавляем этих титанов в Черный список
                    if "titan_hp_below" in condition:
                        forbidden.update(condition["titan_hp_below"].keys())
                    # Если сработал скип по Энергии
                    if "titan_energy_below" in condition:
                        forbidden.update(condition["titan_energy_below"].keys())
        return forbidden

    def get_battle_decision(self, room_type, enemies, current_state=None):
        """
        Вызывается, когда мы УЖЕ выбрали комнату и обязаны вернуть пак для боя.
        """
        if current_state is None:
            current_state = {}

        room_data = self.rules_cache.get(room_type, {})
        rules = room_data.get("rules", [])
        
        # 0. АБСОЛЮТНЫЙ ПРИОРИТЕТ: Формируем Черный список умирающих титанов
        forbidden_titans = self._get_forbidden_titans(rules, enemies, current_state)

        # 1. ПЕРВЫЙ ПРОХОД: Правила спасения (отхил / нехватка энергии)
        for rule in rules:
            if rule.get("action") == "skip":
                continue
                
            condition = rule.get("condition", {})
            if "titan_hp_below" in condition or "titan_energy_below" in condition:
                if self._evaluate_condition(condition, enemies, current_state):
                    team = rule.get("team", [])
                    
                    # ГЛОБАЛЬНОЕ ВЕТО: Если в целевом паке есть титан из Черного списка - отбраковываем пак!
                    if any(t in forbidden_titans for t in team):
                        continue
                        
                    reason = rule.get("name", "ПРИОРИТЕТ 1: Спасение")
                    delta = rule.get("allowed_delta")
                    special_ult = self._resolve_special_ult(team, rule)
                    return team, reason, delta, special_ult

        # 2. ВТОРОЙ ПРОХОД: Тактические правила под состав врагов (Золотые Правила)
        for rule in rules:
            if rule.get("action") == "skip":
                continue
                
            condition = rule.get("condition", {})
            if "enemies_contain" in condition and not ("titan_hp_below" in condition or "titan_energy_below" in condition):
                if self._evaluate_condition(condition, enemies, current_state):
                    team = rule.get("team", [])
                    
                    # ГЛОБАЛЬНОЕ ВЕТО: Запрет на умирающих титанов работает и здесь
                    if any(t in forbidden_titans for t in team):
                        continue
                        
                    reason = rule.get("name", "ПРИОРИТЕТ 2: Тактика")
                    delta = rule.get("allowed_delta")
                    special_ult = self._resolve_special_ult(team, rule)
                    return team, reason, delta, special_ult
                    
        # 3. ПРИОРИТЕТ 3: Базовый пак по умолчанию
        default_team = room_data.get("default_team", [])
        
        # Защита от самоубийства: если даже Дефолтный пак требует титанов из Черного списка
        if default_team and any(t in forbidden_titans for t in default_team):
            bad_titans = ", ".join([t.upper() for t in forbidden_titans if t in default_team])
            reason = f"ФАТАЛЬНО: Все паки отбракованы. Дефолтный пак содержит запрещенных титанов ({bad_titans})"
            # Возвращаем STOP, main.py поставит бота на паузу.
            return ["STOP"], reason, None, "auto"
            
        special_ult = self._resolve_special_ult(default_team, {})
        return default_team, "ПРИОРИТЕТ 3: Базовый пак", None, special_ult

    def _resolve_special_ult(self, team, rule):
        if rule.get("special_ult"):
            return rule.get("special_ult")
        
        manual_angus = self.get_global_setting("angus_manual_control", False)
        if manual_angus and "angus" in team:
            return "angus"
            
        return "auto"

    def _evaluate_condition(self, condition, enemies, current_state):
        if not condition: 
            return False
            
        if "enemies_contain" in condition:
            if not enemies or not all(e in enemies for e in condition["enemies_contain"]):
                return False
                
        if "titan_hp_below" in condition:
            for titan, threshold in condition["titan_hp_below"].items():
                if current_state.get(titan, {}).get("hp", 100) >= threshold:
                    return False 
                    
        if "titan_energy_below" in condition:
            for titan, threshold in condition["titan_energy_below"].items():
                if current_state.get(titan, {}).get("energy", 100) >= threshold:
                    return False
                    
        # ПРОВЕРКА НА ОБКАТКУ (Не пускаем в бой не заряженных титанов)
        if "require_fought" in condition:
            for titan in condition["require_fought"]:
                if titan not in current_state:
                    return False
                    
        return True

    def learn_new_rule(self, room_type, enemies, team, custom_delta=None, before_state=None):
        """Интеллектуальное создание правила с анализом причин провала"""
        path = f"rules/{room_type}.yml"
        data = {"default_team": [], "rules": []}
        
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if loaded and isinstance(loaded, dict):
                    data = loaded
                    
        if "rules" not in data or not isinstance(data["rules"], list):
            data["rules"] = []
            
        new_rule = {
            "team": team,
            "stats": {"wins": 0, "fails": 0}
        }

        is_rescue = False
        
        if before_state:
            # Находим всех раненых титанов
            wounded = {t: hp for t, hp in before_state.items() if hp < 65}
            if wounded:
                # Находим самого пострадавшего
                worst_titan = min(wounded.items(), key=lambda x: x[1])[0]
                
                # КРИТИЧЕСКИЙ ФИКС: Является ли это правилом отхила?
                # Только если этот самый раненый титан ПРИСУТСТВУЕТ в новом паке!
                if worst_titan in team:
                    threshold = 65 
                    new_rule["condition"] = {"titan_hp_below": {worst_titan: threshold}}
                    new_rule["name"] = f"Авто-отхил ({worst_titan} < {threshold}%)"
                    is_rescue = True

        # Если это не спасательная операция (или раненого титана убрали из пака)
        # значит, это тактический Анти-пак против конкретных врагов.
        if not is_rescue:
            new_rule["condition"] = {"enemies_contain": enemies}
            new_rule["name"] = f"Анти-пак (Тактика) - {len(data['rules']) + 1}"
        
        if custom_delta is not None:
            new_rule["allowed_delta"] = custom_delta
            
        if "angus" in team:
            new_rule["special_ult"] = "angus"
            
        data["rules"].insert(0, new_rule)
        
        os.makedirs("rules", exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
            
        self.rules_cache[room_type] = data
        print(f"[ОБУЧЕНИЕ] Новое правило '{new_rule['name']}' сохранено на 1-е место!")

engine = RulesEngine()