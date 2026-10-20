# Тесты задачи 9б: кто виноват в плохом бое, история с ХП до боя, прогноз потерь раненых, выбор двери по здоровью,
# решение без вас (окно SOS без ответа), «золотые правила».
import importlib
import json
import sys

import pytest
import yaml

import data_paths
import tactics
from battle_verdict import full_hp_reason

FIRE_BASE = ["araji", "ignis", "acheron"]
FIRE_MOLOCH = ["araji", "ignis", "acheron", "vulcan", "moloch"]
FIRE_ALECTO = ["araji", "acheron", "ignis", "vulcan", "alecto"]
E54 = ["angus", "silva", "verdok"]
E74 = ["angus", "avalon", "eden"]
MIX_BASE = ["hyperion", "rigel", "iyari", "lumira", "amon"]
MIX_HEAL = ["araji", "hyperion", "rigel", "iyari", "lumira"]


def settings(**values):
    # Пороги из сессии 07: паника 30%, допуск 60%, общие потери 3 титана по 40%
    values.setdefault("critical_hp", 30)
    values.setdefault("max_hp_delta", 60)
    return tactics.Settings(lambda key, default=None: values.get(key, default))


def hp(**titans):
    return {t: {"hp": v, "energy": 50, "status": "ЖИВ" if v > 0 else "МЕРТВ"} for t, v in titans.items()}


def battle(team, action, status, enemies=E54, room="fire", time="2026-10-20 10:30:00", before=None):
    entry = {"timestamp": time, "room": room, "enemies": list(enemies), "team": list(team), "action": action,
             "hp_status": status}
    if before is not None:
        entry["hp_before"] = before
    return entry


@pytest.fixture(autouse=True)
def fresh_process_state():
    data_paths._CHECKED.clear()
    yield
    data_paths._CHECKED.clear()


# --- Кто виноват: враги или раненый титан ---
def test_weak_entry_is_not_enemies_fault():
    """Комната 54: Араджи вошёл с 36% и упал до 9%. Со 100% осталось бы 73% — враги ни при чём."""
    status = hp(araji=9, ignis=100, acheron=86)
    assert full_hp_reason(FIRE_BASE, status, {"araji": 36}, 30, 60) == ""
    # Тот же бой со 100% до боя — виноваты враги
    assert "ARAJI" in full_hp_reason(FIRE_BASE, status, {}, 30, 60)


def test_full_hp_reason_checks_all_thresholds():
    # Потеря больше допуска
    assert "допуск" in full_hp_reason(["rigel"], hp(rigel=35), {"rigel": 100}, 20, 60)
    # Личный порог паники: Ригель со 100% упал бы до 25% при пороге 30%
    assert "порог 30%" in full_hp_reason(["rigel"], hp(rigel=5), {"rigel": 80}, 20, 90, titan_critical_hp={"rigel": 30})
    # Общие потери: трое потеряли по 40% и больше
    status = hp(hyperion=55, rigel=58, iyari=60, lumira=100, amon=100)
    assert "Большие потери" in full_hp_reason(MIX_BASE, status, {}, 30, 60, group_loss=(3, 40))
    # Погиб, войдя с 36% — враги ни при чём; погиб со 100% — виноваты враги
    assert full_hp_reason(["araji"], hp(araji=0), {"araji": 36}, 30, 60) == ""
    assert full_hp_reason(["araji"], hp(araji=0), {"araji": 100}, 30, 60) != ""
    # Не найден на окне результата — не судим
    assert full_hp_reason(["araji"], {"araji": {"hp": 0, "status": "ОТСУТСТВУЕТ"}}, {}, 30, 60) == ""


