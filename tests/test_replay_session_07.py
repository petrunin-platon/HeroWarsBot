# Задачи 9б и 9в: «повтор» сессии 07 (20.10.2026, 105 комнат) по логу бота tests/data/session_07_bot_log.txt (копия из logs/session_07).
# Ваше замечание (замечания сессии 07):
#  - комната 54: Араджи вошёл в огонь раненым (36%) — правильно поставить Молоха и Вулкана, но не запоминать анти-пак;
#  - комната 74: все здоровы — обычный пак огня, а не пак с Алекто;
#  - комната 104: обычный пак.
# Бои берутся из лога как были; бот решает перед каждой комнатой по новой логике, а дальше получает настоящий итог боя.
import ast
import importlib
import os
import re
import sys

import pytest
import yaml

import data_paths
import tactics
from battle_verdict import evaluate_battle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "tests", "data", "session_07_bot_log.txt")

FIRE_BASE = ["araji", "ignis", "acheron"]
FIRE_MOLOCH = ["araji", "ignis", "acheron", "vulcan", "moloch"]
FIRE_ALECTO = ["araji", "acheron", "ignis", "vulcan", "alecto"]
MIX_BASE = ["hyperion", "rigel", "iyari", "lumira", "amon"]
MIX_HEAL = ["araji", "hyperion", "rigel", "iyari", "lumira"]
MIX_ALECTO = ["hyperion", "rigel", "iyari", "lumira", "alecto"]  # Алекто — запасная (в ваших запасных паках огня)

# Настройки из начала лога сессии 07 (запасные паки огня — в том порядке, в каком бот их брал)
PROFILE = {
    "global_thresholds": {"critical_hp": 30, "max_hp_delta": 60, "group_loss_titans": 3, "group_loss_percent": 40,
                          "titan_critical_hp": {"iyari": 25, "lumira": 30, "rigel": 25, "sigurd": 20}},
    "settings": {"auto_rollback": True, "auto_rollback_tries": 3,
                 "backup_teams": {"fire": [FIRE_MOLOCH, FIRE_ALECTO]}},
}
# Правила, которые видны по логу: отхил Араджи в смешанной (сработал при 55% и 36%, не сработал при 85%)
RULES = {
    "mix": {"rules": [{"name": "Отхил Араджи", "condition": {"titan_hp_below": {"araji": 65}}, "team": MIX_HEAL}],
            "default_team": MIX_BASE},
    "fire": {"rules": [], "default_team": FIRE_BASE},
    "earth": {"rules": [], "default_team": ["angus", "avalon", "eden", "silva", "verdok"]},
    "water": {"rules": [], "default_team": ["hyperion", "sigurd", "tidus", "nova", "mairi"]},
}
# Сессия 06: вы откатили обычный пак огня против Ангуса, Авалона и Эдема (Араджи потерял 39% при допуске 20%)
ROLLBACK_06 = {"timestamp": "2026-10-19 18:00:24", "room": "fire", "enemies": ["angus", "avalon", "eden"],
               "team": FIRE_BASE, "action": "ROLLBACK", "reason": "Превышена Дельта потерь! ARAJI потерял 39% ХП",
               "hp_status": {"araji": {"hp": 61, "energy": 17, "status": "ЖИВ"},
                             "ignis": {"hp": 100, "energy": 79, "status": "ЖИВ"},
                             "acheron": {"hp": 86, "energy": 79, "status": "ЖИВ"}}}


