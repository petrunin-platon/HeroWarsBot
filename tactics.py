# tactics.py
# Самостоятельные решения бота (задачи 9, 9б и 9в): настройки тактики из profile.yml, история боёв против этих врагов,
# выбор запасного пака, можно ли откатить бой без вас, прогноз потерь раненых титанов (с учётом энергии),
# выбор двери по здоровью, решение, если вы не ответили на окно SOS, «золотые правила»
# и пак отхила, который бот собирает сам.
# Без OpenCV и игры, поэтому проверяется тестами (tests/test_tactics.py, tests/test_tactics_9b.py, tests/test_tactics_9v.py,
# tests/test_replay_session_b.py, tests/test_replay_session_07.py).
import glob
import json
import os
from datetime import datetime, timedelta

from battle_verdict import full_hp_reason

ROOM_TYPES = ("water", "mix", "earth", "fire")
DEFAULT_DOOR_ORDER = ["water", "mix", "earth", "fire"]
DEFAULT_TRIES = 2   # сколько раз за комнату бот сам пробует запасной пак
MAX_TRIES = 3       # больше не бывает: бой не переигрывается по 10 раз
DEFAULT_SOS_TIMEOUT = 10  # минут: столько бот ждёт ответа на окно SOS, потом решает сам (0 — ждать всегда)
MAX_SOS_TIMEOUT = 60

# Кто лечит союзников (ваш ответ на вопрос 2): сильно — Гиперион и Ияри, слабее — Авалон, Сигурд, Солярис, Паллант, Метида
HEALERS = ("hyperion", "iyari", "avalon", "sigurd", "solaris", "pallant", "metida")

# «Золотое правило» — как во вкладке «Аналитика»: не меньше 5 боёв с этими врагами и не меньше 80% побед
GOLDEN_MIN_BATTLES = 5
GOLDEN_MIN_WINRATE = 80

# Прогноз потерь: сколько последних боёв пака брать и сколько нужно хотя бы (по одному бою прогноз ненадёжен:
# в сессии 07 Люмира один раз потеряла 45% против сильных врагов, а в следующий раз — ничего)
LOSS_SAMPLES = 5
LOSS_MIN_SAMPLES = 2
# Энергия при входе в бой (задача 9в, ваш ответ на вопрос 22): Араджи с 60–80% энергии в огне теряет мало,
# с меньшей — много. Поэтому прогноз берётся из боёв, где энергия титана была похожей (отличалась не больше чем на 25%)
ENERGY_NEAR = 25