# --- История: ХП до боя и поражения только по вине врагов ---
def test_history_restores_hp_before_for_old_records():
    """В старых записях нет hp_before: ХП до боя — после последней удачной битвы в тот же игровой день."""
    h = tactics.BattleHistory([
        battle(FIRE_BASE, "SUCCESS", hp(araji=36, ignis=100, acheron=86), time="2026-10-20 10:52:05"),
        battle(FIRE_BASE, "ROLLBACK", hp(araji=9, ignis=100, acheron=86), time="2026-10-20 10:54:38"),
        battle(FIRE_MOLOCH, "SUCCESS", hp(araji=36, ignis=100, acheron=85, vulcan=100, moloch=81),
               time="2026-10-20 10:55:38"),
        # Новый игровой день (после 05:00) — ХП забыто
        battle(FIRE_BASE, "SUCCESS", hp(araji=80, ignis=100, acheron=100), time="2026-10-21 05:10:00"),
    ], settings())
    assert h.before[1] == {"araji": 36, "ignis": 100, "acheron": 86}
    # Откат бой отменяет: для пака с Молохом Араджи по-прежнему 36%
    assert h.before[2]["araji"] == 36 and "moloch" not in h.before[2]
    assert h.before[3] == {}
    # Сохранённое в записи ХП до боя важнее цепочки
    h.add(battle(FIRE_BASE, "ROLLBACK", hp(araji=10), before={"araji": 40}, time="2026-10-21 05:20:00"))
    assert h.before[4] == {"araji": 40}


def test_weak_entry_rollback_does_not_spoil_pack():
    """Сессия 07: откат в комнате 54 (Араджи вошёл раненым) не делает базовый пак «проигрывающим этим врагам»."""
    h = tactics.BattleHistory([
        battle(FIRE_BASE, "SUCCESS", hp(araji=36, ignis=100, acheron=86), time="2026-10-20 10:52:05"),
        battle(FIRE_BASE, "ROLLBACK", hp(araji=9, ignis=100, acheron=86), time="2026-10-20 10:54:38"),
    ], settings())
    st = h.stats("fire", E54, FIRE_BASE)
    assert st["fails"] == 0 and st["weak_entry"] == 1
    assert not h.lost_to("fire", E54, FIRE_BASE)
    # Если бы Араджи вошёл здоровым и упал до 9% — пак проигрывает этим врагам
    h = tactics.BattleHistory([battle(FIRE_BASE, "ROLLBACK", hp(araji=9, ignis=100, acheron=86), before={"araji": 100})],
                              settings())
    assert h.lost_to("fire", E54, FIRE_BASE)


def test_old_rollback_is_judged_by_current_thresholds():
    """Сессия 06: вы откатили бой (Араджи потерял 39% при допуске 20%). С нынешним допуском 60% бой нормальный,
    поэтому в комнате 74 сессии 07 базовый пак не должен считаться проигрывающим."""
    rollback_06 = battle(FIRE_BASE, "ROLLBACK", hp(araji=61, ignis=100, acheron=86), enemies=E74,
                         time="2026-10-19 18:00:24")
    assert not tactics.BattleHistory([rollback_06], settings()).lost_to("fire", E74, FIRE_BASE)
    # С допуском 20% (как тогда) — проигрывает
    assert tactics.BattleHistory([rollback_06], settings(max_hp_delta=20)).lost_to("fire", E74, FIRE_BASE)


# --- Прогноз потерь раненых ---
MOLOCH_WIN = hp(araji=36, ignis=100, acheron=85, vulcan=100, moloch=81)


def fire_history():
    """Огонь сессии 07: Араджи 85 → 55 (комната 39) и 64 → 36 (комната 49); с Молохом Араджи не теряет ХП."""
    return tactics.BattleHistory([
        battle(FIRE_BASE, "SUCCESS", hp(araji=55, ignis=100, acheron=86), before={"araji": 85}, enemies=E74),
        battle(FIRE_BASE, "SUCCESS", hp(araji=36, ignis=100, acheron=86), before={"araji": 64}),
        battle(FIRE_MOLOCH, "SUCCESS", MOLOCH_WIN, before={"araji": 36}),
        battle(FIRE_MOLOCH, "SUCCESS", MOLOCH_WIN, before={"araji": 36}),
    ], settings())


