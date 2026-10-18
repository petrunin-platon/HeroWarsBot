# Тесты задачи 3: оценка боя без ложного окна SOS после отхила.
# Данные взяты из сессии 18.10.2026 (комнаты 55 и 112) и из rules/*.yml.
import importlib
import os
import sys

import pytest

import data_paths
from battle_verdict import evaluate_battle

# Пороги из профиля пользователя (profile.yml.bak)
CRITICAL_HP = 30
MAX_DELTA = 60

MIX_RULES = """\
rules:
- name: Авто-отхил (araji < 50%)
  condition:
    titan_hp_below:
      araji: 50
  team: [araji, hyperion, rigel, iyari, lumira]
- name: Авто-отхил (araji < 65%)
  condition:
    titan_hp_below:
      araji: 65
  team: [hyperion, araji, sigurd, iyari, lumira]
  allowed_delta: 62
- name: Просадка Ригеля
  condition:
    titan_hp_below:
      rigel: 35
  team: [rigel, iyari, lumira, hyperion, sigurd]
- name: Не пускать Сигурда
  condition:
    titan_hp_below:
      sigurd: 50
  team: []
  action: skip
default_team: [hyperion, rigel, iyari, lumira, amon]
"""

EARTH_RULES = """\
rules:
- name: Заряд Ангуса
  condition:
    titan_energy_below:
      angus: 97
  team: [STOP]
default_team: [angus, avalon, eden, silva, verdok]
"""


@pytest.fixture(autouse=True)
def fresh_process_state():
    data_paths._CHECKED.clear()
    yield
    data_paths._CHECKED.clear()


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """Движок правил в пустой папке: настоящие profile.yml и bot_data/ не трогаем."""
    monkeypatch.chdir(tmp_path)
    for name, text in (("mix", MIX_RULES), ("earth", EARTH_RULES)):
        path = tmp_path / "bot_data" / "rules" / f"{name}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    sys.modules.pop("rules_engine", None)
    module = importlib.import_module("rules_engine")
    yield module.RulesEngine()
    sys.modules.pop("rules_engine", None)


def state(**hp):
    return {t: {"hp": v, "energy": 0} for t, v in hp.items()}


def status(**hp):
    return {t: {"hp": v, "energy": 50, "status": "ЖИВ"} for t, v in hp.items()}


def judge(engine, room, pack, before, after_hp, delta=MAX_DELTA, enemies=("avalon", "eden")):
    return evaluate_battle(
        pack, status(**after_hp), before, CRITICAL_HP, delta,
        engine=engine, room=room, enemies=list(enemies),
    )


def test_room_55_heal_win_is_not_bad(engine):
    """Комната 55: Араджи 48 → 100, Ригель 55. Раньше был ложный SOS."""
    before = state(araji=48, hyperion=100, rigel=100, iyari=100, lumira=100)
    pack = ["araji", "hyperion", "rigel", "iyari", "lumira"]
    result = judge(engine, "mix", pack, before,
                   dict(araji=100, hyperion=100, rigel=55, iyari=100, lumira=100))
    assert not result["bad"], result["reason"]
    assert result["max_loss"] == 45
    assert result["after_state"]["araji"]["hp"] == 100


def test_room_112_big_loss_is_bad(engine):
    """Комната 112: Ияри потеряла 62% при допуске 60% — окно SOS."""
    before = state(araji=49, hyperion=100, rigel=100, iyari=100, lumira=100)
    pack = ["araji", "hyperion", "rigel", "iyari", "lumira"]
    result = judge(engine, "mix", pack, before,
                   dict(araji=56, hyperion=59, rigel=81, iyari=38, lumira=44))
    assert result["bad"]
    assert "IYARI" in result["reason"] and "62" in result["reason"]
    assert result["max_loss"] == 62


def test_angus_low_energy_after_win_is_not_bad(engine):
    """Ангус с энергией 90% после победы: правило «энергия < 97 → STOP» откат не вызывает."""
    pack = ["angus", "avalon", "eden", "silva", "verdok"]
    result_status = status(angus=100, avalon=100, eden=100, silva=100, verdok=100)
    result_status["angus"]["energy"] = 90
    result = evaluate_battle(pack, result_status, {}, CRITICAL_HP, MAX_DELTA,
                             engine=engine, room="earth", enemies=["sigurd", "nova"])
    assert not result["bad"], result["reason"]
    assert result["after_state"]["angus"]["energy"] == 90
    # А перед следующим боем это правило по-прежнему останавливает бота
    team, _, _, _ = engine.get_battle_decision("earth", [], result["after_state"])
    assert team == ["STOP"]