# Пак отхила, который бот собирает сам (задача 9в, ваш ответ на вопрос 23)
HEAL_ROOM = "mix"        # лечат в смешанной: туда можно ставить кого угодно
DEFAULT_HEAL_HP = 60     # лечить ниже 60% ХП: «пробить полосу здоровья у Ригеля выше 60% — и он ещё 50 комнат ходит»
MAX_HEAL_REMOVE = 3      # сколько титанов можно перечислить в «кого убирать из пака ради раненого»
STUCK_BATTLES = 2        # раненый в паке «не поднимается»: столько последних боёв в смешанной подряд ниже порога
HELPER_MIN_HP = 80       # помощник-лекарь (как Сигурд для Ригеля) здоров: «даже если Сигурд просядет на 60%»
HELPER_MIN_ENERGY = 60   # и заряжен: «если у него при входе будет более 60% энергии... ульту использует» (вопрос 22)

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
        self.sos_timeout_minutes = max(0, min(MAX_SOS_TIMEOUT, _number(get("sos_timeout_minutes", DEFAULT_SOS_TIMEOUT),
                                                                       DEFAULT_SOS_TIMEOUT)))
        self.reset_hour = _number(get("reset_hour", 5), 5)
        # Пак отхила (задача 9в): лечить ниже heal_hp% ХП (0 — не собирать), кого убирать из пака ради раненого
        self.heal_hp = max(0, min(100, _number(get("heal_below_hp", DEFAULT_HEAL_HP), DEFAULT_HEAL_HP)))
        order = get("heal_remove_order", [])
        order = [str(t) for t in order] if isinstance(order, list) else []
        self.heal_remove_order = [t for i, t in enumerate(order) if t not in order[:i]][:MAX_HEAL_REMOVE]

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
        if self.sos_timeout_minutes:
            lines.append(f"[ТАКТИКА] Окно SOS без ответа {self.sos_timeout_minutes} мин — бот решает сам "
                         "(запасной пак, принять бой или мягкая пауза).")
        else:
            lines.append("[ТАКТИКА] Окно SOS: бот ждёт вашего ответа сколько угодно.")
        if self.door_order != DEFAULT_DOOR_ORDER:
            lines.append(f"[ТАКТИКА] Порядок дверей: {' → '.join(self.door_order)}")
        if self.auto_rollback and self.heal_hp:
            remove = " → ".join(self.heal_remove_order) if self.heal_remove_order else \
                "сам: с конца базового пака, кроме лекарей"
            lines.append(f"[ТАКТИКА] Отхил в смешанной без вашего правила: бот лечит титанов ниже {self.heal_hp}% ХП "
                         f"по одному. Кого убирать из пака: {remove}.")
        return lines

    def full_hp_reason(self, pack, team_status, hp_before, allowed_delta=None):
        """Был бы бой плохим, если бы все вошли в него со 100% ХП (виноваты враги)? Причина или ""."""
        delta = self.max_hp_delta if allowed_delta is None else allowed_delta
        return full_hp_reason(pack, team_status, hp_before, self.critical_hp, delta,
                              group_loss=self.group_loss, titan_critical_hp=self.titan_critical_hp)


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
SETTINGS_KEYS = ("auto_rollback", "auto_rollback_tries", "backup_teams", "door_order", "sos_timeout_minutes",
                 "heal_below_hp", "heal_remove_order")


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
        "sos_timeout_minutes": s.sos_timeout_minutes,
        "heal_below_hp": s.heal_hp,
        "heal_remove_order": list(s.heal_remove_order),
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
    Бой «хороший», если записан как SUCCESS. Откат (ROLLBACK) — поражение пака против этих врагов, только если
    виноваты враги: бой был бы плохим и при 100% ХП у всех (Settings.full_hp_reason, пороги — нынешние).
    Откат из-за того, что титан вошёл в бой раненым, пак не портит (сессия 07: из-за такого отката в комнате 74
    бот поставил пак с Алекто вместо обычного).
    ХП до боя: из записи (hp_before, пишется с задачи 9б). В старых записях — ХП титана после его последней удачной
    битвы в тот же игровой день (откат бой отменяет, поэтому откаты ХП не меняют). Неизвестно — считается 100%.
    Энергия до боя (задача 9в) — так же: из записи (energy_before) или после последней удачной битвы этого дня."""

    def __init__(self, entries=None, settings=None):
        self.settings = settings or Settings(lambda key, default=None: default)
        self.entries = []
        self.before = []      # ХП до боя для каждой записи: {титан: ХП}; кого нет — неизвестно
        self.energy = []      # энергия до боя для каждой записи: {титан: %}; кого нет — неизвестно
        self._last_hp = {}    # ХП титанов после последней удачной битвы в этот игровой день
        self._last_energy = {}
        self._day = None
        for entry in entries or []:
            self.add(entry)

    @classmethod
    def load(cls, folder, settings=None):
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
        entries.sort(key=lambda e: str(e.get("timestamp") or ""))  # по времени: файлы разных запусков вперемешку
        return cls(entries, settings)

    def add(self, entry):
        if not entry:
            return
        day = _game_day(entry.get("timestamp"), self.settings.reset_hour)
        if day != self._day:
            self._day, self._last_hp, self._last_energy = day, {}, {}
        before = _known(entry, "hp_before", self._last_hp)
        energy = _known(entry, "energy_before", self._last_energy)
        if entry.get("action") == "SUCCESS":
            for titan, st in (entry.get("hp_status") or {}).items():
                if isinstance(st, dict) and st.get("status") != "ОТСУТСТВУЕТ":
                    self._last_hp[titan] = st.get("hp", 0)
                    if isinstance(st.get("energy"), (int, float)):
                        self._last_energy[titan] = st["energy"]
        self.entries.append(entry)
        self.before.append(before)
        self.energy.append(energy)

    def enemies_to_blame(self, index):
        """Откат номер index — вина врагов (бой был бы плохим и со 100% ХП)? Причина или ""."""
        e = self.entries[index]
        return self.settings.full_hp_reason(e.get("team") or [], e.get("hp_status") or {}, self.before[index])

    def _battles(self, room, enemies=None, team=None):
        """Номера боёв в этой стихии; enemies — только против этих врагов, team — только этого пака (None — любые)."""
        enemies = None if enemies is None else set(enemies)
        team = None if team is None else set(team)
        for i, e in enumerate(self.entries):
            if e.get("room") != room or e.get("action") not in ("SUCCESS", "ROLLBACK"):
                continue
            if enemies is not None and set(e.get("enemies") or []) != enemies:
                continue
            if team is not None and set(e.get("team") or []) != team:
                continue
            yield i

    def stats(self, room, enemies, team):
        """Как пак играл против этих врагов в этой стихии: wins, fails (откаты по вине врагов), weak_entry (откаты
        из-за раненых титанов — не считаются), avg_hp (среднее ХП после победы), last_failed (последний бой проигран)."""
        wins, fails, weak, hp, last = 0, 0, 0, [], None
        for i in self._battles(room, enemies or [], team):
            e = self.entries[i]
            if e["action"] == "ROLLBACK":
                if not self.enemies_to_blame(i):
                    weak += 1
                    continue
                fails += 1
            else:
                wins += 1
                hp.append(_avg_hp(e, team))
            last = e["action"]
        return {"wins": wins, "fails": fails, "weak_entry": weak, "avg_hp": sum(hp) / len(hp) if hp else 0.0,
                "last_failed": last == "ROLLBACK"}

    def lost_to(self, room, enemies, team):
        """Пак «проигрывает этим врагам»: последний бой против них откатили по вине врагов, и побед у него не больше,
        чем поражений. Пак, который раньше много раз побеждал этих врагов, после одной неудачи из запасных не выпадает."""
        if not enemies or not team:
            return False
        st = self.stats(room, enemies, team)
        return st["last_failed"] and st["fails"] >= st["wins"]

    def winners(self, room, enemies):
        """Паки, которые побеждали этих врагов: [(пак, stats)], лучшие (больше ХП после боя) первыми."""
        seen, result = set(), []
        for i in self._battles(room, enemies or []):
            e = self.entries[i]
            key = frozenset(e.get("team") or [])
            if not key or key in seen:
                continue
            seen.add(key)
            st = self.stats(room, enemies, e["team"])
            if st["wins"] > 0:
                result.append((list(e["team"]), st))
        result.sort(key=lambda x: (-x[1]["avg_hp"], -x[1]["wins"]))
        return result

    def expected_loss(self, room, team, titan, enemies=None, energy=None):
        """Сколько ХП обычно теряет титан с этим паком в этой стихии: среднее за последние бои (LOSS_SAMPLES).
        Если против этих врагов боёв хотя бы LOSS_MIN_SAMPLES — только они. Бои, где ХП до боя неизвестно, не берутся.
        energy — энергия титана сейчас (задача 9в): если боёв с похожей энергией (±ENERGY_NEAR) хотя бы
        LOSS_MIN_SAMPLES — берутся только они. None — боёв меньше LOSS_MIN_SAMPLES."""
        samples = []
        for i in self._battles(room, None, team):
            e = self.entries[i]
            before = self.before[i].get(titan)
            st = (e.get("hp_status") or {}).get(titan)
            if before is None or not isinstance(st, dict) or st.get("status") == "ОТСУТСТВУЕТ":
                continue
            same = enemies is not None and set(e.get("enemies") or []) == set(enemies)
            samples.append((same, self.energy[i].get(titan), max(0, before - st.get("hp", 0))))
        pool = [s for s in samples if s[0]]
        if len(pool) < LOSS_MIN_SAMPLES:
            pool = samples
        if energy is not None:
            near = [s for s in pool if s[1] is not None and abs(s[1] - energy) <= ENERGY_NEAR]
            if len(near) >= LOSS_MIN_SAMPLES:
                pool = near
        losses = [loss for _, _, loss in pool][-LOSS_SAMPLES:]
        return sum(losses) / len(losses) if len(losses) >= LOSS_MIN_SAMPLES else None

    def not_healing(self, room, titan, below, battles=STUCK_BATTLES):
        """Раненый «не поднимается» (задача 9в): в последних battles удачных боях в этой стихии с ним, в этот игровой
        день, его ХП и до боя, и после было ниже below (ваш пример: Ригель 2–3 боя в смешанной держится на 30–60%)."""
        count = 0
        for i in range(len(self.entries) - 1, -1, -1):
            e = self.entries[i]
            if _game_day(e.get("timestamp"), self.settings.reset_hour) != self._day:
                break
            if e.get("room") != room or e.get("action") != "SUCCESS" or titan not in (e.get("team") or []):
                continue
            st = (e.get("hp_status") or {}).get(titan)
            before = self.before[i].get(titan)
            if not isinstance(st, dict) or before is None or before >= below or st.get("hp", 100) >= below:
                return False
            count += 1
            if count >= battles:
                return True
        return False


def _known(entry, key, last):
    """ХП или энергия до боя: из записи (key), а в старых записях — после последней удачной битвы этого дня (last)."""
    stored = entry.get(key)
    if isinstance(stored, dict):
        return {t: v for t, v in stored.items() if isinstance(v, (int, float))}
    return {t: last[t] for t in entry.get("team") or [] if t in last}


def _game_day(timestamp, reset_hour):
    """Игровой день записи (день сдвинут на reset_hour). None — времени в записи нет."""
    try:
        moment = datetime.strptime(str(timestamp), "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None
    return (moment - timedelta(hours=reset_hour)).strftime("%Y-%m-%d")


def _avg_hp(entry, team):
    hp = [v.get("hp", 0) for t, v in (entry.get("hp_status") or {}).items()
          if t in team and isinstance(v, dict) and v.get("status") != "ОТСУТСТВУЕТ"]
    return sum(hp) / len(hp) if hp else 0.0


# ---------------------------------------------------------------------------
# Раненые титаны: прогноз потерь (задача 9б)
# ---------------------------------------------------------------------------
def wounded_at_risk(room, enemies, pack, state, settings, history):
    """Кто из пака, судя по прошлым боям, упадёт ниже порога паники: [(титан, ХП сейчас, обычная потеря)].
    Смотрим только раненых (ХП известно и меньше 100%). Здоровым этот пак не опасен: если бы он проигрывал
    этим врагам, его отсеяла бы история (lost_to). Обычная потеря — BattleHistory.expected_loss,
    с задачи 9в — по боям с похожей энергией титана, если она известна."""
    risks = []
    for titan in pack:
        hp = state.get(titan, {}).get("hp")
        if hp is None or hp >= 100:
            continue
        loss = history.expected_loss(room, pack, titan, enemies, energy=state.get(titan, {}).get("energy"))
        if loss and hp - loss < max(1, settings.panic_hp(titan)):
            risks.append((titan, hp, round(loss)))
    return risks


def is_rescue_condition(condition):
    """Пак дало правило спасения (по ХП или энергии): его вы поставили для раненого, бот его заранее не заменяет."""
    return "titan_hp_below" in (condition or {}) or "titan_energy_below" in (condition or {})


def describe_risks(risks, state=None):
    """Строка для лога: «ARAJI: 36% ХП, обычно теряет ~29%» (со state — и энергия: «ARAJI: 36% ХП, ⚡47%, ...»)."""
    def energy(titan):
        value = (state or {}).get(titan, {}).get("energy")
        return f", ⚡{value}%" if value is not None else ""
    return "; ".join(f"{t.upper()}: {hp}% ХП{energy(t)}, обычно теряет ~{loss}%" for t, hp, loss in risks)


# ---------------------------------------------------------------------------
# Пак отхила, который бот собирает сам (задача 9в)
# ---------------------------------------------------------------------------
def home_rooms(titan, base_packs, room=HEAL_ROOM):
    """Где титана лечат в своей комнате: стихии, в базовом паке которых он стоит вместе с лекарем
    (вода — Гиперион и Сигурд, земля — Авалон). Огненных лечить негде: в огне лекарей нет (ваш ответ на вопрос 23)."""
    return [r for r, pack in base_packs.items()
            if r != room and pack and titan in pack and any(t in HEALERS for t in pack)]


def heals_at_home(titan, base_packs, room=HEAL_ROOM):
    """Лечится ли титан в своей комнате (home_rooms). base_packs — {стихия: пак}."""
    return bool(home_rooms(titan, base_packs, room))


def removal_order(pack, settings, keep=()):
    """Кого убирать из пака ради раненого, по порядку: сначала ваш список (окно «⚙️ Тактика»), потом сам —
    с конца пака, кроме лекарей. Для пака «Гиперион, Ригель, Ияри, Люмира, Амон» это Амон, потом Люмира —
    как вы ответили на вопрос 23. keep — кого не убирать (самого раненого)."""
    order = [t for t in settings.heal_remove_order if t in pack]
    order += [t for t in reversed(pack) if t not in HEALERS and t not in order]
    return [t for t in order if t not in keep]


def _helper(pack, state, forbidden):
    """Помощник-лекарь (как Сигурд вместо Амона для Ригеля): лекарь не из пака, здоров (HELPER_MIN_HP) и заряжен
    (HELPER_MIN_ENERGY), чтобы сразу сделать ультимейт. Из подходящих — самый заряженный. (титан, ХП, энергия) или None."""
    best = None
    for titan in HEALERS:
        st = state.get(titan) or {}
        hp, energy = st.get("hp"), st.get("energy")
        if titan in pack or titan in forbidden or hp is None or energy is None:
            continue
        if hp >= HELPER_MIN_HP and energy >= HELPER_MIN_ENERGY and (best is None or energy > best[2]):
            best = (titan, hp, energy)
    return best


def heal_plan(room, pack, state, settings, history, base_packs, forbidden=(), enemies=None, special_ult=None,
              notes=None):
    """
    Пак отхила, который бот собирает сам (задача 9в, ваш ответ на вопрос 23), когда ваше правило отхила
    не сработало. Только в смешанной (туда можно ставить кого угодно), pack — пак, который поставил бы движок правил.
    Лечим по одному — того, кто ближе всех к своему порогу паники. Кого лечим:
      - ХП ниже settings.heal_hp, но не ниже порога паники (ниже в смешанной уже не вылечить — вопрос 1),
        и титан не под запретом правил skip;
      - его нет в паке, и в своей комнате его не лечат (heals_at_home: огненных лечить негде) или отхила там
        не хватает (STUCK_BATTLES боя подряд в своей комнате не поднимается выше порога — ваше замечание:
        водных и земляных вы тоже иногда лечите в смешанной) —
        он встаёт вместо первого из removal_order;
      - или он в паке, но STUCK_BATTLES боя подряд не поднимается выше порога (BattleHistory.not_healing) —
        тогда вместо первого из removal_order встаёт помощник-лекарь (_helper).
    Пак не берётся, если в нём не осталось лекаря, он проигрывает этим врагам (history.lost_to), опасен для раненых
    по прогнозу (wounded_at_risk) или требует ручного боя (special_ult(пак) не "auto", например Ангус).
    Возвращает (пак, кого лечим, пояснение) или None. notes — куда писать, почему раненого не лечим (для лога).
    """
    if room != HEAL_ROOM or not settings.heal_hp or not pack or pack == ["STOP"]:
        return None

    def note(text):
        if notes is not None:
            notes.append(text)

    wounded = []
    for titan, st in state.items():
        hp = st.get("hp") if isinstance(st, dict) else None
        if hp is None or hp <= 0 or hp >= settings.heal_hp:
            continue  # здоров, неизвестно или погиб (погибшие до конца дня не воюют)
        panic = max(1, settings.panic_hp(titan))
        if hp < panic:
            note(f"{titan.upper()} {hp}%: ниже порога паники ({panic}%), в смешанной его уже не вылечить")
        elif titan in forbidden:
            note(f"{titan.upper()} {hp}%: под запретом правил skip")
        else:
            wounded.append((hp - panic, titan, hp))

    for _, titan, hp in sorted(wounded):
        out = removal_order(pack, settings, keep={titan})
        if titan in pack:
            if not history.not_healing(room, titan, settings.heal_hp):
                continue  # лечится обычным паком смешанной
            helper = _helper(pack, state, forbidden)
            if not helper:
                note(f"{titan.upper()} {hp}%: не поднимается, но нет здорового заряженного лекаря "
                     f"(ХП от {HELPER_MIN_HP}%, энергия от {HELPER_MIN_ENERGY}%)")
                continue
            if not out:
                note(f"{titan.upper()} {hp}%: некого убрать из пака ради лекаря")
                continue
            new_pack = [helper[0] if t == out[0] else t for t in pack]
            why = (f"{titan.upper()} {hp}% ХП {STUCK_BATTLES} боя подряд не поднимается выше {settings.heal_hp}% — "
                   f"лекарь {helper[0].upper()} ({helper[1]}% ХП, ⚡{helper[2]}%) вместо {out[0].upper()}")
        else:
            homes = home_rooms(titan, base_packs, room)
            stuck = [r for r in homes if history.not_healing(r, titan, settings.heal_hp)]
            if homes and not stuck:
                continue  # его лечат в своей комнате (вода, земля), и отхила там хватает
            where = (f"в своей комнате ({stuck[0]}) {STUCK_BATTLES} боя подряд не поднимается выше {settings.heal_hp}%"
                     if stuck else "в своей комнате его не лечат")
            if len(pack) < 5:
                new_pack, why = list(pack) + [titan], f"{titan.upper()} {hp}% ХП: {where}"
            elif out:
                new_pack = [titan if t == out[0] else t for t in pack]
                why = f"{titan.upper()} {hp}% ХП: {where} — ставлю вместо {out[0].upper()}"
            else:
                note(f"{titan.upper()} {hp}%: некого убрать из пака")
                continue

        risks = wounded_at_risk(room, enemies, new_pack, state, settings, history)
        if not any(t in HEALERS for t in new_pack):
            note(f"{new_pack}: в паке не осталось лекаря")
        elif history.lost_to(room, enemies, new_pack):
            note(f"{new_pack}: проигрывает этим врагам")
        elif risks:
            note(f"{new_pack}: опасен для раненых ({describe_risks(risks, state)})")
        elif special_ult and special_ult(new_pack) != "auto":
            note(f"{new_pack}: нужен ручной бой ({special_ult(new_pack)}), его нельзя откатить")
        else:
            return new_pack, titan, why
    return None


# ---------------------------------------------------------------------------
# Запасной пак
# ---------------------------------------------------------------------------
def choose_backup(room, enemies, tried, state, settings, rule_packs, history, forbidden=(),
                  risky=None, allow_risky=True, notes=None):
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
      - проигрывает этим врагам (последний бой откатили по вине врагов, а побед не больше, чем поражений);
      - содержит титана из чёрного списка (правила skip) или титана, у которого ХП ниже порога паники.
    risky(пак) — чем пак опасен для раненых титанов ("" — не опасен). Опасный пак берётся, только если
    allow_risky и неопасных нет. notes — список, куда пишутся причины, почему паки не взяты (для лога).
    """
    tried = {frozenset(p) for p in tried}
    candidates = [(p, SOURCE_USER) for p in settings.backup_teams.get(room, [])]
    candidates += [(p, SOURCE_RULES) for p in _rank_rule_packs(room, enemies, rule_packs, history)]
    candidates += [(p, SOURCE_HISTORY) for p, _ in history.winners(room, enemies)]

    seen, fallback = set(), None
    for pack, source in candidates:
        key = frozenset(pack)
        if not pack or pack == ["STOP"] or key in seen:
            continue
        seen.add(key)
        if key in tried:
            continue
        why = _unusable(pack, room, enemies, state, settings, history, forbidden)
        if not why and risky:
            danger = risky(pack)
            if danger:
                why = f"опасен для раненых ({danger})"
                fallback = fallback or (list(pack), source)
        if why:
            if notes is not None:
                notes.append(f"{pack} ({source}): {why}")
            continue
        return list(pack), source
    if fallback and allow_risky:
        return fallback
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