def test_expected_loss_and_wounded_at_risk():
    h = fire_history()
    assert h.expected_loss("fire", FIRE_BASE, "araji") == 29
    assert h.expected_loss("fire", FIRE_MOLOCH, "araji") == 0
    assert h.expected_loss("fire", FIRE_BASE, "vulcan") is None
    # По одному бою прогноза нет: в сессии 07 Люмира один раз потеряла 45% против сильных врагов, а потом — ничего
    one = tactics.BattleHistory([battle(MIX_HEAL, "SUCCESS", hp(lumira=55), before={"lumira": 100}, room="mix")],
                                settings())
    assert one.expected_loss("mix", MIX_HEAL, "lumira") is None
    s = settings()
    # Араджи 36%: обычно теряет ~29% → 7% < 30% — опасно
    risks = tactics.wounded_at_risk("fire", E54, FIRE_BASE, {"araji": {"hp": 36}}, s, h)
    assert risks == [("araji", 36, 29)]
    assert "ARAJI: 36% ХП" in tactics.describe_risks(risks)
    # Араджи здоров или его ХП неизвестно — не опасно
    assert tactics.wounded_at_risk("fire", E54, FIRE_BASE, {"araji": {"hp": 100}}, s, h) == []
    assert tactics.wounded_at_risk("fire", E54, FIRE_BASE, {}, s, h) == []
    # Араджи 64%: 64 − 29 = 35% — не опасно
    assert tactics.wounded_at_risk("fire", E54, FIRE_BASE, {"araji": {"hp": 64}}, s, h) == []
    # С Молохом Араджи не теряет — не опасно и при 36%
    assert tactics.wounded_at_risk("fire", E54, FIRE_MOLOCH, {"araji": {"hp": 36}}, s, h) == []


def test_rescue_condition():
    assert tactics.is_rescue_condition({"titan_hp_below": {"araji": 50}})
    assert tactics.is_rescue_condition({"titan_energy_below": {"angus": 97}, "enemies_contain": ["nova"]})
    assert not tactics.is_rescue_condition({"enemies_contain": ["nova"]}) and not tactics.is_rescue_condition({})


def test_expected_loss_prefers_same_enemies_when_enough():
    h = tactics.BattleHistory([
        battle(FIRE_BASE, "SUCCESS", hp(araji=90), before={"araji": 100}, enemies=E74),
        battle(FIRE_BASE, "SUCCESS", hp(araji=50), before={"araji": 100}),
        battle(FIRE_BASE, "SUCCESS", hp(araji=60), before={"araji": 100}),
    ], settings())
    assert h.expected_loss("fire", FIRE_BASE, "araji", E54) == 45      # 2 боя с этими врагами — только они
    assert round(h.expected_loss("fire", FIRE_BASE, "araji", E74)) == 33  # 1 бой — берём все: (10 + 50 + 40) / 3


# --- Запасной пак: опасные для раненых паки и причины в лог ---
def test_backup_skips_risky_pack_and_explains():
    moloch_lost = hp(araji=10, ignis=100, acheron=85, vulcan=100, moloch=81)
    h = tactics.BattleHistory([battle(FIRE_MOLOCH, "SUCCESS", moloch_lost, before={"araji": 40})] * 2, settings())
    s = settings(backup_teams={"fire": [FIRE_MOLOCH, FIRE_ALECTO]})
    state = {"araji": {"hp": 36}}
    danger = lambda pack: tactics.describe_risks(tactics.wounded_at_risk("fire", E54, pack, state, s, h))
    notes = []
    pack, source = tactics.choose_backup("fire", E54, [FIRE_BASE], state, s, [(FIRE_BASE, {})], h,
                                         risky=danger, notes=notes)
    assert pack == FIRE_ALECTO and source == tactics.SOURCE_USER
    assert len(notes) == 1 and "опасен для раненых" in notes[0] and "moloch" in notes[0]
    # Неопасных нет: после боя опасный всё равно лучше, чем ничего; перед боем — не берём
    s = settings(backup_teams={"fire": [FIRE_MOLOCH]})
    assert tactics.choose_backup("fire", E54, [FIRE_BASE], state, s, [], h, risky=danger)[0] == FIRE_MOLOCH
    assert tactics.choose_backup("fire", E54, [FIRE_BASE], state, s, [], h, risky=danger, allow_risky=False) == (None, None)


def test_backup_notes_for_wounded_and_forbidden():
    s = settings(backup_teams={"fire": [FIRE_MOLOCH, FIRE_ALECTO]})
    notes = []
    pack, _ = tactics.choose_backup("fire", E74, [FIRE_BASE], {"moloch": {"hp": 20}}, s, [], tactics.BattleHistory(),
                                    forbidden={"alecto"}, notes=notes)
    assert pack is None
    assert any("ниже порога паники: moloch 20%" in n for n in notes)
    assert any("под запретом правил skip: alecto" in n for n in notes)


