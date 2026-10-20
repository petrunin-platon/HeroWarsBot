# Тесты задачи 12: земля автобоем — ручная ульта Ангуса только при включённом переключателе.
import importlib
import sys

import pytest
import yaml

EARTH = ["angus", "avalon", "eden", "silva", "verdok"]
ENEMIES = ["angus", "avalon", "eden"]
# Правило, которое бот раньше запоминал сам: с пометкой special_ult: angus
OLD_RULE = {"name": "Анти-пак против: Ангус, Авалон, Эдем", "condition": {"enemies_contain": ENEMIES},
            "team": ["angus", "avalon", "eden", "silva", "pallant"], "special_ult": "angus", "source": "auto"}


def make_engine(tmp_path, monkeypatch, manual):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "profile.yml").write_text(f"settings:\n  angus_manual_control: {str(manual).lower()}\n", encoding="utf-8")
    path = tmp_path / "bot_data" / "rules" / "earth.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump({"default_team": EARTH, "rules": [OLD_RULE]}, allow_unicode=True), encoding="utf-8")
    sys.modules.pop("rules_engine", None)
    return importlib.import_module("rules_engine").RulesEngine()


@pytest.fixture(autouse=True)
def clean_modules():
    yield
    sys.modules.pop("rules_engine", None)


def test_switch_off_means_auto_battle_everywhere(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, monkeypatch, manual=False)
    assert engine.battle_decision("earth", [], {})["special_ult"] == "auto"           # базовый пак
    assert engine.battle_decision("earth", ENEMIES, {})["special_ult"] == "auto"      # старое правило с пометкой
    assert engine.special_ult_for(EARTH) == "auto"                                   # ваш пак из окна SOS, запасной
    assert "автобоем" in engine.angus_line()


def test_switch_on_keeps_manual_ult(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, monkeypatch, manual=True)
    assert engine.battle_decision("earth", [], {})["special_ult"] == "angus"
    assert engine.battle_decision("earth", ENEMIES, {})["special_ult"] == "angus"
    assert engine.special_ult_for(EARTH) == "angus"
    assert engine.special_ult_for(["hyperion", "sigurd"]) == "auto"                  # без Ангуса — автобой
    assert "ручная ульта включена" in engine.angus_line()


def test_no_switch_in_profile_means_auto(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("rules_engine", None)
    engine = importlib.import_module("rules_engine").RulesEngine()
    assert engine.special_ult_for(EARTH) == "auto"


def test_new_rules_do_not_get_manual_mark(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, monkeypatch, manual=False)
    engine.learn_new_rule("earth", ["silva", "verdok", "eden"], EARTH, base_condition={})
    engine.add_golden_rule("earth", ["pallant", "verdok"], ["angus", "avalon", "eden", "silva", "pallant"], 5, 5, 90)
    rules = yaml.safe_load((tmp_path / "bot_data" / "rules" / "earth.yml").read_text(encoding="utf-8"))["rules"]
    new = [r for r in rules if r != OLD_RULE]
    assert len(new) == 2 and not any("special_ult" in r for r in new)
