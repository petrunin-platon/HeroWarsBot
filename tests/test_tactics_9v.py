# Тесты задачи 9в: ХП и энергия с экрана против памяти, энергия в истории и в прогнозе потерь,
# пак отхила по правилам игры (ваш ответ на вопрос 23), настройки отхила в окне «⚙️ Тактика».
import importlib
import json
import sys

import pytest
import yaml

import data_paths
import tactics
import titan_state

MIX_BASE = ["hyperion", "rigel", "iyari", "lumira", "amon"]
MIX_ARAJI = ["hyperion", "rigel", "iyari", "lumira", "araji"]
MIX_ALECTO = ["hyperion", "rigel", "iyari", "lumira", "alecto"]
MIX_SIGURD = ["hyperion", "rigel", "iyari", "lumira", "sigurd"]
FIRE_BASE = ["araji", "ignis", "acheron"]
BASE_PACKS = {"mix": MIX_BASE, "fire": FIRE_BASE, "water": ["hyperion", "sigurd", "tidus", "nova", "mairi"],
              "earth": ["angus", "avalon", "eden", "silva", "verdok"]}
E1 = ["avalon", "eden", "verdok", "nova", "araji"]
DAY = "2026-10-20"


def settings(**values):
    # Пороги из сессии 07: паника 30%, допуск 60%; бот решает сам
    values.setdefault("critical_hp", 30)
    values.setdefault("max_hp_delta", 60)
    values.setdefault("auto_rollback", True)
    return tactics.Settings(lambda key, default=None: values.get(key, default))


def state(**titans):
    """{титан: (ХП, энергия)} или {титан: ХП}."""
    out = {}
    for t, v in titans.items():
        hp, energy = v if isinstance(v, tuple) else (v, 50)
        out[t] = {"hp": hp, "energy": energy}
    return out


def battle(team, action, after, room="mix", enemies=E1, time=f"{DAY} 10:30:00", before=None, energy=None, **extra):
    entry = {"timestamp": time, "room": room, "enemies": list(enemies), "team": list(team), "action": action,
             "hp_status": {t: {"hp": v, "energy": 50, "status": "ЖИВ"} for t, v in after.items()}}
    if before is not None:
        entry["hp_before"] = before
    if energy is not None:
        entry["energy_before"] = energy
    entry.update(extra)
    return entry


def plan(st, s=None, history=None, pack=MIX_BASE, room="mix", **kw):
    notes = []
    result = tactics.heal_plan(room, pack, st, s or settings(), history or tactics.BattleHistory(), BASE_PACKS,
                               notes=notes, **kw)
    return result, notes


@pytest.fixture(autouse=True)
def fresh_process_state():
    data_paths._CHECKED.clear()
    yield
    data_paths._CHECKED.clear()


# --- ХП с экрана выбора команды против памяти ---
def test_screen_reading_fixes_memory_and_explains():
    memory = {"araji": {"hp": 55, "energy": 40}, "ignis": {"hp": 100, "energy": 70}, "acheron": {"hp": 86, "energy": 10}}
    bars = {"araji": {"hp": 36, "energy": 47}, "ignis": {"hp": 98, "energy": None},
            "acheron": {"hp": None, "energy": 20}, "vulcan": {"hp": 100, "energy": 0}}
    updates, text, fixed = titan_state.screen_reading(memory, bars)
    assert updates == {"araji": {"hp": 36, "energy": 47}, "ignis": {"hp": 98, "energy": 70},
                       "vulcan": {"hp": 100, "energy": 0}}
    assert "ARAJI 36% ⚡47% (бот помнил 55%)" in text
    assert "IGNIS 98% ⚡70%" in text and "IGNIS 98% ⚡70% (" not in text  # разница 2% — шум, не исправление
    assert "ACHERON не прочиталось" in text                               # ХП не прочиталось — память не трогаем
    assert "VULCAN 100% ⚡0% (бот не знал)" in text                        # после ручной игры память пустая
    assert fixed == ["araji", "vulcan"]