def test_history_backup_only_with_your_titans():
    """Сессия 08: пак с Алекто остался только в истории боёв (правило удалено, из запасных паков вы её убрали).
    Из истории бот берёт только паки, где все титаны есть в ваших правилах, базовых или запасных паках."""
    won = hp(araji=90, ignis=100, acheron=100, vulcan=100, alecto=90)
    h = tactics.BattleHistory([battle(FIRE_ALECTO, "SUCCESS", won, enemies=E74)], settings())
    s = settings()
    roster = tactics.own_titans([FIRE_BASE, MIX_BASE, FIRE_MOLOCH], s)
    assert "alecto" not in roster and {"vulcan", "moloch", "amon"} <= roster
    assert tactics.choose_backup("fire", E74, [FIRE_BASE], {}, s, [], h, roster=roster) == (None, None)
    assert tactics.choose_backup("fire", E74, [FIRE_BASE], {}, s, [], h)[0] == FIRE_ALECTO   # без списка — как раньше
    # Алекто в ваших запасных паках — её паки из истории снова можно брать
    s = settings(backup_teams={"water": [["hyperion", "alecto"]]})
    roster = tactics.own_titans([FIRE_BASE, FIRE_MOLOCH], s)
    assert tactics.choose_backup("fire", E74, [FIRE_BASE], {}, s, [], h, roster=roster) == (FIRE_ALECTO,
                                                                                               tactics.SOURCE_HISTORY)


# --- Двери ---
def test_door_choice_prefers_heal_door_and_avoids_danger():
    order = ["water", "mix", "earth", "fire"]
    no = lambda r: False
    heals = lambda r: "Отхил Араджи" if r == "mix" else ""
    danger = lambda r: "ARAJI: 36% ХП, обычно теряет ~29%" if r == "fire" else ""
    # Вода и смешанная: раненого лечат в смешанной — идём туда, хотя вода первая по порядку
    idx, allowed, banned, note = tactics.door_choice(["water", "mix"], order, no, heals, danger)
    assert idx == 1 and allowed and "лечат" in note
    # Смешанная и так первая — пояснения нет
    assert tactics.door_choice(["mix", "earth"], order, no, heals, danger)[3] == ""
    # Свой порядок «огонь первым», Араджи слаб — идём в землю
    idx, _, _, note = tactics.door_choice(["fire", "earth"], ["fire", "earth", "water", "mix"], no, None, danger)
    assert idx == 1 and "FIRE опасна" in note
    # Опасны все — первая по порядку
    assert tactics.door_choice(["fire"], order, no, heals, danger)[:2] == (0, True)
    # Дверь, где лечат, но под запретом skip — не берём
    idx, _, banned, _ = tactics.door_choice(["water", "mix"], order, lambda r: r == "mix", heals, danger)
    assert idx == 0 and banned == ["mix"]
    # Без подсказок — как раньше
    assert tactics.door_choice(["water", "mix"], order, no) == (0, True, [], "")


# --- Решение без вас ---
def test_decide_without_you():
    alive = hp(araji=9, ignis=100, acheron=86)
    assert tactics.decide_without_you(FIRE_BASE, alive, True, FIRE_MOLOCH)[0] == tactics.ROLLBACK
    # Откатить нельзя (ручной бой Ангуса) или запасного нет — все живы: принимаем бой
    assert tactics.decide_without_you(FIRE_BASE, alive, False, FIRE_MOLOCH)[0] == tactics.ACCEPT
    assert tactics.decide_without_you(FIRE_BASE, alive, True, None)[0] == tactics.ACCEPT
    # Кто-то погиб или не найден — мягкая пауза
    dead = hp(araji=0, ignis=100, acheron=86)
    choice, why = tactics.decide_without_you(FIRE_BASE, dead, True, None)
    assert choice == tactics.PAUSE and "araji" in why
    missing = {"araji": {"hp": 0, "status": "ОТСУТСТВУЕТ"}, "ignis": hp(ignis=100)["ignis"]}
    assert tactics.decide_without_you(["araji", "ignis"], missing, False, None)[0] == tactics.PAUSE