def _unusable(pack, room, enemies, state, settings, history, forbidden):
    """Почему пак нельзя брать в запасные (текст для лога) или None, если можно."""
    banned = [t for t in pack if t in forbidden]
    if banned:
        return "под запретом правил skip: " + ", ".join(banned)
    hurt = [t for t in pack if state.get(t, {}).get("hp", 100) < max(1, settings.panic_hp(t))]
    if hurt:
        return "ниже порога паники: " + ", ".join(f"{t} {state[t]['hp']}%" for t in hurt)
    if history.lost_to(room, enemies, pack):
        return "проигрывает этим врагам"
    return None


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


# ---------------------------------------------------------------------------
# Вы не ответили на окно SOS (задача 9б)
# ---------------------------------------------------------------------------
ROLLBACK, ACCEPT, PAUSE = "rollback", "accept", "pause"


def decide_without_you(pack, team_status, can_rollback, backup):
    """Окно SOS висит sos_timeout_minutes, а вы молчите. Что делает бот:
      ROLLBACK — откатить бой и переиграть запасным паком (бой можно откатить, и запасной пак есть);
      ACCEPT   — принять бой: все титаны пака живы;
      PAUSE    — безопасно остановиться (мягкая пауза и сообщение в Telegram): кто-то погиб или не найден на окне.
    Возвращает (решение, пояснение для лога)."""
    if can_rollback and backup:
        return ROLLBACK, f"откатываю бой и переигрываю паком {backup}"
    lost = [t for t in pack if (team_status.get(t) or {}).get("status") != "ЖИВ"
            or (team_status.get(t) or {}).get("hp", 0) <= 0]
    if not lost:
        return ACCEPT, "все титаны живы — принимаю бой и иду дальше"
    return PAUSE, "погибли или не найдены на окне результата: " + ", ".join(lost)


