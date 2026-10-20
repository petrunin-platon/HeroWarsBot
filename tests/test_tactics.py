# Тесты задачи 9: настройки тактики, история боёв, запасной пак, выбор двери, обучение правил.
import importlib
import sys

import pytest
import yaml

import data_paths
import tactics

E = ["avalon", "eden", "verdok", "nova", "araji"]           # опасный состав врагов в смешанной (сессия B)
OTHER = ["avalon", "verdok", "nova", "araji", "ignis"]
BASE = ["hyperion", "rigel", "iyari", "lumira", "amon"]       # базовый пак смешанной
HEAL = ["araji", "hyperion", "rigel", "iyari", "lumira"]      # отхил Араджи
SIGURD_HEAL = ["hyperion", "araji", "sigurd", "iyari", "lumira"]
RIGEL_HEAL = ["rigel", "iyari", "lumira", "hyperion", "sigurd"]


def settings(**values):
    return tactics.Settings(lambda key, default=None: values.get(key, default))


def battle(team, action="SUCCESS", enemies=E, room="mix", hp=None):
    # Откат по умолчанию — вина врагов: титаны вошли со 100% и упали до 10% (с задачи 9б это важно, см. test_tactics_9b.py)
    hp = (10 if action == "ROLLBACK" else 100) if hp is None else hp
    return {"room": room, "enemies": list(enemies), "team": list(team), "action": action,
            "hp_status": {t: {"hp": hp, "energy": 50, "status": "ЖИВ"} for t in team}}


@pytest.fixture(autouse=True)
def fresh_process_state():
    data_paths._CHECKED.clear()
    yield
    data_paths._CHECKED.clear()


# --- Настройки ---
def test_settings_defaults_keep_old_behaviour():
    s = settings()
    assert s.critical_hp == 40 and s.max_hp_delta == 30
    assert s.group_loss == (3, 40)
    assert s.titan_critical_hp == {}
    assert s.auto_rollback is False          # бот сам не откатывает, пока вы не включите
    assert s.auto_rollback_tries == 2        # запасной пак — до 2 раз за комнату
    assert s.backup_teams == {}
    assert s.door_order == ["water", "mix", "earth", "fire"]


def test_settings_from_profile():
    s = settings(critical_hp=30, max_hp_delta=60, group_loss_titans=2, group_loss_percent=35,
                 titan_critical_hp={"rigel": 25, "sigurd": "19"}, auto_rollback=True, auto_rollback_tries=2,
                 backup_teams={"mix": [SIGURD_HEAL, "плохая запись", []]}, door_order=["mix", "WATER", "lava"])
    assert s.group_loss == (2, 35)
    assert s.titan_critical_hp == {"rigel": 25, "sigurd": 19}
    assert s.panic_hp("rigel") == 25 and s.panic_hp("hyperion") == 30
    assert s.auto_rollback is True and s.auto_rollback_tries == 2
    assert s.backup_teams == {"mix": [SIGURD_HEAL]}
    assert s.door_order == ["mix", "water", "earth", "fire"]
    assert any("Бот решает сам" in line for line in s.describe())


def test_settings_survive_broken_values():
    s = settings(group_loss_titans="три", titan_critical_hp=["rigel"], backup_teams="mix", auto_rollback="да")
    assert s.group_loss == (3, 40)
    assert s.titan_critical_hp == {} and s.backup_teams == {}
    assert s.auto_rollback is False  # включается только словом true


# --- Двери ---
def test_pick_door_follows_order_and_skip_rules():
    order = ["water", "mix", "earth", "fire"]
    assert tactics.pick_door(["fire", "earth"], order, lambda r: False) == (1, True, [])
    # Земля под запретом — идём в огонь
    assert tactics.pick_door(["fire", "earth"], order, lambda r: r == "earth") == (0, True, ["earth"])
    # Все под запретом — первая по порядку
    assert tactics.pick_door(["fire", "earth"], order, lambda r: True) == (1, False, ["earth", "fire"])
    # Свой порядок: огонь раньше земли
    assert tactics.pick_door(["earth", "fire"], ["fire", "earth", "water", "mix"], lambda r: False)[0] == 1
    # Неизвестная дверь — в самом конце
    assert tactics.pick_door(["unknown", "mix"], order, lambda r: False)[0] == 1


# --- История ---
def test_history_stats_and_winners():
    h = tactics.BattleHistory([
        battle(BASE, hp=90), battle(BASE, hp=70), battle(HEAL, "ROLLBACK"),
        battle(SIGURD_HEAL, hp=95), battle(BASE, enemies=OTHER, hp=100), battle(BASE, room="water"),
    ])
    st = h.stats("mix", list(reversed(E)), list(reversed(BASE)))  # порядок не важен
    assert st["wins"] == 2 and st["fails"] == 0 and st["avg_hp"] == 80 and not st["last_failed"]
    assert h.lost_to("mix", E, HEAL)
    assert not h.lost_to("mix", OTHER, HEAL)
    assert [team for team, _ in h.winners("mix", E)] == [SIGURD_HEAL, BASE]


