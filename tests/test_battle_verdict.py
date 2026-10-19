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


# --- Задача 9: общие потери пака и личные пороги ---
GROUP = (3, 40)


def test_room_129_group_loss_is_bad(engine):
    """Комната 129 (ваше замечание 128): четверо потеряли 41–54%, каждый в допуске 60% — теперь бой плохой."""
    before = state(hyperion=100, rigel=100, iyari=100, lumira=100, amon=100)
    after = status(hyperion=59, rigel=100, iyari=59, lumira=46, amon=51)
    old = evaluate_battle(list(before), after, before, CRITICAL_HP, MAX_DELTA, engine=engine, room="mix", enemies=[])
    assert not old["bad"]  # без проверки общих потерь бой «нормальный», как было в сессии
    result = evaluate_battle(list(before), after, before, CRITICAL_HP, MAX_DELTA,
                             engine=engine, room="mix", enemies=[], group_loss=GROUP)
    assert result["bad"]
    assert "Большие потери пака" in result["reason"]
    for name in ("HYPERION 41%", "IYARI 41%", "LUMIRA 54%", "AMON 49%"):
        assert name in result["reason"]


def test_room_55_with_group_check_is_still_good(engine):
    """Комната 55: просел только Ригель (45%) — один титан, общие потери в норме."""
    before = state(araji=48, hyperion=100, rigel=100, iyari=100, lumira=100)
    result = evaluate_battle(["araji", "hyperion", "rigel", "iyari", "lumira"],
                             status(araji=100, hyperion=100, rigel=55, iyari=100, lumira=100), before,
                             CRITICAL_HP, MAX_DELTA, engine=engine, room="mix", enemies=[], group_loss=GROUP)
    assert not result["bad"], result["reason"]


def test_group_loss_needs_enough_titans(engine):
    """Двое по 50% при пороге «трое» — бой хороший; healed (ХП выросло) потерей не считается."""
    before = state(araji=40, hyperion=100, rigel=100, iyari=100, lumira=100)
    after = status(araji=100, hyperion=50, rigel=50, iyari=100, lumira=100)
    result = evaluate_battle(list(before), after, before, CRITICAL_HP, MAX_DELTA, group_loss=GROUP)
    assert not result["bad"], result["reason"]


def test_group_loss_can_be_switched_off(engine):
    before = state(hyperion=100, rigel=100, iyari=100, lumira=100, amon=100)
    after = status(hyperion=59, rigel=100, iyari=59, lumira=46, amon=51)
    for off in (None, (0, 40)):
        assert not evaluate_battle(list(before), after, before, CRITICAL_HP, MAX_DELTA, group_loss=off)["bad"]


def test_personal_panic_threshold_replaces_global():
    """Личный порог: Сигурду можно опуститься до 20% (общий 30%), а Ригелю нельзя ниже 25%."""
    before = state(sigurd=100, rigel=100)
    personal = {"sigurd": 19, "rigel": 25}
    ok = evaluate_battle(["sigurd"], status(sigurd=20), before, CRITICAL_HP, 90, titan_critical_hp=personal)
    assert not ok["bad"], ok["reason"]
    bad = evaluate_battle(["rigel"], status(rigel=24), before, CRITICAL_HP, 90, titan_critical_hp=personal)
    assert bad["bad"] and "личный порог: 25%" in bad["reason"]
    # У остальных — общий порог
    other = evaluate_battle(["hyperion"], status(hyperion=29), {}, CRITICAL_HP, 90, titan_critical_hp=personal)
    assert other["bad"] and "порог: 30%" in other["reason"]
