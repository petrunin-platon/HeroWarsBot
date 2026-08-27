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

    def get_battle_decision(self, room_type, enemies, current_state=None):
        if current_state is None:
            current_state = {}

        room_data = self.rules_cache.get(room_type, {})
        rules = room_data.get("rules", [])
        
        # 1. ПЕРВЫЙ ПРОХОД: Правила спасения (отхил / нехватка энергии)
        for rule in rules:
            condition = rule.get("condition", {})
            if "titan_hp_below" in condition or "titan_energy_below" in condition:
                if self._evaluate_condition(condition, enemies, current_state):
                    team = rule.get("team", [])
                    reason = rule.get("name", "ПРИОРИТЕТ: Спасение")
                    delta = rule.get("allowed_delta")
                    special_ult = self._resolve_special_ult(team, rule)
                    return team, reason, delta, special_ult

        # 2. ВТОРОЙ ПРОХОД: Тактические правила под состав врагов
        for rule in rules:
            condition = rule.get("condition", {})
            if "enemies_contain" in condition and not ("titan_hp_below" in condition or "titan_energy_below" in condition):
                if self._evaluate_condition(condition, enemies, current_state):
                    team = rule.get("team", [])
                    reason = rule.get("name", "Тактическое правило")
                    delta = rule.get("allowed_delta")
                    special_ult = self._resolve_special_ult(team, rule)
                    return team, reason, delta, special_ult
                    
        # 3. Базовый пак по умолчанию
        default_team = room_data.get("default_team", [])
        special_ult = self._resolve_special_ult(default_team, {})
        return default_team, "Базовый пак", None, special_ult

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
            if not all(e in enemies for e in condition["enemies_contain"]):
                return False
                
        if "titan_hp_below" in condition:
            for titan, threshold in condition["titan_hp_below"].items():
                if current_state.get(titan, {}).get("hp", 100) >= threshold:
                    return False 
                    
        if "titan_energy_below" in condition:
            for titan, threshold in condition["titan_energy_below"].items():
                if current_state.get(titan, {}).get("energy", 100) >= threshold:
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
        
        # АНАЛИЗАТОР ОБУЧЕНИЯ: Решаем, какое условие прописать
        if before_state:
            # Ищем титанов, которые зашли в бой УЖЕ ранеными
            wounded = {t: hp for t, hp in before_state.items() if hp < 65}
            if wounded:
                # Находим самого раненого и привязываем правило спасения к нему
                worst_titan = min(wounded.items(), key=lambda x: x[1])[0]
                threshold = 65 
                new_rule["condition"] = {"titan_hp_below": {worst_titan: threshold}}
                new_rule["name"] = f"Авто-отхил ({worst_titan} < {threshold}%)"
                is_rescue = True

        if not is_rescue:
            # Если все были здоровы, значит проблема в тактике против конкретных врагов
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