def test_screen_reading_after_manual_play_fills_empty_memory(tmp_path):
    memory = titan_state.TitanMemory(str(tmp_path / "titan_state.json"), lambda: DAY)
    updates, _, fixed = titan_state.screen_reading(memory, {"rigel": {"hp": 40, "energy": 15}})
    memory.update(updates)
    again = titan_state.TitanMemory(str(tmp_path / "titan_state.json"), lambda: DAY)
    assert again["rigel"] == {"hp": 40, "energy": 15} and fixed == ["rigel"]


# --- Энергия в истории и в прогнозе ---
def test_history_restores_energy_before_for_old_records():
    entries = [
        battle(FIRE_BASE, "SUCCESS", {"araji": 64}, room="fire", time=f"{DAY} 10:00:00"),
        battle(FIRE_BASE, "ROLLBACK", {"araji": 9}, room="fire", time=f"{DAY} 10:10:00"),
        battle(FIRE_BASE, "SUCCESS", {"araji": 36}, room="fire", time=f"{DAY} 10:20:00", energy={"araji": 80}),
        battle(FIRE_BASE, "SUCCESS", {"araji": 100}, room="fire", time="2026-10-21 10:00:00"),
    ]
    entries[0]["hp_status"]["araji"]["energy"] = 47
    h = tactics.BattleHistory(entries, settings())
    assert h.energy[0] == {}                 # раньше в этот день Араджи не дрался
    assert h.energy[1] == {"araji": 47}      # после последней удачной битвы
    assert h.energy[2] == {"araji": 80}      # записано в бою (задача 9в)
    assert h.energy[3] == {}                 # новый игровой день


def energy_history():
    """Араджи в огне: с энергией 70–80% теряет 5–10%, с 20–30% — 40–45%."""
    entries = []
    for i, (energy, loss) in enumerate([(70, 5), (25, 40), (80, 10), (20, 45), (75, 5)]):
        entries.append(battle(FIRE_BASE, "SUCCESS", {"araji": 90 - loss}, room="fire", enemies=["angus"],
                              time=f"{DAY} 10:{10 + i}:00", before={"araji": 90}, energy={"araji": energy}))
    return tactics.BattleHistory(entries, settings())


def test_expected_loss_by_energy():
    h = energy_history()
    assert h.expected_loss("fire", FIRE_BASE, "araji", energy=75) == pytest.approx(20 / 3)  # бои с энергией 70–80%
    assert h.expected_loss("fire", FIRE_BASE, "araji", energy=20) == pytest.approx(42.5)    # бои с энергией 20–25%
    assert h.expected_loss("fire", FIRE_BASE, "araji") == pytest.approx(21)                 # энергия неизвестна — все
    # Боёв с похожей энергией меньше двух — берутся все
    charged = tactics.BattleHistory(h.entries[:1] + h.entries[2:3], settings())               # только 70% и 80%
    assert charged.expected_loss("fire", FIRE_BASE, "araji", energy=20) == pytest.approx(7.5)


def test_wounded_at_risk_uses_energy():
    """Ваш пример (вопрос 22): Араджи с половиной ХП, но заряженный на 60–80%, проходит огонь почти без потерь."""
    h = energy_history()
    s = settings()
    assert tactics.wounded_at_risk("fire", ["angus"], FIRE_BASE, state(araji=(50, 75)), s, h) == []
    risks = tactics.wounded_at_risk("fire", ["angus"], FIRE_BASE, state(araji=(50, 20)), s, h)
    assert risks == [("araji", 50, 42)]
    assert tactics.describe_risks(risks, state(araji=(50, 20))) == "ARAJI: 50% ХП, ⚡20%, обычно теряет ~42%"