def parse_log(path, date="2026-10-20"):
    """Бои из лога: стихия, враги, пак, ХП после боя, итог (SUCCESS — комната засчитана, ROLLBACK — бот откатил),
    двери, которые видел бот перед входом."""
    battles, enemies, doors, current = [], [], [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.search(r"\[НАВИГАЦИЯ\] Двери \(слева направо\): (.*)", line)
            if m:
                doors = [d.split(" (")[0].lower() for d in m.group(1).split(", ")]
                continue
            m = re.search(r"\[КОМБАТ\] Успешный вход\. Комната: \w+ \| Враги: (\[.*\])", line)
            if m:
                enemies = ast.literal_eval(m.group(1))
                continue
            m = re.search(r"\[ТАКТИКА\] Комната (\w+) \| Пак: (\[.*?\])", line)
            if m:
                current = {"room": m.group(1), "enemies": list(enemies), "team": ast.literal_eval(m.group(2)),
                           "hp_status": {}, "doors": list(doors)}
                continue
            m = re.search(r"---> (\w+): ХП (\d+)%, Энергия (\d+)%", line)
            if m and current is not None:
                current["hp_status"][m.group(1).lower()] = {"hp": int(m.group(2)), "energy": int(m.group(3)),
                                                            "status": "ЖИВ"}
                continue
            if current is not None and "Откатываю бой сам" in line:
                current.update(action="ROLLBACK", timestamp=f"{date} {line[:8]}")
                battles.append(current)
                current = None
                continue
            m = re.search(r"\[СТАТИСТИКА\] Комнат: (\d+)", line)
            if m and current is not None:
                current.update(action="SUCCESS", timestamp=f"{date} {line[:8]}", room_no=int(m.group(1)))
                battles.append(current)
                current = None
    return battles


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_paths._CHECKED.clear()
    (tmp_path / "profile.yml").write_text(yaml.dump(PROFILE), encoding="utf-8")
    for name, rules in RULES.items():
        path = tmp_path / "bot_data" / "rules" / f"{name}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(rules, allow_unicode=True), encoding="utf-8")
    sys.modules.pop("rules_engine", None)
    module = importlib.import_module("rules_engine")
    yield module.RulesEngine()
    sys.modules.pop("rules_engine", None)
    data_paths._CHECKED.clear()


def replay(engine):
    """Как main.py: перед комнатой — дверь и пак (SET_TEAM), после боя — оценка и запись в историю с ХП до боя.
    Возвращает (решения по комнатам, откаты)."""
    s = tactics.Settings(engine.get_global_setting)
    history = tactics.BattleHistory([ROLLBACK_06], s)
    state = {}
    decisions, rollbacks = {}, {}
    rooms, retry = 0, False

    def danger_for(room, enemies):
        return lambda pack: tactics.describe_risks(tactics.wounded_at_risk(room, enemies, pack, state, s, history))

    def heal_for(room, enemies, pack):
        return tactics.heal_plan(room, pack, state, s, history, engine.base_packs(),
                                 forbidden=engine.forbidden_titans(room, enemies, state), enemies=enemies,
                                 special_ult=engine.special_ult_for,
                                 reserve=tactics.own_titans(engine.all_packs(), s))

    for b in parse_log(LOG):
        room_no, room, enemies = rooms + 1, b["room"], b["enemies"]
        if not retry:
            # Дверь (main.py:door_hints): ваше правило отхила или пак отхила, который бот соберёт сам (задача 9в)
            def planned(r):
                choice = engine.battle_decision(r, [], state)
                heal = None if choice["condition"] else heal_for(r, [], choice["team"])
                return (heal[0] if heal else choice["team"]), heal
            heals = lambda r: engine.heal_rule_for(r, state, tactics.HEALERS) or (planned(r)[1] or ("", "", ""))[2]
            danger = lambda r: danger_for(r, [])(planned(r)[0])
            order = tactics.door_order(None)
            idx, _, _, door_note = tactics.door_choice(b["doors"], order, lambda r: False, heals, danger)
            # Пак (main.py, SET_TEAM)
            choice = engine.battle_decision(room, enemies, state)
            pack, condition = choice["team"], choice["condition"]
            # Пак отхила по правилам игры (задача 9в) — вместо базового пака
            heal = None
            if not condition and not history.lost_to(room, enemies, pack):
                heal = heal_for(room, enemies, pack)
                if heal:
                    pack, condition = heal[0], {"titan_hp_below": {heal[1]: s.heal_hp}}
            losing = history.lost_to(room, enemies, pack)
            rescue = tactics.is_rescue_condition(condition)
            risks = [] if losing or rescue else tactics.wounded_at_risk(room, enemies, pack, state, s, history)
            backup = None
            if losing or risks:
                backup, _ = tactics.choose_backup(room, enemies, [pack], state, s, engine.room_packs(room), history,
                                                  forbidden=engine.forbidden_titans(room, enemies, state),
                                                  risky=danger_for(room, enemies), allow_risky=losing)
            decisions[room_no] = {"pack": backup or pack, "losing": losing, "risks": risks, "learn": losing,
                                  "door": b["doors"][idx], "door_note": door_note, "heal": heal}

        before = {t: state[t]["hp"] for t in b["team"] if t in state}
        energy = {t: state[t]["energy"] for t in b["team"] if "energy" in state.get(t, {})}
        verdict = evaluate_battle(b["team"], b["hp_status"], state, s.critical_hp, s.max_hp_delta,
                                  engine=None if retry else engine, room=room, enemies=enemies,
                                  group_loss=s.group_loss, titan_critical_hp=s.titan_critical_hp)
        history.add(dict(b, hp_before=before, energy_before=energy))
        if b["action"] == "ROLLBACK":
            rollbacks[room_no] = {"reason": verdict["reason"], "before": before,
                                  "weak_entry": verdict["bad"] and not s.full_hp_reason(b["team"], b["hp_status"], before)}
            retry = True
            continue
        retry = False
        state.update(verdict["after_state"])
        rooms += 1
    return rooms, decisions, rollbacks, history


def test_session_07_replay(engine):
    rooms, decisions, rollbacks, history = replay(engine)
    assert rooms == 105

    # Комната 54: Араджи 36%, обычно теряет в огне ~29% — Молох и Вулкан сразу, без отката. Правило не запоминается
    d54 = decisions[54]
    assert d54["pack"] == FIRE_MOLOCH and not d54["losing"] and not d54["learn"]
    assert d54["risks"] == [("araji", 36, 29)]
    # Настоящий откат в комнате 54 — из-за раненого Араджи, не из-за врагов: анти-пак не запомнился бы
    assert rollbacks[54]["weak_entry"] and rollbacks[54]["before"]["araji"] == 36
    assert not history.lost_to("fire", ["angus", "silva", "verdok"], FIRE_BASE)

    # Комната 74: все здоровы, откат из сессии 06 по нынешнему допуску (60%) — не поражение. Обычный пак, не Алекто
    d74 = decisions[74]
    assert d74["pack"] == FIRE_BASE and not d74["losing"] and d74["risks"] == []

    # Комната 104 — обычный пак
    assert decisions[104]["pack"] == FIRE_BASE

    # Задача 9в и сессия 08: в комнате 74 по-настоящему стоял пак с Алекто, она ушла с 44% ХП. Тогда Алекто была
    # в ваших запасных паках огня — запасная. Основным (базовые паки) лечение не нужно, поэтому в следующей смешанной
    # (75) бот ставит её вместо Амона. В повторе бои берутся из лога, где её не лечили, — поэтому так в каждой
    # смешанной до конца сессии. В комнатах 40 и 55 Араджи лечит ваше правило, бот его не трогает
    actual = {b["room_no"]: b["team"] for b in parse_log(LOG) if b["action"] == "SUCCESS"}
    rooms_07 = {b["room_no"]: b["room"] for b in parse_log(LOG) if b["action"] == "SUCCESS"}
    healed = {n: d for n, d in decisions.items() if d["heal"]}
    assert sorted(healed) == [n for n, room in sorted(rooms_07.items()) if room == "mix" and n > 74]
    assert all(d["pack"] == MIX_ALECTO and d["heal"][1] == "alecto" and "запасной" in d["heal"][2]
               and "AMON" in d["heal"][2] for d in healed.values())
    assert sorted(decisions[40]["pack"]) == sorted(decisions[55]["pack"]) == sorted(MIX_HEAL)

    # Во всех остальных комнатах пак тот же, что ставил бот в сессии 07
    first_try = {54: FIRE_BASE}   # в комнате 54 первым стоял обычный пак, потом откат
    changed = [n for n, d in decisions.items()
               if sorted(d["pack"]) != sorted(first_try.get(n, actual[n])) and n not in (54, 74) and n not in healed]
    assert changed == []

    # Двери: в сессии 07 раненый Араджи ни разу не встретил выбора «смешанная или нет» и огонь не стоял первым —
    # выбор дверей не меняется
    assert [n for n, d in decisions.items() if d["door_note"]] == []
