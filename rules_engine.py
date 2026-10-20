import yaml
import os
import data_paths
from i18n import get_text

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
        if key in self.global_thresholds:
            return self.global_thresholds[key]
        return self.global_settings.get(key, default)

    def load_rules(self):
        rooms = ["earth", "water", "fire", "mix"]
        for r in rooms:
            path = data_paths.rules_path(r)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.rules_cache[r] = yaml.safe_load(f) or {}
                drop_obsolete_rules(path, self.rules_cache[r])
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
        Возвращает (пак, причина, свой допуск потерь, стратегия ульты).
        """
        d = self.battle_decision(room_type, enemies, current_state)
        return d["team"], d["reason"], d["delta"], d["special_ult"]

    def forbidden_titans(self, room_type, enemies, current_state=None):
        """Чёрный список титанов комнаты: правила skip, которые сейчас срабатывают."""
        rules = self.rules_cache.get(room_type, {}).get("rules", [])
        return self._get_forbidden_titans(rules, enemies, current_state or {})

    def battle_decision(self, room_type, enemies, current_state=None):
        """
        То же, что get_battle_decision, но словарём: team, reason, delta, special_ult и
        condition — условие правила, которое дало пак ({} для базового пака).
        Условие нужно, чтобы после отката запомнить правило для той же ситуации.
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
                    return self._decision(team, reason, rule)

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
                    return self._decision(team, reason, rule)
                    
        # 3. ПРИОРИТЕТ 3: Базовый пак по умолчанию
        default_team = room_data.get("default_team", [])
        
        # Защита от самоубийства: если даже Дефолтный пак требует титанов из Черного списка
        if default_team and any(t in forbidden_titans for t in default_team):
            bad_titans = ", ".join([t.upper() for t in forbidden_titans if t in default_team])
            reason = f"ФАТАЛЬНО: Все паки отбракованы. Дефолтный пак содержит запрещенных титанов ({bad_titans})"
            # Возвращаем STOP, main.py поставит бота на паузу.
            return {"team": ["STOP"], "reason": reason, "delta": None, "special_ult": "auto", "condition": {}}

        return self._decision(default_team, "ПРИОРИТЕТ 3: Базовый пак", {})

    def _decision(self, team, reason, rule):
        return {
            "team": team,
            "reason": reason,
            "delta": rule.get("allowed_delta"),
            "special_ult": self._resolve_special_ult(team, rule),
            "condition": dict(rule.get("condition") or {}),
        }

    def room_packs(self, room_type):
        """Все паки из правил стихии и базовый пак, по порядку файла: [(пак, условие правила)].
        Правила skip и [STOP] не входят. Нужно для выбора запасного пака (tactics.py)."""
        room_data = self.rules_cache.get(room_type, {})
        packs = []
        for rule in room_data.get("rules", []) or []:
            team = rule.get("team") or []
            if rule.get("action") == "skip" or not team or team == ["STOP"]:
                continue
            packs.append((list(team), dict(rule.get("condition") or {})))
        default_team = room_data.get("default_team") or []
        if default_team:
            packs.append((list(default_team), {}))
        return packs

    def all_packs(self):
        """Паки из правил и базовые паки всех стихий (без skip и [STOP]). Из них tactics.own_titans узнаёт,
        каких титанов вы сами где-то указали (сессия 08)."""
        return [pack for room in self.rules_cache for pack, _ in self.room_packs(room)]

    def base_packs(self):
        """Базовые паки всех стихий: {стихия: пак}. По ним бот видит, где титана лечат в своей комнате (задача 9в)."""
        return {room: list(data.get("default_team") or []) for room, data in self.rules_cache.items()
                if isinstance(data, dict)}

    def heal_rule_for(self, room_type, current_state, healers):
        """Правило отхила, которое сработает за дверью этой стихии (задача 9б, выбор двери): условие по ХП
        без привязки к врагам выполняется, а в паке есть и раненые титаны условия, и лекарь (healers).
        Возвращает название правила или "". Правила с врагами не берутся: врагов за дверью бот ещё не видел."""
        rules = self.rules_cache.get(room_type, {}).get("rules", []) or []
        forbidden = self._get_forbidden_titans(rules, [], current_state)
        for rule in rules:
            condition = rule.get("condition") or {}
            hp_cond = condition.get("titan_hp_below")
            team = rule.get("team") or []
            if rule.get("action") == "skip" or not hp_cond or "enemies_contain" in condition:
                continue
            if not all(t in team for t in hp_cond) or not any(t in healers for t in team):
                continue
            if any(t in forbidden for t in team):
                continue
            if self._evaluate_condition(condition, [], current_state):
                return rule.get("name") or "правило отхила"
        return ""

    def situational_packs(self, room_type):
        """Паки правил спасения (по ХП или энергии) и базовый пак: они ставятся по ситуации, а не против врагов,
        поэтому «золотым правилом» не становятся."""
        room_data = self.rules_cache.get(room_type, {})
        packs = [sorted(room_data.get("default_team") or [])]
        for rule in room_data.get("rules", []) or []:
            condition = rule.get("condition") or {}
            if "titan_hp_below" in condition or "titan_energy_below" in condition:
                packs.append(sorted(rule.get("team") or []))
        return packs

    def add_golden_rule(self, room_type, enemies, team, wins, battles, avg_hp):
        """«Золотое правило» (задача 9б): пак много раз побеждал этот состав врагов — ставить его против них.
        Не добавляется, если против этих врагов уже есть правило (ваше или запомненное: его бот не трогает)
        или пак ставится по ситуации (базовый, отхил). Возвращает правило или None."""
        enemies = sorted(enemies)
        if sorted(team) in self.situational_packs(room_type):
            return None
        rules = self.rules_cache.get(room_type, {}).get("rules", []) or []
        if any(r.get("action") != "skip" and sorted((r.get("condition") or {}).get("enemies_contain") or []) == enemies
               for r in rules):
            return None
        names = ", ".join(titan_name_ru(e) for e in enemies)
        rule = {"name": f"Золотое правило против: {names} (побед {wins} из {battles}, ХП {avg_hp:.0f}%)",
                "condition": {"enemies_contain": enemies}, "team": list(team), "source": "golden"}
        self._save_rule_first(room_type, rule)
        return rule

    def _save_rule_first(self, room_type, rule):
        """Ставит правило на 1-е место в bot_data/rules/<стихия>.yml (остальные правила не трогает)."""
        path = data_paths.rules_path(room_type)
        data = {"default_team": [], "rules": []}
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if loaded and isinstance(loaded, dict):
                    data = loaded
        if not isinstance(data.get("rules"), list):
            data["rules"] = []
        data["rules"].insert(0, rule)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp, path)
        self.rules_cache[room_type] = data

    def rescue_rules_fired_by_battle(self, room_type, enemies, before_state, after_state, fighters):
        """
        Правила отхила (titan_hp_below), которые сработали ИЗ-ЗА этого боя:
        до боя ХП-условие не выполнялось, после боя выполняется, и один из титанов
        условия только что дрался (он в fighters). Возвращает названия через запятую или "".
        Правила skip и условия по энергии не учитываются.
        """
        rules = self.rules_cache.get(room_type, {}).get("rules", [])
        fired = []
        for rule in rules:
            if rule.get("action") == "skip":
                continue
            hp_cond = rule.get("condition", {}).get("titan_hp_below")
            if not hp_cond or not any(t in fighters for t in hp_cond):
                continue
            only_hp = {"titan_hp_below": hp_cond}
            # Условие по врагам оставляем: правило отхила могло быть привязано к составу врагов
            if "enemies_contain" in rule["condition"]:
                only_hp["enemies_contain"] = rule["condition"]["enemies_contain"]
            if self._evaluate_condition(only_hp, enemies, before_state):
                continue  # уже срабатывало до боя
            if self._evaluate_condition(only_hp, enemies, after_state):
                fired.append(rule.get("name", "правило отхила"))
        return ", ".join(fired)

    def angus_line(self):
        """Строка лога при запуске: как бот играет пак с Ангусом (задача 12)."""
        if self.get_global_setting("angus_manual_control", False):
            return ("[ТАКТИКА] Ангус: ручная ульта включена (переключатель во вкладке «Мастер правил»). "
                    "Такой бой бот сам не откатывает.")
        return "[ТАКТИКА] Ангус: бой автобоем, как в остальных комнатах."

    def special_ult_for(self, team):
        """Стратегия ульты для пака без правила: "angus", если Ангус в паке и включён его ручной контроль."""
        return self._resolve_special_ult(team, {})

    def _resolve_special_ult(self, team, rule):
        """Ручная ульта Ангуса — только при включённом переключателе «Ручной контроль ульты Ангуса»
        (задача 12). Пометка special_ult: angus в правиле без переключателя не действует: раньше бот
        дописывал её к каждому запомненному правилу с Ангусом, и земля шла вручную (~40 с вместо ~27)."""
        manual_angus = self.get_global_setting("angus_manual_control", False)
        if not manual_angus:
            return "auto"
        if rule.get("special_ult"):
            return rule.get("special_ult")
        if "angus" in team:
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

    def learn_new_rule(self, room_type, enemies, team, base_condition=None, success_loss=None, source="gui"):
        """
        Запоминает удачный пак после отката (вашего или самостоятельного). Возвращает правило или None.
        Правило всегда привязано к составу врагов: «против этих врагов ставить этот пак».
        base_condition — условие правила, чей пак проиграл (например, {"titan_hp_below": {"araji": 50}}).
          Оно входит в новое правило: тогда новое срабатывает в той же ситуации и стоит выше старого.
          Пустое (проиграл базовый пак) — получится анти-пак против этих врагов.
        success_loss — наибольшая потеря ХП в удачном бою. Больше общего допуска — правило получает свой допуск.
        Правило с тем же условием не дублируется: у него меняется пак, и оно поднимается на 1-е место.
        """
        if not enemies:
            print("[ОБУЧЕНИЕ] Враги не распознаны — правило не сохраняю: без врагов оно срабатывало бы в каждой комнате.")
            return None
        team = list(team)
        condition = {k: v for k, v in (base_condition or {}).items() if k != "enemies_contain"}
        condition["enemies_contain"] = sorted(enemies)

        new_rule = {"name": learned_rule_name(condition), "condition": condition, "team": team, "source": source}
        global_delta = self.get_global_setting("max_hp_delta", 30)
        if success_loss is not None and success_loss > global_delta:
            new_rule["allowed_delta"] = int(success_loss)

        path = data_paths.rules_path(room_type)
        data = {"default_team": [], "rules": []}
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if loaded and isinstance(loaded, dict):
                    data = loaded
        if not isinstance(data.get("rules"), list):
            data["rules"] = []
        rules = data["rules"]

        same = next((i for i, r in enumerate(rules)
                     if r.get("action") != "skip" and same_condition(r.get("condition", {}), condition)), None)
        if same is None:
            rules.insert(0, new_rule)
            print(f"[ОБУЧЕНИЕ] Новое правило '{new_rule['name']}': пак {team}. Сохранено на 1-е место.")
        else:
            old = rules.pop(same)
            if sorted(old.get("team") or []) == sorted(team):
                rules.insert(0, old)
                print(f"[ОБУЧЕНИЕ] Правило '{old.get('name', new_rule['name'])}' с этим паком уже есть. Поднимаю на 1-е место.")
            else:
                rules.insert(0, new_rule)
                print(f"[ОБУЧЕНИЕ] Правило '{new_rule['name']}' обновлено: пак {team} вместо {old.get('team')}. "
                      "Стоит на 1-м месте.")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp, path)

        self.rules_cache[room_type] = data
        return rules[0]


