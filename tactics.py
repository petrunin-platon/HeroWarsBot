# tactics.py
# Самостоятельные решения бота (задача 9): настройки тактики из profile.yml, история боёв против этих врагов,
# выбор запасного пака и можно ли откатить бой без вас.
# Без OpenCV и игры, поэтому проверяется тестами (tests/test_tactics.py, tests/test_replay_session_b.py).
import glob
import json
import os

ROOM_TYPES = ("water", "mix", "earth", "fire")
DEFAULT_DOOR_ORDER = ["water", "mix", "earth", "fire"]
DEFAULT_TRIES = 2   # сколько раз за комнату бот сам пробует запасной пак
MAX_TRIES = 3       # больше не бывает: бой не переигрывается по 10 раз

# Откуда взят запасной пак (для строк лога)
SOURCE_USER = "ваш список запасных паков"
SOURCE_RULES = "правила стихии"
SOURCE_HISTORY = "история боёв"


# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------
class Settings:
    """Настройки тактики из profile.yml (get — engine.get_global_setting: сначала global_thresholds, потом settings).
    Все новые настройки необязательные. Без них бот работает как раньше, только с проверкой общих потерь
    (3 титана и больше потеряли по 40%)."""

    def __init__(self, get):
        self.critical_hp = _number(get("critical_hp", 40), 40)
        self.max_hp_delta = _number(get("max_hp_delta", 30), 30)
        self.group_loss = (_number(get("group_loss_titans", 3), 3), _number(get("group_loss_percent", 40), 40))
        self.titan_critical_hp = {str(t): _number(v, 0) for t, v in _dict(get("titan_critical_hp", {})).items()}
        self.auto_rollback = get("auto_rollback", False) is True
        self.auto_rollback_tries = max(1, min(MAX_TRIES, _number(get("auto_rollback_tries", DEFAULT_TRIES), DEFAULT_TRIES)))
        self.backup_teams = {room: _packs(packs) for room, packs in _dict(get("backup_teams", {})).items()}
        self.door_order = door_order(get("door_order", None))

    def panic_hp(self, titan):
        """Порог паники титана: личный, если задан, иначе общий."""
        return self.titan_critical_hp.get(titan, self.critical_hp)

    def describe(self):
        """Строки для лога при запуске бота."""
        titans, percent = self.group_loss
        group = f"{titans} и больше титанов потеряли по {percent}%" if titans > 0 else "выключены"
        lines = [f"[ТАКТИКА] Плохой бой: ХП ниже {self.critical_hp}% | потеря больше {self.max_hp_delta}% | "
                 f"общие потери: {group}"]
        if self.titan_critical_hp:
            personal = ", ".join(f"{t} {v}%" for t, v in self.titan_critical_hp.items())
            lines.append(f"[ТАКТИКА] Личные пороги ХП: {personal}")
        if self.auto_rollback:
            lines.append(f"[ТАКТИКА] Бот решает сам (auto_rollback): плохой бой откатывает и переигрывает "
                         f"запасным паком, не больше {self.auto_rollback_tries} раз(а) за комнату, потом спрашивает вас.")
        else:
            lines.append("[ТАКТИКА] Бот решает сам: выключено. При плохом бое — окно SOS, как раньше "
                         "(включается во вкладке с настройками: «Бот решает сам»).")
        if self.door_order != DEFAULT_DOOR_ORDER:
            lines.append(f"[ТАКТИКА] Порядок дверей: {' → '.join(self.door_order)}")
        return lines


def profile_getter(profile):
    """Как engine.get_global_setting, но для словаря профиля: сначала global_thresholds, потом settings."""
    thresholds = _dict(profile.get("global_thresholds"))
    settings = _dict(profile.get("settings"))

    def get(key, default=None):
        if key in thresholds:
            return thresholds[key]
        return settings.get(key, default)
    return get


# Где в profile.yml лежит каждая настройка тактики (окно программы пишет туда же)
THRESHOLD_KEYS = ("group_loss_titans", "group_loss_percent", "titan_critical_hp")
SETTINGS_KEYS = ("auto_rollback", "auto_rollback_tries", "backup_teams", "door_order")


def read_tactics(profile):
    """Настройки тактики из словаря профиля — для окна программы (ui/tactics_dialog.py)."""
    s = Settings(profile_getter(profile))
    return {
        "auto_rollback": s.auto_rollback,
        "auto_rollback_tries": s.auto_rollback_tries,
        "group_loss_titans": s.group_loss[0],
        "group_loss_percent": s.group_loss[1],
        "titan_critical_hp": dict(s.titan_critical_hp),
        "backup_teams": {room: [list(p) for p in packs] for room, packs in s.backup_teams.items() if packs},
        "door_order": list(s.door_order),
    }


