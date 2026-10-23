# Тесты задачи 15, шаг 5в: тумблер правила «вкл/выкл» (единственная правка бота в задаче 15).
# Правило с пометкой enabled: false бот пропускает везде, где выбирает пак, дверь и запасной пак; правила без пометки
# включены, как раньше. Выключенные правила бот не трогает (ваш ответ): обучение обновляет только включённые,
# пак выключенного правила не запоминает, «золотое правило» против тех же врагов не добавляет.
import importlib
import sys

import pytest
import yaml

import data_paths

E = ["avalon", "eden", "verdok", "nova", "araji"]
BASE = ["hyperion", "rigel", "iyari", "lumira", "amon"]
HEAL = ["araji", "hyperion", "rigel", "iyari", "lumira"]
SIGURD_HEAL = ["hyperion", "araji", "sigurd", "iyari", "lumira"]
ANTI = ["sigurd", "nova", "mairi", "rigel", "amon"]
OTHER = ["tidus", "orm", "rigel", "iyari", "amon"]

HEAL_RULE = {"name": "Отхил Араджи", "condition": {"titan_hp_below": {"araji": 50}}, "team": HEAL}
ANTI_RULE = {"name": "Против Эдема", "condition": {"enemies_contain": ["eden"]}, "team": ANTI}
SKIP_RULE = {"name": "Араджи при смерти", "condition": {"titan_hp_below": {"araji": 20}}, "team": [], "action": "skip"}


def off(rule):
    return dict(rule, enabled=False)


@pytest.fixture(autouse=True)
def fresh_process_state():
    data_paths._CHECKED.clear()
    yield
    data_paths._CHECKED.clear()


@pytest.fixture
def make_engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "profile.yml").write_text("global_thresholds:\n  max_hp_delta: 30\n", encoding="utf-8")
    folder = tmp_path / "bot_data" / "rules"
    folder.mkdir(parents=True)

    def make(rules, room="mix", default_team=BASE):
        (folder / f"{room}.yml").write_text(yaml.dump({"default_team": default_team, "rules": rules},
                                                      allow_unicode=True, sort_keys=False), encoding="utf-8")
        sys.modules.pop("rules_engine", None)
        return importlib.import_module("rules_engine").RulesEngine()
    yield make
    sys.modules.pop("rules_engine", None)


def saved_rules(tmp_path, room="mix"):
    return yaml.safe_load((tmp_path / "bot_data" / "rules" / f"{room}.yml").read_text(encoding="utf-8"))["rules"]


def test_rules_without_mark_work_as_before(make_engine):
    engine = make_engine([HEAL_RULE, ANTI_RULE, dict(SKIP_RULE, enabled=True)])
    assert engine.battle_decision("mix", E, {"araji": {"hp": 40}})["team"] == HEAL
    assert engine.battle_decision("mix", E, {})["team"] == ANTI
    assert engine.is_room_forbidden("mix", {"araji": {"hp": 10}})
    assert engine.forbidden_titans("mix", E, {"araji": {"hp": 10}}) == {"araji"}


def test_switched_off_rescue_and_anti_pack_are_skipped(make_engine):
    engine = make_engine([off(HEAL_RULE), off(ANTI_RULE)])
    d = engine.battle_decision("mix", E, {"araji": {"hp": 40}})
    assert d["team"] == BASE and d["condition"] == {}
    assert engine.room_packs("mix") == [(BASE, {})]          # запасным паком тоже не берётся
    assert ANTI not in engine.all_packs()                    # и титаны выключенного правила — не «ваши»
    assert engine.heal_rule_for("mix", {"araji": {"hp": 40}}, {"rigel", "lumira"}) == ""
    # Правило отхила, выключенное, не делает бой «плохим» (battle_verdict)
    assert engine.rescue_rules_fired_by_battle("mix", E, {"araji": {"hp": 80}}, {"araji": {"hp": 40}}, {"araji"}) == ""