# Правила, которые старый код обучения записал с ошибкой. Удаляются при запуске, по вашему решению.
# Правило совпадает, если совпали условие и пак, а также допуск и источник, если они указаны.
OBSOLETE_RULES = [
    # «Авто-отхил (araji < 65%)» с Ригелем: допуск 6% взят из боя, где окно SOS было ложным (сессия 03),
    # поэтому почти любой бой с этим паком давал окно SOS. Оно закрывало правило с Сигурдом.
    {"condition": {"titan_hp_below": {"araji": 65}},
     "team": {"araji", "hyperion", "rigel", "iyari", "lumira"}, "allowed_delta": 6},
    # Сессия 07 (задача 9б): бот сам запомнил анти-паки огня, хотя враги были ни при чём.
    # Комната 54: Араджи вошёл раненым, Молох и Вулкан были разовой помощью.
    {"condition": {"enemies_contain": ["angus", "silva", "verdok"]},
     "team": {"araji", "ignis", "acheron", "vulcan", "moloch"}, "source": "auto"},
    # Комната 74: обычный пак «проигрывал» из-за старого отката с допуском 20% — встал пак с Алекто.
    {"condition": {"enemies_contain": ["angus", "avalon", "eden"]},
     "team": {"araji", "acheron", "ignis", "vulcan", "alecto"}, "source": "auto"},
]


