# Задача 9, «Готово, когда»: прогон всей сессии B (18.10.2026, 148 боёв) через новую логику.
# История боёв — tests/data/session_B.jsonl (копия logs/battle_log_2026-10-18_13-57-00.jsonl из истории git).
# Ожидаем: в комнате 55 окна нет (удачный отхил), в комнатах 112 и 129 бой плохой, и бот находит запасной пак.
import importlib
import json
import os
import sys

import pytest
import yaml

import data_paths
import tactics
from battle_verdict import evaluate_battle

DATA = os.path.join(os.path.dirname(__file__), "data", "session_B.jsonl")

# Профиль на время сессии B (profile.yml.bak): порог паники 30%, допуск 60%; общие потери — 3 титана по 40%
PROFILE = {"global_thresholds": {"critical_hp": 30, "max_hp_delta": 60},
           "settings": {"auto_rollback": True}}

# Правила смешанной и огненной комнат на начало сессии B (из истории git)
MIX = {
    "rules": [
        {"name": "Auto Rule", "condition": {"titan_hp_below": {"sigurd": 50}}, "team": [], "action": "skip"},
        {"name": "Auto Rule", "condition": {"titan_hp_below": {"rigel": 35}},
         "team": ["rigel", "iyari", "lumira", "hyperion", "sigurd"]},
        {"name": "Auto Rule", "condition": {"titan_hp_below": {"moloch": 40}},
         "team": ["moloch", "rigel", "iyari", "lumira", "hyperion"]},
        {"name": "Auto Rule", "condition": {"titan_hp_below": {"araji": 50}},
         "team": ["araji", "hyperion", "rigel", "iyari", "lumira"]},
    ],
    "default_team": ["hyperion", "rigel", "iyari", "lumira", "amon"],
}
FIRE = {
    "rules": [{"name": "Auto Rule", "condition": {"titan_hp_below": {"araji": 35}},
               "team": ["araji", "ignis", "acheron", "vulcan", "moloch"]}],
    "default_team": ["araji", "ignis", "acheron"],
}
EARTH = {"rules": [], "default_team": ["angus", "avalon", "eden", "silva", "verdok"]}
WATER = {"rules": [], "default_team": ["hyperion", "sigurd", "tidus", "nova", "mairi"]}

SIGURD_HEAL = ["hyperion", "araji", "sigurd", "iyari", "lumira"]


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_paths._CHECKED.clear()
    (tmp_path / "profile.yml").write_text(yaml.dump(PROFILE), encoding="utf-8")
    for name, rules in (("mix", MIX), ("fire", FIRE), ("earth", EARTH), ("water", WATER)):
        path = tmp_path / "bot_data" / "rules" / f"{name}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(rules, allow_unicode=True), encoding="utf-8")
    sys.modules.pop("rules_engine", None)
    module = importlib.import_module("rules_engine")
    yield module.RulesEngine()
    sys.modules.pop("rules_engine", None)
    data_paths._CHECKED.clear()


def load_session():
    with open(DATA, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def replay(engine):
    """Прогоняет бои по порядку, как main.py в WAIT_FOR_OK. Возвращает {номер комнаты: решение}."""
    s = tactics.Settings(engine.get_global_setting)
    history = tactics.BattleHistory()
    state = {}
    rooms = 0
    decisions = {}
    testing = False  # после отката проверяется новый пак — по правилам отхила он не судится

    for entry in load_session():
        room_no = rooms + 1
        pack = entry["team"]
        verdict = evaluate_battle(pack, entry["hp_status"], state, s.critical_hp, s.max_hp_delta,
                                  engine=None if testing else engine, room=entry["room"], enemies=entry["enemies"],
                                  group_loss=s.group_loss, titan_critical_hp=s.titan_critical_hp)
        if verdict["bad"]:
            backup, source = tactics.choose_backup(
                entry["room"], entry["enemies"], [pack], state, s, engine.room_packs(entry["room"]), history,
                forbidden=engine.forbidden_titans(entry["room"], entry["enemies"], state))
            decisions[room_no] = {"reason": verdict["reason"], "backup": backup, "source": source, "pack": pack}

        if entry["action"] == "ROLLBACK":
            testing = True
            history.add(entry)
            continue

        if testing:
            # Комната 112: вы подтвердили пак с Сигурдом — бот запоминает его так же, как теперь (против этих врагов)
            engine.learn_new_rule(entry["room"], entry["enemies"], pack,
                                  base_condition={"titan_hp_below": {"araji": 50}}, success_loss=verdict["max_loss"])
            testing = False
        history.add(entry)
        state.update(verdict["after_state"])
        rooms += 1
    return rooms, decisions


def test_session_b_replay(engine):
    rooms, decisions = replay(engine)
    assert rooms == 147

    # Плохие бои — только 112 и 129 (ваше замечание 128). В комнате 55 окна нет
    assert sorted(decisions) == [112, 129], {k: v["reason"] for k, v in decisions.items()}
    assert 55 not in decisions

    # 112: отхил Араджи против Авалон, Эдем, Вердок, Нова, Араджи. Ияри потеряла 62% (допуск 60%)
    room_112 = decisions[112]
    assert "IYARI" in room_112["reason"]
    # Запасной пак — базовый микс: он уже побеждал этих врагов в этой сессии
    assert room_112["backup"] == ["hyperion", "rigel", "iyari", "lumira", "amon"]
    assert room_112["source"] == tactics.SOURCE_RULES

    # 129: базовый микс, четверо потеряли 41–54% — плохой бой по общим потерям
    room_129 = decisions[129]
    assert "Большие потери пака" in room_129["reason"]
    # Запасной пак — правило, запомненное в комнате 112 (против этих врагов, пак с Сигурдом)
    assert sorted(room_129["backup"]) == sorted(SIGURD_HEAL)
    assert room_129["source"] == tactics.SOURCE_RULES