def test_sos_timeout_setting():
    assert settings().sos_timeout_minutes == 10                        # ваш ответ: 10 минут
    assert settings(sos_timeout_minutes=0).sos_timeout_minutes == 0    # ждать всегда
    assert settings(sos_timeout_minutes=500).sos_timeout_minutes == tactics.MAX_SOS_TIMEOUT
    assert settings(sos_timeout_minutes="abc").sos_timeout_minutes == 10
    assert any("10 мин" in line for line in settings().describe())
    profile = tactics.write_tactics({}, {"sos_timeout_minutes": 15})
    assert profile["settings"] == {"sos_timeout_minutes": 15}
    assert tactics.read_tactics(profile)["sos_timeout_minutes"] == 15


# --- Правила: отхил за дверью и «золотые правила» ---
RULES = {
    "mix": {"rules": [
        {"name": "Отхил Араджи", "condition": {"titan_hp_below": {"araji": 50}}, "team": MIX_HEAL},
        {"name": "Ригель без лекаря", "condition": {"titan_hp_below": {"rigel": 35}}, "team": ["rigel", "amon"]},
        {"name": "Анти-пак", "condition": {"enemies_contain": ["nova"], "titan_hp_below": {"amon": 50}},
         "team": ["amon", "hyperion"]},
        {"name": "Не пускать Сигурда", "condition": {"titan_hp_below": {"sigurd": 50}}, "team": [], "action": "skip"},
    ], "default_team": MIX_BASE},
    "fire": {"rules": [], "default_team": FIRE_BASE},
}


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "profile.yml").write_text("global_thresholds:\n  max_hp_delta: 60\n", encoding="utf-8")
    for room, data in RULES.items():
        path = tmp_path / "bot_data" / "rules" / f"{room}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    sys.modules.pop("rules_engine", None)
    module = importlib.import_module("rules_engine")
    yield module.RulesEngine()
    sys.modules.pop("rules_engine", None)


def test_heal_rule_for_door(engine):
    assert engine.heal_rule_for("mix", {"araji": {"hp": 40}}, tactics.HEALERS) == "Отхил Араджи"
    assert engine.heal_rule_for("mix", {"araji": {"hp": 60}}, tactics.HEALERS) == ""
    # В паке правила нет лекаря — это не отхил
    assert engine.heal_rule_for("mix", {"rigel": {"hp": 20}}, tactics.HEALERS) == ""
    # Правило с врагами не берём: врагов за дверью бот ещё не видел
    assert engine.heal_rule_for("mix", {"amon": {"hp": 20}}, tactics.HEALERS) == ""
    assert engine.heal_rule_for("fire", {"araji": {"hp": 10}}, tactics.HEALERS) == ""