def test_history_last_result_counts():
    """Пак проиграл, потом выиграл — в последний раз он справился, его можно брать."""
    h = tactics.BattleHistory([battle(HEAL, "ROLLBACK"), battle(HEAL)])
    assert not h.lost_to("mix", E, HEAL)


def test_one_loss_does_not_spoil_good_pack():
    """Пак много раз побеждал этих врагов и один раз проиграл — он по-прежнему годится в запасные."""
    h = tactics.BattleHistory([battle(SIGURD_HEAL)] * 3 + [battle(SIGURD_HEAL, "ROLLBACK")])
    assert not h.lost_to("mix", E, SIGURD_HEAL)
    # А выиграл 1 и проиграл 1 (последним) — проигрывает
    h = tactics.BattleHistory([battle(SIGURD_HEAL), battle(SIGURD_HEAL, "ROLLBACK")])
    assert h.lost_to("mix", E, SIGURD_HEAL)


def test_history_loads_jsonl_files(tmp_path):
    (tmp_path / "battle_log_1.jsonl").write_text(
        '{"room": "mix", "enemies": ["a"], "team": ["b"], "action": "SUCCESS", "hp_status": {}}\nне json\n\n',
        encoding="utf-8")
    h = tactics.BattleHistory.load(str(tmp_path))
    assert len(h.entries) == 1


# --- Запасной пак ---
def rule_packs():
    return [(HEAL, {"titan_hp_below": {"araji": 50}}),
            (RIGEL_HEAL, {"titan_hp_below": {"rigel": 35}}),
            (BASE, {})]


def test_backup_user_list_first():
    s = settings(critical_hp=30, backup_teams={"mix": [SIGURD_HEAL]})
    pack, source = tactics.choose_backup("mix", E, [BASE], {}, s, rule_packs(), tactics.BattleHistory())
    assert pack == SIGURD_HEAL and source == tactics.SOURCE_USER


def test_backup_from_rules_prefers_anti_pack_against_these_enemies():
    packs = rule_packs() + [(SIGURD_HEAL, {"enemies_contain": E})]
    pack, source = tactics.choose_backup("mix", E, [HEAL], {}, settings(), packs, tactics.BattleHistory())
    assert pack == SIGURD_HEAL and source == tactics.SOURCE_RULES


def test_backup_from_rules_prefers_pack_that_beat_these_enemies():
    history = tactics.BattleHistory([battle(BASE, hp=90)])
    pack, _ = tactics.choose_backup("mix", E, [HEAL], {}, settings(), rule_packs(), history)
    assert pack == BASE  # побеждал этих врагов, поэтому раньше отхила Ригеля, хоть и ниже в файле


def test_backup_from_history_last():
    history = tactics.BattleHistory([battle(SIGURD_HEAL, hp=93)])
    pack, source = tactics.choose_backup("mix", E, [BASE], {}, settings(), [(BASE, {})], history)
    assert pack == SIGURD_HEAL and source == tactics.SOURCE_HISTORY


def test_backup_skips_failed_forbidden_and_wounded_packs():
    history = tactics.BattleHistory([battle(HEAL, "ROLLBACK")])
    state = {"rigel": {"hp": 20, "energy": 0}}  # Ригель ниже порога паники 30
    s = settings(critical_hp=30)
    # HEAL проиграл этим врагам, в RIGEL_HEAL и BASE раненый Ригель — запасного нет
    assert tactics.choose_backup("mix", E, [], state, s, rule_packs(), history) == (None, None)
    # Без раненого Ригеля, но Сигурд в чёрном списке (skip) — остаётся только BASE
    pack, _ = tactics.choose_backup("mix", E, [], {}, s, rule_packs(), history, forbidden={"sigurd"})
    assert pack == BASE
    # Уже проигравший в этой комнате пак не берётся
    assert tactics.choose_backup("mix", E, [BASE], {}, s, rule_packs(), history, forbidden={"sigurd"}) == (None, None)


def test_backup_never_takes_dead_titan_even_with_zero_threshold():
    s = settings(critical_hp=0)
    state = {"amon": {"hp": 0}}
    assert tactics.choose_backup("mix", E, [], state, s, [(BASE, {})], tactics.BattleHistory()) == (None, None)