def test_dead_titan_is_bad(engine):
    before = state(hyperion=100, rigel=100, iyari=100, lumira=100, amon=100)
    result = judge(engine, "mix", list(before), before,
                   dict(hyperion=100, rigel=0, iyari=100, lumira=100, amon=100))
    assert result["bad"] and "RIGEL" in result["reason"]


def test_missing_icon_counts_as_dead(engine):
    """Нет данных по титану — как раньше, ХП = 0 и бой плохой."""
    before = state(hyperion=100, rigel=100)
    result = evaluate_battle(["hyperion", "rigel"], status(hyperion=100), before,
                             CRITICAL_HP, MAX_DELTA, engine=engine, room="mix", enemies=[])
    assert result["bad"] and "RIGEL" in result["reason"]


def test_below_panic_threshold_is_bad(engine):
    before = state(hyperion=60, rigel=100, iyari=100, lumira=100, amon=100)
    result = judge(engine, "mix", list(before), before,
                   dict(hyperion=25, rigel=100, iyari=100, lumira=100, amon=100))
    assert result["bad"] and "Критический порог" in result["reason"]


def test_absent_titan_is_skipped(engine):
    before = state(hyperion=100, rigel=100)
    statuses = status(hyperion=100)
    statuses["rigel"] = {"hp": 0, "energy": 0, "status": "ОТСУТСТВУЕТ"}
    result = evaluate_battle(["hyperion", "rigel"], statuses, before, CRITICAL_HP, MAX_DELTA,
                             engine=engine, room="mix", enemies=[])
    assert not result["bad"]
    assert "rigel" not in result["after_state"]


def test_own_allowed_delta_of_rule_is_used(engine):
    before = state(hyperion=100, rigel=100, iyari=100, lumira=100, amon=100)
    after = dict(hyperion=100, rigel=100, iyari=100, lumira=100, amon=60)
    assert not judge(engine, "mix", list(before), before, after)["bad"]
    assert judge(engine, "mix", list(before), before, after, delta=30)["bad"]


def test_new_heal_rule_trigger_after_battle_is_bad(engine):
    """Ригель дрался, до боя 100%, после 33% — правило «rigel < 35» сработало из-за боя."""
    before = state(hyperion=100, rigel=100, iyari=100, lumira=100, amon=100)
    result = judge(engine, "mix", list(before), before,
                   dict(hyperion=100, rigel=33, iyari=100, lumira=100, amon=100), delta=90)
    assert result["bad"] and "Просадка Ригеля" in result["reason"]


def test_heal_rule_already_active_before_battle_is_not_bad(engine):
    """Ригель был 30% и остался 32% — это не просадка из-за боя."""
    before = state(hyperion=100, rigel=30, iyari=100, lumira=100, amon=100)
    result = judge(engine, "mix", list(before), before,
                   dict(hyperion=100, rigel=32, iyari=100, lumira=100, amon=100))
    assert not result["bad"], result["reason"]


def test_heal_rule_of_titan_who_did_not_fight_is_ignored(engine):
    """Правило про Араджи, а Араджи в бою не было — оно на итог боя не влияет."""
    before = state(hyperion=100, rigel=100, iyari=100, lumira=100, amon=100)
    after_state = dict(before)
    after_state["araji"] = {"hp": 40, "energy": 0}
    fired = engine.rescue_rules_fired_by_battle(
        "mix", [], before, after_state, {"hyperion", "rigel", "iyari", "lumira", "amon"})
    assert fired == ""


def test_skip_rule_does_not_make_battle_bad(engine):
    """Сигурд упал до 45% (правило skip «sigurd < 50»): бой хороший, дверь будет пропущена позже."""
    before = state(hyperion=100, sigurd=100, tidus=100, nova=100, mairi=100)
    result = judge(engine, "mix", list(before), before,
                   dict(hyperion=100, sigurd=45, tidus=100, nova=100, mairi=100))
    assert not result["bad"], result["reason"]


def test_next_room_after_heal_uses_base_pack(engine):
    """После удачного отхила (Араджи 100%) в следующей смешанной комнате обычный пак без вопросов."""
    team, reason, _, _ = engine.get_battle_decision(
        "mix", [], state(araji=100, hyperion=100, rigel=55, iyari=100, lumira=100))
    assert team == ["hyperion", "rigel", "iyari", "lumira", "amon"]
    assert "Базовый" in reason


def test_learned_rule_has_no_own_allowed_delta(engine):
    """Новое правило после отката не получает свой допуск (раньше туда попадала потеря из неудачного боя)."""
    engine.learn_new_rule("mix", ["avalon", "eden"], ["hyperion", "araji", "sigurd", "iyari", "lumira"],
                          before_state={"araji": 49, "hyperion": 100})
    new_rule = engine.rules_cache["mix"]["rules"][0]
    assert new_rule["name"] == "Авто-отхил (araji < 65%)"
    assert "allowed_delta" not in new_rule