# ---------------------------------------------------------------------------
# Двери
# ---------------------------------------------------------------------------
def door_choice(elements, order, is_forbidden, heals=None, danger=None):
    """Какую дверь выбрать. elements — стихии дверей на экране; order — порядок стихий (door_order);
    is_forbidden(стихия) — дверь под запретом правил skip.
    С задачи 9б и здоровье титанов (когда дверей больше одной):
      heals(стихия) — правило отхила, которое сработает за этой дверью ("" — никакое): туда идём первыми;
      danger(стихия) — чем стихия опасна для раненых ("" — не опасна): такую дверь пропускаем, если есть другая.
    Возвращает (номер двери в elements, разрешена ли она, стихии запрещённых дверей, пояснение для лога —
    пустое, если выбрана просто первая по порядку). Все двери под запретом — берётся первая по порядку."""
    rank = {room: i for i, room in enumerate(order)}
    by_priority = sorted(range(len(elements)), key=lambda i: rank.get(elements[i], 99))
    allowed = [i for i in by_priority if not is_forbidden(elements[i])]
    banned = [elements[i] for i in by_priority if i not in allowed]
    if not allowed:
        return by_priority[0], False, banned, ""
    first = allowed[0]
    if len(allowed) > 1:
        risk = {i: (danger(elements[i]) if danger else "") for i in allowed}
        for i in allowed:
            rule = heals(elements[i]) if heals else ""
            if rule and not risk[i]:
                note = "" if i == first else f"за дверью {elements[i].upper()} лечат раненого ({rule})"
                return i, True, banned, note
        safe = [i for i in allowed if not risk[i]]
        if safe and safe[0] != first:
            return safe[0], True, banned, f"{elements[first].upper()} опасна ({risk[first]})"
    return first, True, banned, ""