def test_auto_rollback_blocker():
    on = settings(auto_rollback=True)
    assert tactics.auto_rollback_blocker(on, False, False, 0) is None
    assert "выключен" in tactics.auto_rollback_blocker(settings(), False, False, 0)
    assert "вручную" in tactics.auto_rollback_blocker(on, True, False, 0)
    assert "не прочиталось" in tactics.auto_rollback_blocker(on, False, True, 0)
    assert tactics.auto_rollback_blocker(on, False, False, 1) is None    # по умолчанию 2 попытки
    assert "уже откатывал" in tactics.auto_rollback_blocker(on, False, False, 2)
    assert "выбрали вы" in tactics.auto_rollback_blocker(on, False, False, 0, user_pack=True)


# --- Обучение правил (rules_engine.learn_new_rule) ---
MIX_RULES = {
    "rules": [
        {"name": "Отхил Араджи", "condition": {"titan_hp_below": {"araji": 50}}, "team": HEAL},
        {"name": "Не пускать Сигурда", "condition": {"titan_hp_below": {"sigurd": 50}}, "team": [], "action": "skip"},
    ],
    "default_team": BASE,
}


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "profile.yml").write_text("global_thresholds:\n  max_hp_delta: 30\n", encoding="utf-8")
    path = tmp_path / "bot_data" / "rules" / "mix.yml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.dump(MIX_RULES, allow_unicode=True), encoding="utf-8")
    sys.modules.pop("rules_engine", None)
    module = importlib.import_module("rules_engine")
    yield module.RulesEngine()
    sys.modules.pop("rules_engine", None)


def saved_rules(tmp_path):
    return yaml.safe_load((tmp_path / "bot_data" / "rules" / "mix.yml").read_text(encoding="utf-8"))["rules"]


def test_decision_reports_rule_condition(engine):
    d = engine.battle_decision("mix", E, {"araji": {"hp": 49}})
    assert d["team"] == HEAL and d["condition"] == {"titan_hp_below": {"araji": 50}}
    assert engine.battle_decision("mix", E, {})["condition"] == {}
    assert engine.get_battle_decision("mix", E, {})[0] == BASE
    assert engine.room_packs("mix") == [(HEAL, {"titan_hp_below": {"araji": 50}}), (BASE, {})]


def test_learned_rule_is_tied_to_enemies_and_situation(engine, tmp_path):
    """Комната 112: отхил Араджи против опасных врагов проиграл, удачный пак — с Сигурдом.
    Новое правило срабатывает только против этих врагов и только когда Араджи ранен."""
    rule = engine.learn_new_rule("mix", E, SIGURD_HEAL, base_condition={"titan_hp_below": {"araji": 50}},
                                 success_loss=24, source="auto")
    assert rule["condition"] == {"titan_hp_below": {"araji": 50}, "enemies_contain": sorted(E)}
    assert rule["name"].startswith("Анти-пак против: ") and "Эдем" in rule["name"] and "Араджи < 50% ХП" in rule["name"]
    assert "allowed_delta" not in rule  # 24% меньше общего допуска 30%
    assert saved_rules(tmp_path)[0]["team"] == SIGURD_HEAL
    # Против этих врагов при раненом Араджи — новый пак
    assert engine.get_battle_decision("mix", E, {"araji": {"hp": 49}})[0] == SIGURD_HEAL
    # Против других врагов — по-прежнему обычный отхил
    assert engine.get_battle_decision("mix", OTHER, {"araji": {"hp": 49}})[0] == HEAL
    # Араджи здоров — против этих врагов базовый пак
    assert engine.get_battle_decision("mix", E, {})[0] == BASE


def test_learned_anti_pack_after_base_pack_lost(engine):
    """Комната 129: проиграл базовый пак — получится анти-пак против этих врагов."""
    rule = engine.learn_new_rule("mix", E, SIGURD_HEAL, base_condition={}, success_loss=45)
    assert rule["condition"] == {"enemies_contain": sorted(E)}
    assert rule["allowed_delta"] == 45  # удачный бой потерял больше общего допуска — у правила свой допуск
    assert engine.get_battle_decision("mix", E, {})[0] == SIGURD_HEAL
    assert engine.get_battle_decision("mix", OTHER, {})[0] == BASE


def test_same_situation_updates_rule_instead_of_duplicate(engine, tmp_path):
    engine.learn_new_rule("mix", E, RIGEL_HEAL)
    engine.learn_new_rule("mix", list(reversed(E)), SIGURD_HEAL)   # то же условие, другой пак
    rules = saved_rules(tmp_path)
    learned = [r for r in rules if "enemies_contain" in r["condition"]]
    assert len(learned) == 1 and learned[0]["team"] == SIGURD_HEAL
    assert rules[0]["team"] == SIGURD_HEAL  # обновлённое правило — первое
    # Тот же пак ещё раз — правило не дублируется
    engine.learn_new_rule("mix", E, list(reversed(SIGURD_HEAL)))
    assert len(saved_rules(tmp_path)) == len(rules)
    # Старые правила на месте
    assert any(r.get("action") == "skip" for r in saved_rules(tmp_path))