def is_obsolete_rule(rule):
    for bad in OBSOLETE_RULES:
        if not same_condition(rule.get("condition"), bad["condition"]) or set(rule.get("team") or []) != bad["team"]:
            continue
        if all(rule.get(key) == bad[key] for key in ("allowed_delta", "source") if key in bad):
            return True
    return False


def drop_obsolete_rules(path, data):
    """Убирает из файла правил устаревшие правила (OBSOLETE_RULES). Остальные правила не трогает."""
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        return
    keep = [r for r in rules if not (isinstance(r, dict) and is_obsolete_rule(r))]
    if len(keep) == len(rules):
        return
    for r in rules:
        if isinstance(r, dict) and is_obsolete_rule(r):
            delta = f", допуск {r['allowed_delta']}%" if r.get("allowed_delta") is not None else ""
            print(f"[ПРАВИЛА] Удаляю устаревшее правило '{r.get('name')}' (пак {r.get('team')}{delta}) из {path}.")
    data["rules"] = keep
    tmp = f"{path}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    os.replace(tmp, path)


def titan_name_ru(titan):
    """Имя титана по-русски для названий правил. Нет перевода — id как есть."""
    key = f"titan_{titan}"
    name = get_text("RU", key)
    return titan if name == key else name


def learned_rule_name(condition):
    """Понятное название запомненного правила: против кого и в какой ситуации."""
    name = "Анти-пак против: " + ", ".join(titan_name_ru(e) for e in condition.get("enemies_contain", []))
    situation = [f"{titan_name_ru(t)} < {v}% ХП" for t, v in condition.get("titan_hp_below", {}).items()]
    situation += [f"энергия {titan_name_ru(t)} < {v}%" for t, v in condition.get("titan_energy_below", {}).items()]
    if situation:
        name += " (при " + ", ".join(situation) + ")"
    return name


def same_condition(a, b):
    """Одинаковые ли условия правил (порядок врагов не важен)."""
    def norm(cond):
        cond = dict(cond or {})
        for key in ("enemies_contain", "require_fought"):
            if key in cond:
                cond[key] = sorted(cond[key])
        return cond
    return norm(a) == norm(b)


engine = RulesEngine()