def test_log_battle_writes_energy_and_heal_mark(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("analytics", None)
    analytics = importlib.import_module("analytics")
    try:
        entry = analytics.log_battle("mix", E1, MIX_ARAJI, "SUCCESS", "ok", {}, hp_before={"araji": 59},
                                     energy_before={"araji": 47}, heal_for="araji")
        assert entry["energy_before"] == {"araji": 47} and entry["heal_for"] == "araji"
        with open(analytics.SESSION_LOG_FILE, encoding="utf-8") as f:
            assert json.loads(f.readline())["energy_before"] == {"araji": 47}
        plain = analytics.log_battle("mix", E1, MIX_BASE, "SUCCESS", "ok", {})
        assert "energy_before" not in plain and "heal_for" not in plain
    finally:
        sys.modules.pop("analytics", None)


# --- Пак отхила по правилам игры ---
def test_fire_titan_is_healed_in_mix_instead_of_amon():
    """Сессия 07, комната 75: Алекто ушла из огня с 44%. В огне лекарей нет — в смешанной она встаёт вместо Амона."""
    result, notes = plan(state(alecto=44, rigel=100))
    pack, titan, why = result
    assert pack == MIX_ALECTO and titan == "alecto" and "вместо AMON" in why and notes == []


def test_water_and_earth_titans_heal_at_home():
    """Сигурда лечат в воде (Гиперион), Эдема — в земле (Авалон): в смешанную их не тянем."""
    assert plan(state(sigurd=40, eden=45)) == (None, [])
    assert tactics.heals_at_home("sigurd", BASE_PACKS) and tactics.heals_at_home("eden", BASE_PACKS)
    assert not tactics.heals_at_home("araji", BASE_PACKS) and not tactics.heals_at_home("moloch", BASE_PACKS)


def test_one_at_a_time_closest_to_panic_first():
    """Лечим по одному (вопрос 23): первым тот, кто ближе к своему порогу паники."""
    (pack, titan, _), _ = plan(state(araji=50, alecto=45), settings(titan_critical_hp={"araji": 40}))
    assert titan == "araji" and pack == MIX_ARAJI


def test_not_below_panic_and_not_forbidden():
    """Ниже порога паники в смешанной уже не вылечить (вопрос 1); под запретом правил skip — не ставим."""
    result, notes = plan(state(araji=20))
    assert result is None and "ниже порога паники" in notes[0]
    result, notes = plan(state(araji=45), forbidden={"araji"})
    assert result is None and "skip" in notes[0]
    # Погибшего не лечат и о нём не пишут; здоровые и неизвестные не раненые
    assert plan(state(araji=0, ignis=100)) == (None, [])


def test_threshold_and_room_settings():
    assert plan(state(araji=59)) [0][1] == "araji"
    assert plan(state(araji=60))[0] is None                       # порог по умолчанию — ниже 60%
    assert plan(state(araji=65), settings(heal_below_hp=70))[0][1] == "araji"
    assert plan(state(araji=40), settings(heal_below_hp=0))[0] is None   # 0 — не собирать
    assert plan(state(araji=40), room="fire", pack=FIRE_BASE)[0] is None  # только в смешанной


def test_removal_order():
    """Кого убирать: ваш список, потом сам — с конца пака, кроме лекарей. Для вашего пака: Амон, потом Люмира."""
    s = settings()
    assert tactics.removal_order(MIX_BASE, s) == ["amon", "lumira", "rigel"]
    assert tactics.removal_order(MIX_BASE, s, keep={"amon"}) == ["lumira", "rigel"]
    mine = settings(heal_remove_order=["lumira", "moloch", "lumira"])
    assert tactics.removal_order(MIX_BASE, mine) == ["lumira", "amon", "rigel"]
    (pack, _, why), _ = plan(state(araji=45), mine)
    assert pack == ["hyperion", "rigel", "iyari", "araji", "amon"] and "вместо LUMIRA" in why


def rigel_stuck(time2=f"{DAY} 10:20:00"):
    """Ригель два боя подряд в смешанной держится ниже 60% (ваш пример из ответа на вопрос 23)."""
    return tactics.BattleHistory([
        battle(MIX_BASE, "SUCCESS", {"rigel": 45}, time=f"{DAY} 10:10:00", before={"rigel": 50}),
        battle(MIX_BASE, "SUCCESS", {"rigel": 40}, time=time2, before={"rigel": 45}),
    ], settings())


def test_wounded_in_pack_gets_helper_healer_when_not_healing():
    """Ригель в паке, но не поднимается выше 60% — вместо Амона встаёт Сигурд (здоров и заряжен)."""
    st = state(rigel=40, sigurd=(100, 70), avalon=(100, 0))
    (pack, titan, why), notes = plan(st, history=rigel_stuck())
    assert pack == MIX_SIGURD and titan == "rigel" and "SIGURD" in why and "AMON" in why
    # Сигурд с энергией меньше 60% — не помощник (вопрос 22: с 15% энергии в смешанной его просто убьют)
    result, notes = plan(state(rigel=40, sigurd=(100, 15)), history=rigel_stuck())
    assert result is None and "лекаря" in notes[0]


def test_wounded_in_pack_is_healed_by_usual_pack_first():
    """Ригель 55% в обычном паке смешанной лечится им (сессия B, комната 56): пак не меняем."""
    one_battle = tactics.BattleHistory([battle(MIX_BASE, "SUCCESS", {"rigel": 55}, before={"rigel": 100})], settings())
    assert plan(state(rigel=55, sigurd=(100, 90)), history=one_battle) == (None, [])
    # Вчерашние бои не считаются: ХП за ночь восстановилось
    yesterday = tactics.BattleHistory([
        battle(MIX_BASE, "SUCCESS", {"rigel": 45}, time="2026-10-19 22:00:00", before={"rigel": 50}),
        battle(MIX_BASE, "SUCCESS", {"rigel": 40}, time="2026-10-19 22:10:00", before={"rigel": 45}),
        battle(FIRE_BASE, "SUCCESS", {"araji": 100}, room="fire", time=f"{DAY} 06:00:00"),
    ], settings())
    assert not yesterday.not_healing("mix", "rigel", 60)
    assert rigel_stuck().not_healing("mix", "rigel", 60)


def test_heal_pack_checks():
    """Пак отхила не берётся, если он проигрывает этим врагам, опасен для раненых или нужен ручной бой."""
    lost = tactics.BattleHistory([battle(MIX_ARAJI, "ROLLBACK", {"araji": 59, "iyari": 10}, before={"araji": 59})],
                                 settings())
    result, notes = plan(state(araji=59), history=lost, enemies=E1)
    assert result is None and "проигрывает" in notes[0]
    # Против других врагов этот бой не считается
    assert plan(state(araji=59), history=lost, enemies=["nova"])[0][0] == MIX_ARAJI

    risky = tactics.BattleHistory([battle(MIX_ARAJI, "SUCCESS", {"araji": 25}, before={"araji": 55},
                                          time=f"{DAY} 10:0{i}:00") for i in range(2)], settings())
    result, notes = plan(state(araji=55), history=risky, enemies=E1)
    assert result is None and "опасен для раненых" in notes[0]

    result, notes = plan(state(angus=45), pack=["hyperion", "rigel", "iyari", "lumira", "amon"],
                         special_ult=lambda p: "angus" if "angus" in p else "auto")
    assert result is None  # Ангуса лечат в земле (Авалон) — в смешанную не тянем
    result, notes = plan(state(araji=45), special_ult=lambda p: "angus")
    assert result is None and "ручной бой" in notes[0]


def test_heal_packs_are_not_golden():
    """Пак отхила, который бот собрал сам, нужен, только пока титан ранен: «золотым правилом» он не становится."""
    entries = [battle(MIX_ARAJI, "SUCCESS", {"araji": 100}, time=f"{DAY} 10:0{i}:00", heal_for="araji")
               for i in range(6)]
    assert tactics.golden_packs(tactics.BattleHistory(entries, settings())) == []
    for e in entries:
        del e["heal_for"]
    assert len(tactics.golden_packs(tactics.BattleHistory(entries, settings()))) == 1


def test_heal_settings_in_tactics_window():
    s = settings()
    assert s.heal_hp == tactics.DEFAULT_HEAL_HP == 60 and s.heal_remove_order == []
    s = settings(heal_below_hp=150, heal_remove_order=["amon", "amon", "lumira", "rigel", "moloch"])
    assert s.heal_hp == 100 and s.heal_remove_order == ["amon", "lumira", "rigel"]
    assert settings(heal_remove_order="amon").heal_remove_order == []
    profile = {"settings": {"auto_rollback": True}}
    tactics.write_tactics(profile, {"heal_below_hp": 55, "heal_remove_order": ["amon", "lumira"]})
    assert profile["settings"]["heal_below_hp"] == 55
    values = tactics.read_tactics(profile)
    assert values["heal_below_hp"] == 55 and values["heal_remove_order"] == ["amon", "lumira"]
    lines = "\n".join(tactics.Settings(tactics.profile_getter(profile)).describe())
    assert "ниже 55% ХП" in lines and "amon → lumira" in lines
    assert "Отхил в смешанной" not in "\n".join(settings(auto_rollback=False).describe())


# --- Движок правил и дверь ---
RULES = {
    "mix": {"rules": [
        {"name": "Отхил Араджи", "condition": {"titan_hp_below": {"araji": 50}}, "team": MIX_ARAJI},
        {"name": "Не пускать Сигурда", "condition": {"titan_hp_below": {"sigurd": 50}}, "team": [], "action": "skip"},
    ], "default_team": MIX_BASE},
    "fire": {"rules": [], "default_team": FIRE_BASE},
    "water": {"rules": [], "default_team": BASE_PACKS["water"]},
    "earth": {"rules": [], "default_team": BASE_PACKS["earth"]},
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


def test_your_heal_rule_comes_first(engine):
    """Ваше правило отхила главнее: ниже 50% Араджи лечит оно. Между 50% и 60% — пак собирает бот."""
    assert engine.base_packs()["fire"] == FIRE_BASE
    s, h = settings(), tactics.BattleHistory()
    choice = engine.battle_decision("mix", E1, state(araji=45))
    assert choice["reason"] == "Отхил Араджи" and choice["condition"]   # main.py собирает пак только вместо базового
    choice = engine.battle_decision("mix", E1, state(araji=55))
    assert not choice["condition"]
    pack, titan, _ = tactics.heal_plan("mix", choice["team"], state(araji=55), s, h, engine.base_packs(),
                                       forbidden=engine.forbidden_titans("mix", E1, state(araji=55)), enemies=E1,
                                       special_ult=engine.special_ult_for)
    assert pack == MIX_ARAJI and titan == "araji"
    # Ваше правило skip: Сигурд ниже 50% в смешанную не идёт — и помощником тоже
    st = state(rigel=40, sigurd=(45, 90))
    assert tactics.heal_plan("mix", MIX_BASE, st, s, rigel_stuck(), engine.base_packs(),
                             forbidden=engine.forbidden_titans("mix", E1, st)) is None


def test_door_prefers_mix_when_bot_will_heal(engine):
    """Дверь по здоровью (задача 9б) теперь видит и пак отхила, который соберёт бот: раненая Алекто — в смешанную."""
    st, s, h = state(alecto=44), settings(), tactics.BattleHistory()

    def heals(room):
        rule = engine.heal_rule_for(room, st, tactics.HEALERS)
        choice = engine.battle_decision(room, [], st)
        heal = None if choice["condition"] else tactics.heal_plan(room, choice["team"], st, s, h, engine.base_packs())
        return rule or (f"бот соберёт пак отхила: {heal[2]}" if heal else "")

    index, allowed, _, note = tactics.door_choice(["water", "mix"], tactics.DEFAULT_DOOR_ORDER, lambda r: False, heals)
    assert index == 1 and allowed and "ALECTO" in note
    # Все здоровы — обычный порядок дверей
    index, _, _, note = tactics.door_choice(["water", "mix"], tactics.DEFAULT_DOOR_ORDER, lambda r: False,
                                            lambda r: "")
    assert index == 0 and note == ""