def test_no_rule_without_enemies(engine, tmp_path):
    assert engine.learn_new_rule("mix", [], SIGURD_HEAL) is None
    assert len(saved_rules(tmp_path)) == 2


def test_history_empty_pack_matches_nothing():
    h = tactics.BattleHistory([battle(HEAL, "ROLLBACK")])
    assert not h.lost_to("mix", E, [])
    assert h.stats("mix", E, [])["wins"] == 0 and h.stats("mix", E, [])["fails"] == 0


def test_tries_are_limited():
    assert settings(auto_rollback_tries=10).auto_rollback_tries == 3   # не по 10 раз
    assert settings(auto_rollback_tries=0).auto_rollback_tries == 1


def test_read_and_write_tactics_keep_other_profile_keys():
    """Окно программы читает и пишет настройки тактики, не трогая остальное (Telegram, цели)."""
    profile = {"global_thresholds": {"critical_hp": 30, "max_hp_delta": 20},
               "settings": {"target_time": 50, "telegram": {"active": True}}}
    values = tactics.read_tactics(profile)
    assert values == {"auto_rollback": False, "auto_rollback_tries": 2, "group_loss_titans": 3,
                      "group_loss_percent": 40, "titan_critical_hp": {}, "backup_teams": {},
                      "door_order": ["water", "mix", "earth", "fire"], "sos_timeout_minutes": 10,
                      "heal_below_hp": 60, "heal_remove_order": []}
    values.update(auto_rollback=True, auto_rollback_tries=3, titan_critical_hp={"rigel": 25},
                  backup_teams={"mix": [SIGURD_HEAL]}, door_order=["mix", "water", "earth", "fire"])
    tactics.write_tactics(profile, values)
    assert profile["settings"]["telegram"] == {"active": True} and profile["settings"]["target_time"] == 50
    assert profile["global_thresholds"]["critical_hp"] == 30
    assert profile["global_thresholds"]["titan_critical_hp"] == {"rigel": 25}
    assert profile["settings"]["auto_rollback"] is True
    again = tactics.read_tactics(profile)
    assert again["backup_teams"] == {"mix": [SIGURD_HEAL]} and again["auto_rollback_tries"] == 3
    assert again["door_order"][0] == "mix"
    assert tactics.Settings(tactics.profile_getter(profile)).auto_rollback is True


def test_write_tactics_into_empty_profile():
    profile = tactics.write_tactics({}, {"auto_rollback": True, "group_loss_titans": 2, "чужой_ключ": 1})
    assert profile == {"global_thresholds": {"group_loss_titans": 2}, "settings": {"auto_rollback": True}}


def test_obsolete_rule_is_removed_once(tmp_path, monkeypatch):
    """Старое правило «Авто-отхил (araji < 65%)» с Ригелем и допуском 6% бот удаляет сам; остальные остаются."""
    monkeypatch.chdir(tmp_path)
    old_rule = {"team": ["araji", "hyperion", "rigel", "iyari", "lumira"], "stats": {"wins": 0, "fails": 0},
                "condition": {"titan_hp_below": {"araji": 65}}, "name": "Авто-отхил (araji < 65%)", "allowed_delta": 6}
    sigurd_rule = {"team": SIGURD_HEAL, "condition": {"titan_hp_below": {"araji": 65}},
                   "name": "Авто-отхил (araji < 65%)", "allowed_delta": 62}
    same_pack_other_delta = dict(old_rule, allowed_delta=20)
    path = tmp_path / "bot_data" / "rules" / "mix.yml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.dump({"rules": [old_rule, sigurd_rule, same_pack_other_delta], "default_team": BASE},
                              allow_unicode=True), encoding="utf-8")
    sys.modules.pop("rules_engine", None)
    module = importlib.import_module("rules_engine")
    engine = module.RulesEngine()
    try:
        rules = yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]
        assert [r["team"] for r in rules] == [SIGURD_HEAL, old_rule["team"]]
        assert rules[1]["allowed_delta"] == 20
        assert engine.get_battle_decision("mix", E, {"araji": {"hp": 50}})[0] == SIGURD_HEAL
        # Второй запуск ничего не меняет
        before = path.read_text(encoding="utf-8")
        module.RulesEngine()
        assert path.read_text(encoding="utf-8") == before
    finally:
        sys.modules.pop("rules_engine", None)