def pick_door(elements, order, is_forbidden):
    """Дверь только по порядку и правилам skip: (номер двери, разрешена ли, запрещённые стихии)."""
    return door_choice(elements, order, is_forbidden)[:3]


# ---------------------------------------------------------------------------
# «Золотые правила» (задача 9б)
# ---------------------------------------------------------------------------
def golden_packs(history, settings=None):
    """Паки, которые много раз побеждали этот состав врагов: не меньше GOLDEN_MIN_BATTLES боёв против него
    и не меньше GOLDEN_MIN_WINRATE% побед — как кнопка во вкладке «Аналитика».
    Ваши запасные паки (settings.backup_teams) не берутся: они для помощи, а не на каждый бой (сессия 07, пак с Молохом).
    Бои паков отхила, которые бот собрал сам (heal_for, задача 9в), тоже: такой пак нужен, только пока титан ранен.
    Возвращает [{"room", "enemies", "team", "wins", "battles", "avg_hp"}]."""
    backups = {room: [sorted(p) for p in packs] for room, packs in (settings.backup_teams if settings else {}).items()}
    groups = {}
    for e in history.entries:
        room, enemies, team = e.get("room"), e.get("enemies") or [], e.get("team") or []
        if not room or room == "unknown" or not enemies or not team or e.get("action") not in ("SUCCESS", "ROLLBACK"):
            continue
        if e.get("heal_for"):
            continue
        g = groups.setdefault((room, tuple(sorted(enemies)), tuple(sorted(team))), {"wins": 0, "battles": 0, "hp": []})
        g["battles"] += 1
        if e["action"] == "SUCCESS":
            g["wins"] += 1
            g["hp"].append(_avg_hp(e, team))
    result = []
    for (room, enemies, team), g in groups.items():
        if list(team) in backups.get(room, []):
            continue
        if g["battles"] >= GOLDEN_MIN_BATTLES and g["wins"] * 100 >= GOLDEN_MIN_WINRATE * g["battles"]:
            result.append({"room": room, "enemies": list(enemies), "team": list(team), "wins": g["wins"],
                           "battles": g["battles"], "avg_hp": sum(g["hp"]) / len(g["hp"]) if g["hp"] else 0.0})
    return result