def write_tactics(profile, values):
    """Записывает настройки тактики в словарь профиля (остальные ключи не трогает). Возвращает профиль."""
    if not isinstance(profile.get("global_thresholds"), dict):
        profile["global_thresholds"] = {}
    if not isinstance(profile.get("settings"), dict):
        profile["settings"] = {}
    for key, value in values.items():
        section = "global_thresholds" if key in THRESHOLD_KEYS else "settings" if key in SETTINGS_KEYS else None
        if section:
            profile[section][key] = value
    return profile


def door_order(value):
    """Порядок дверей из профиля. Неизвестные стихии отбрасываются, забытые добавляются в конец по умолчанию."""
    order = []
    if isinstance(value, (list, tuple)):
        order = [str(r).strip().lower() for r in value]
        order = [r for i, r in enumerate(order) if r in ROOM_TYPES and r not in order[:i]]
    return order + [r for r in DEFAULT_DOOR_ORDER if r not in order]


def _number(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _dict(value):
    return value if isinstance(value, dict) else {}


def _packs(value):
    """Список паков [[титан, ...], ...]. Неправильные записи пропускаются."""
    if not isinstance(value, list):
        return []
    return [[str(t) for t in pack] for pack in value if isinstance(pack, list) and pack]


# ---------------------------------------------------------------------------
# История боёв
# ---------------------------------------------------------------------------
class BattleHistory:
    """История боёв: bot_data/logs/*.jsonl (её же разбирает вкладка «Аналитика») плюс бои этого запуска.
    Бой «плохой», если записан как ROLLBACK (его откатили), «хороший» — SUCCESS."""

    def __init__(self, entries=None):
        self.entries = list(entries or [])

    @classmethod
    def load(cls, folder):
        entries = []
        for path in sorted(glob.glob(os.path.join(folder, "*.jsonl")), key=os.path.getmtime):
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(entry, dict):
                            entries.append(entry)
            except OSError:
                continue
        return cls(entries)

    def add(self, entry):
        if entry:
            self.entries.append(entry)

    def _battles(self, room, enemies, team=None):
        """Бои в этой стихии против этих врагов; team — только этого пака (None — любого)."""
        enemies = set(enemies or [])
        team = None if team is None else set(team)
        for e in self.entries:
            if e.get("room") != room or set(e.get("enemies") or []) != enemies:
                continue
            if team is not None and set(e.get("team") or []) != team:
                continue
            if e.get("action") in ("SUCCESS", "ROLLBACK"):
                yield e

    def stats(self, room, enemies, team):
        """Как пак играл против этих врагов в этой стихии: wins, fails, avg_hp (среднее ХП после победы),
        last_failed (последний бой откатили)."""
        wins, fails, hp, last = 0, 0, [], None
        for e in self._battles(room, enemies, team):
            last = e["action"]
            if last == "ROLLBACK":
                fails += 1
            else:
                wins += 1
                hp.append(_avg_hp(e, team))
        return {"wins": wins, "fails": fails, "avg_hp": sum(hp) / len(hp) if hp else 0.0,
                "last_failed": last == "ROLLBACK"}

    def lost_to(self, room, enemies, team):
        """Пак «проигрывает этим врагам»: последний бой против них откатили, и побед у него не больше, чем поражений.
        Пак, который раньше много раз побеждал этих врагов, после одной неудачи из запасных не выпадает."""
        if not enemies or not team:
            return False
        st = self.stats(room, enemies, team)
        return st["last_failed"] and st["fails"] >= st["wins"]

    def winners(self, room, enemies):
        """Паки, которые побеждали этих врагов: [(пак, stats)], лучшие (больше ХП после боя) первыми."""
        seen, result = set(), []
        for e in self._battles(room, enemies):
            key = frozenset(e.get("team") or [])
            if not key or key in seen:
                continue
            seen.add(key)
            st = self.stats(room, enemies, e["team"])
            if st["wins"] > 0:
                result.append((list(e["team"]), st))
        result.sort(key=lambda x: (-x[1]["avg_hp"], -x[1]["wins"]))
        return result


def _avg_hp(entry, team):
    hp = [v.get("hp", 0) for t, v in (entry.get("hp_status") or {}).items()
          if t in team and isinstance(v, dict) and v.get("status") != "ОТСУТСТВУЕТ"]
    return sum(hp) / len(hp) if hp else 0.0


# ---------------------------------------------------------------------------
# Запасной пак
# ---------------------------------------------------------------------------
def choose_backup(room, enemies, tried, state, settings, rule_packs, history, forbidden=()):
    """
    Запасной пак для этой комнаты. Возвращает (пак, откуда взят) или (None, None).
    Порядок поиска:
      1) ваш список (settings.backup_teams[room]);
      2) паки из правил стихии (rule_packs — [(пак, условие)] из engine.room_packs):
         сначала анти-паки против этих врагов, потом паки, которые уже побеждали этих врагов
         (лучшие первыми), потом остальные анти-паки, потом остальные правила и базовый пак;
      3) в последнюю очередь — паки из истории боёв, которые побеждали этих врагов.
    Не берётся пак, который:
      - уже проиграл в этой комнате (tried);
      - проигрывает этим врагам (последний бой откатили, а побед не больше, чем поражений);
      - содержит титана из чёрного списка (правила skip) или титана, у которого ХП ниже порога паники.
    """
    tried = {frozenset(p) for p in tried}
    candidates = [(p, SOURCE_USER) for p in settings.backup_teams.get(room, [])]
    candidates += [(p, SOURCE_RULES) for p in _rank_rule_packs(room, enemies, rule_packs, history)]
    candidates += [(p, SOURCE_HISTORY) for p, _ in history.winners(room, enemies)]

    for pack, source in candidates:
        if _usable(pack, room, enemies, tried, state, settings, history, forbidden):
            return list(pack), source
    return None, None


def _rank_rule_packs(room, enemies, rule_packs, history):
    enemies_set = set(enemies or [])
    ranked = []
    for index, (pack, condition) in enumerate(rule_packs):
        against = condition.get("enemies_contain")
        st = history.stats(room, enemies, pack)
        if against and set(against) <= enemies_set:
            group, quality = 0, 0.0     # анти-пак против этих врагов («золотое» или запомненное правило)
        elif st["wins"] > 0:
            group, quality = 1, -st["avg_hp"]  # уже побеждал этих врагов
        elif against:
            group, quality = 2, 0.0     # анти-пак против других врагов
        else:
            group, quality = 3, 0.0     # правило отхила или базовый пак
        ranked.append(((group, quality, index), pack))
    return [pack for _, pack in sorted(ranked, key=lambda x: x[0])]


def _usable(pack, room, enemies, tried, state, settings, history, forbidden):
    if not pack or pack == ["STOP"] or frozenset(pack) in tried:
        return False
    if any(t in forbidden for t in pack):
        return False
    if any(state.get(t, {}).get("hp", 100) < max(1, settings.panic_hp(t)) for t in pack):
        return False
    return not history.lost_to(room, enemies, pack)


def auto_rollback_blocker(settings, manual_battle, unreadable, tries_done, user_pack=False):
    """Почему бот не может откатить бой сам (текст для лога) или None, если может.
    user_pack — в бою был пак, который выбрали вы в окне SOS: тогда решаете тоже вы."""
    if not settings.auto_rollback:
        return "самостоятельный откат выключен (auto_rollback в profile.yml)"
    if user_pack:
        return "этот пак выбрали вы, решение тоже за вами"
    if manual_battle:
        return "бой шёл вручную (Ангус): на окне результата нет «Ещё раз»"
    if unreadable:
        return "окно результата не прочиталось, решает человек"
    if tries_done >= settings.auto_rollback_tries:
        return f"в этой комнате бот уже откатывал сам ({tries_done} из {settings.auto_rollback_tries})"
    return None


def pick_door(elements, order, is_forbidden):
    """Какую дверь выбрать. elements — стихии дверей на экране; order — порядок стихий (door_order);
    is_forbidden(стихия) — дверь под запретом правил skip.
    Возвращает (номер двери в elements, разрешена ли она, стихии пропущенных запрещённых дверей).
    Все двери под запретом — берётся первая по порядку."""
    rank = {room: i for i, room in enumerate(order)}
    by_priority = sorted(range(len(elements)), key=lambda i: rank.get(elements[i], 99))
    skipped = []
    for i in by_priority:
        if not is_forbidden(elements[i]):
            return i, True, skipped
        skipped.append(elements[i])
    return by_priority[0], False, skipped