def test_switched_on_again_works(make_engine):
    engine = make_engine([dict(HEAL_RULE, enabled=True)])
    assert engine.battle_decision("mix", E, {"araji": {"hp": 40}})["team"] == HEAL
    assert engine.heal_rule_for("mix", {"araji": {"hp": 40}}, {"rigel", "lumira"}) == "Отхил Араджи"
    assert engine.rescue_rules_fired_by_battle("mix", E, {"araji": {"hp": 80}}, {"araji": {"hp": 40}},
                                               {"araji"}) == "Отхил Араджи"


def test_switched_off_skip_does_not_forbid(make_engine):
    engine = make_engine([off(SKIP_RULE), HEAL_RULE])
    assert not engine.is_room_forbidden("mix", {"araji": {"hp": 10}})
    assert engine.forbidden_titans("mix", E, {"araji": {"hp": 10}}) == set()
    assert engine.battle_decision("mix", E, {"araji": {"hp": 10}})["team"] == HEAL   # Араджи не в чёрном списке


def test_next_rule_wins_when_first_is_off(make_engine):
    engine = make_engine([off(dict(ANTI_RULE, team=OTHER)), ANTI_RULE])
    assert engine.battle_decision("mix", E, {})["team"] == ANTI


def test_start_line_lists_switched_off_rules(make_engine, capsys):
    make_engine([off(HEAL_RULE), ANTI_RULE])
    out = capsys.readouterr().out
    assert "[ПРАВИЛА] Выключено правил: 1" in out and "Смешанная: 'Отхил Араджи'" in out
    make_engine([HEAL_RULE])
    assert "[ПРАВИЛА]" not in capsys.readouterr().out


def test_learning_skips_pack_of_switched_off_rule(make_engine, tmp_path, capsys):
    """Пак выключенного правила с тем же условием бот не запоминает и правило не включает."""
    learned = {"name": "Анти-пак против: ...", "condition": {"enemies_contain": sorted(E)}, "team": SIGURD_HEAL,
               "source": "auto", "enabled": False}
    engine = make_engine([learned, HEAL_RULE])
    before = saved_rules(tmp_path)
    assert engine.learn_new_rule("mix", E, list(reversed(SIGURD_HEAL)), source="auto") is None
    assert "выключенном правиле" in capsys.readouterr().out
    assert saved_rules(tmp_path) == before
    assert engine.battle_decision("mix", E, {})["team"] == BASE


def test_learning_adds_new_rule_above_switched_off_one(make_engine, tmp_path):
    """Другой пак с тем же условием: новое правило сверху и включено, выключенное остаётся как было.
    Следующее обучение обновляет включённое, а не выключенное."""
    learned = {"name": "Анти-пак против: ...", "condition": {"enemies_contain": sorted(E)}, "team": SIGURD_HEAL,
               "source": "auto", "enabled": False}
    engine = make_engine([learned, HEAL_RULE])
    rule = engine.learn_new_rule("mix", E, ANTI, source="auto")
    rules = saved_rules(tmp_path)
    assert rules[0] == rule and rules[0]["team"] == ANTI and "enabled" not in rules[0]
    assert rules[1] == learned
    assert engine.battle_decision("mix", E, {})["team"] == ANTI
    engine.learn_new_rule("mix", E, OTHER, source="auto")
    rules = saved_rules(tmp_path)
    assert [r["team"] for r in rules] == [OTHER, SIGURD_HEAL, HEAL]
    assert rules[1] == learned


def test_golden_rule_not_added_against_switched_off_rule(make_engine, tmp_path):
    """Выключенное правило против этих врагов считается: иначе выключенное «золотое» возвращалось бы при каждом запуске."""
    golden = {"name": "Золотое правило против: ...", "condition": {"enemies_contain": sorted(E)}, "team": ANTI,
              "source": "golden", "enabled": False}
    engine = make_engine([golden])
    assert engine.add_golden_rule("mix", E, OTHER, 9, 10, 80) is None
    assert saved_rules(tmp_path) == [golden]