def test_golden_rules(engine, tmp_path):
    entries = [battle(FIRE_MOLOCH, "SUCCESS", hp(araji=90, ignis=100, acheron=100, vulcan=100, moloch=90), enemies=E74)
               for _ in range(4)]
    entries.append(battle(FIRE_MOLOCH, "ROLLBACK", hp(araji=10), enemies=E74))
    entries += [battle(FIRE_BASE, "SUCCESS", hp(araji=80, ignis=100, acheron=100)) for _ in range(6)]
    entries += [battle(MIX_HEAL, "SUCCESS", hp(araji=100, hyperion=100, rigel=100, iyari=100, lumira=100),
                       enemies=["nova"], room="mix") for _ in range(5)]
    golden = tactics.golden_packs(tactics.BattleHistory(entries, settings()))
    assert {(g["room"], tuple(g["team"])) for g in golden} == {
        ("fire", tuple(sorted(FIRE_MOLOCH))), ("fire", tuple(sorted(FIRE_BASE))), ("mix", tuple(sorted(MIX_HEAL)))}
    moloch = next(g for g in golden if "moloch" in g["team"])
    assert moloch["wins"] == 4 and moloch["battles"] == 5                       # 80% побед — как во вкладке «Аналитика»
    # Ваш запасной пак «золотым» не становится: он для помощи, а не на каждый бой
    with_backup = tactics.golden_packs(tactics.BattleHistory(entries), settings(backup_teams={"fire": [FIRE_MOLOCH]}))
    assert not any("moloch" in g["team"] for g in with_backup)
    # Пак с титаном, которого нет в ваших правилах и паках (сессия 08: Алекто), «золотым» не становится
    roster = tactics.own_titans([FIRE_BASE, MIX_HEAL], settings())
    mine = tactics.golden_packs(tactics.BattleHistory(entries), settings(), roster=roster)
    assert {tuple(g["team"]) for g in mine} == {tuple(sorted(FIRE_BASE)), tuple(sorted(MIX_HEAL))}

    added = [engine.add_golden_rule(g["room"], g["enemies"], g["team"], g["wins"], g["battles"], g["avg_hp"])
             for g in golden]
    # Базовый пак и пак отхила «золотыми» не становятся: они ставятся по ситуации
    assert [r["team"] for r in added if r] == [sorted(FIRE_MOLOCH)]
    fire = yaml.safe_load((tmp_path / "bot_data" / "rules" / "fire.yml").read_text(encoding="utf-8"))
    assert fire["rules"][0]["condition"] == {"enemies_contain": sorted(E74)}
    assert fire["rules"][0]["name"].startswith("Золотое правило против: ") and "побед 4 из 5" in fire["rules"][0]["name"]
    assert engine.get_battle_decision("fire", E74, {})[0] == sorted(FIRE_MOLOCH)
    # Второй раз не дублируется: против этих врагов правило уже есть
    assert engine.add_golden_rule("fire", E74, FIRE_MOLOCH, 4, 5, 96) is None
    assert engine.add_golden_rule("fire", E74, FIRE_ALECTO, 9, 9, 96) is None


def test_log_battle_writes_hp_before(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("analytics", None)
    analytics = importlib.import_module("analytics")
    try:
        entry = analytics.log_battle("fire", E54, FIRE_BASE, "ROLLBACK", "Авто-откат", hp(araji=9), hp_before={"araji": 36})
        assert entry["hp_before"] == {"araji": 36}
        with open(analytics.SESSION_LOG_FILE, encoding="utf-8") as f:
            assert json.loads(f.readline())["hp_before"] == {"araji": 36}
        assert "hp_before" not in analytics.log_battle("fire", E54, FIRE_BASE, "SUCCESS", "ok", hp(araji=50))
    finally:
        sys.modules.pop("analytics", None)


def test_wrong_session_07_rules_are_removed(tmp_path, monkeypatch):
    """Ваше решение: анти-паки огня, которые бот запомнил в сессии 07, удаляются при запуске. Остальные правила
    (в том числе такие же, но заданные вами) остаются."""
    monkeypatch.chdir(tmp_path)
    moloch_54 = {"name": "Анти-пак против: Ангус, Сильва, Вердок", "source": "auto", "team": FIRE_MOLOCH,
                 "condition": {"enemies_contain": ["angus", "silva", "verdok"]}}
    alecto_74 = {"name": "Анти-пак против: Ангус, Авалон, Эдем", "source": "auto", "team": FIRE_ALECTO,
                 "condition": {"enemies_contain": ["angus", "avalon", "eden"]}}
    yours = dict(alecto_74, source="gui")
    rescue = {"name": "Auto Rule", "condition": {"titan_hp_below": {"araji": 35}}, "team": FIRE_MOLOCH}
    path = tmp_path / "bot_data" / "rules" / "fire.yml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.dump({"rules": [alecto_74, moloch_54, yours, rescue], "default_team": FIRE_BASE},
                              allow_unicode=True), encoding="utf-8")
    sys.modules.pop("rules_engine", None)
    module = importlib.import_module("rules_engine")
    try:
        engine = module.RulesEngine()
        rules = yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]
        assert rules == [yours, rescue]
        assert engine.get_battle_decision("fire", ["angus", "silva", "verdok"], {})[0] == FIRE_BASE
    finally:
        sys.modules.pop("rules_engine", None)


def test_all_packs_for_own_titans(engine):
    """Ваши титаны (сессия 08) — из базовых паков и паков правил всех стихий; правила skip и [STOP] не в счёт."""
    roster = tactics.own_titans(engine.all_packs(), settings())
    assert {"araji", "amon", "rigel", "lumira"} <= roster and "STOP" not in roster
    assert "alecto" not in roster
