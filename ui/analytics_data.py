"""«Аналитика» нового окна (задача 15, шаг 6; макет design/mockups/04_analytics): разбор истории боёв — без Tk.

История — bot_data/logs/*.jsonl (её пишет бот, analytics.py). Бой — запись SUCCESS или ROLLBACK с комнатой, врагами
и паком, как в старой вкладке (ui/analytics_tab.py): «Всего боёв», «Средний винрейт» и подробный отчёт — все паки против
каждого состава врагов с винрейтом и средним ХП после боя (ваш ответ 5.1: отчёт остаётся, в колонке «Ход анализа»).
Пометки отчёта — как в старой вкладке: «в базе» (правило с этими врагами и этим паком уже есть), от 80% — «идеально»,
от 50% — «средне», ниже — «опасно».

«Золотые правила» — как у бота (ваш ответ 5.2), а не как в старой вкладке: тот же отбор, что у main.py:add_golden_rules
(tactics.golden_packs: от 5 боёв и от 80% побед; без ваших запасных паков, паков отхила бота и титанов не из ваших паков)
и те же отказы, что у rules_engine.add_golden_rule (базовый пак и паки правил спасения; против этих врагов уже есть
правило — ваше, запомненное или выключенное — его не трогаем). Правило записывается так же, как его записал бы бот:
«Золотое правило против: ...», source: golden, на 1-е место, без пометки ульты Ангуса (задача 12).
В файл стихии пишется один раз за «Внедрить» (пользователь просит писать файлы как можно реже).
"""
import glob
import json
import os
from collections import defaultdict

import data_paths
import tactics
from i18n import get_text
from ui import rules_list, rules_store

ROOMS = ("water", "mix", "earth", "fire")
PERFECT, AVERAGE = 80, 50


def read_history(folder=None):
    """(записи боёв по времени, сколько файлов). Битые строки пропускаются, как в старой вкладке."""
    folder = folder or data_paths.logs_dir()
    files = sorted(glob.glob(os.path.join(folder, "*.jsonl")))
    entries = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(entry, dict):
                        entries.append(entry)
        except OSError:
            continue
    entries.sort(key=lambda e: str(e.get("timestamp") or ""))
    return entries, len(files)


def _counted(entry):
    room, enemies, team = entry.get("room"), entry.get("enemies") or [], entry.get("team") or []
    return bool(room) and room != "unknown" and bool(enemies) and bool(team) and entry.get("action") in ("SUCCESS", "ROLLBACK")


def _avg_hp(entry, team):
    hp = [v.get("hp", 0) for k, v in (entry.get("hp_status") or {}).items() if k in team and isinstance(v, dict)]
    return sum(hp) / len(hp) if hp else None


def read_rules_files(read=rules_store.read_rules):
    """{стихия: данные файла bot_data/rules/<стихия>.yml}; нет файла или битый — пустой словарь (как у бота)."""
    cache = {}
    for room in ROOMS:
        state, data = read(room)
        cache[room] = data if state == rules_store.OK else {}
    return cache


# Ниже — то же, что у бота в rules_engine.py (all_packs, situational_packs, titan_name_ru). Сам rules_engine окно
# не импортирует: при импорте он создаёт движок, а тот чистит устаревшие правила в файлах и печатает строку [ПРАВИЛА] —
# это работа бота при запуске. Что ответы совпадают с ботом, проверяет tests/test_ui_analytics.py.
def _rule_list(data):
    rules = (data or {}).get("rules") or []
    return [r for r in rules if isinstance(r, dict)]


def _enabled(rule):
    return rule.get("enabled") is not False


def all_packs(cache):
    """rules_engine.all_packs: паки включённых правил (без skip и [STOP]) и базовые паки всех стихий."""
    packs = []
    for data in cache.values():
        for rule in _rule_list(data):
            team = rule.get("team") or []
            if _enabled(rule) and rule.get("action") != "skip" and team and team != ["STOP"]:
                packs.append(list(team))
        if (data or {}).get("default_team"):
            packs.append(list(data["default_team"]))
    return packs


def situational_packs(cache, room):
    """rules_engine.situational_packs: базовый пак и паки правил спасения (по ХП или энергии)."""
    data = cache.get(room) or {}
    packs = [sorted(data.get("default_team") or [])]
    for rule in _rule_list(data):
        condition = rule.get("condition") or {}
        if "titan_hp_below" in condition or "titan_energy_below" in condition:
            packs.append(sorted(rule.get("team") or []))
    return packs


def titan_name_ru(titan):
    key = f"titan_{titan}"
    name = get_text("RU", key)
    return titan if name == key else name


def _rules_by_room(cache):
    return {room: _rule_list(cache.get(room)) for room in ROOMS}


def _rule_against(rules, enemies):
    """Правило против этих врагов (как в rules_engine.add_golden_rule: любое, кроме skip, и выключенное тоже)."""
    enemies = sorted(enemies)
    return next((r for r in rules if isinstance(r, dict) and r.get("action") != "skip"
                 and sorted((r.get("condition") or {}).get("enemies_contain") or []) == enemies), None)


def _in_base(rules, enemies, team):
    enemies, team = sorted(enemies), sorted(team)
    return any(isinstance(r, dict) and sorted((r.get("condition") or {}).get("enemies_contain") or []) == enemies
               and sorted(r.get("team") or []) == team for r in rules)


def status(winrate, in_base):
    if winrate >= PERFECT:
        return "in_base" if in_base else "perfect"
    return "average" if winrate >= AVERAGE else "danger"


def analyze(folder=None, profile_path=rules_store.PROFILE):
    """Разбор истории. Возвращает словарь:
    files, records — сколько файлов и записей прочитано; battles, wins, winrate — бои с комнатой, врагами и паком;
    scenarios — [{room, enemies, packs: [{team, wins, attempts, winrate, avg_hp, status}]}] (паки — от лучших);
    golden — [{room, enemies, team, wins, battles, avg_hp}] — что бот сам поставил бы «золотым правилом»."""
    entries, files = read_history(folder)
    _state, profile, _where = rules_store.read_profile(profile_path)
    settings = tactics.Settings(tactics.profile_getter(profile))
    cache = read_rules_files()
    rules = _rules_by_room(cache)

    stats = defaultdict(lambda: defaultdict(lambda: {"attempts": 0, "wins": 0, "hp": []}))
    battles = wins = 0
    for entry in entries:
        if not _counted(entry):
            continue
        team = tuple(sorted(entry["team"]))
        data = stats[(entry["room"], tuple(sorted(entry["enemies"])))][team]
        data["attempts"] += 1
        battles += 1
        if entry["action"] == "SUCCESS":
            data["wins"] += 1
            wins += 1
            hp = _avg_hp(entry, team)
            if hp is not None:
                data["hp"].append(hp)

    scenarios = []
    for (room, enemies), teams in stats.items():
        packs = []
        for team, data in teams.items():
            rate = data["wins"] * 100 / data["attempts"]
            packs.append({"team": list(team), "wins": data["wins"], "attempts": data["attempts"], "winrate": rate,
                          "avg_hp": sum(data["hp"]) / len(data["hp"]) if data["hp"] else 0.0,
                          "status": status(rate, _in_base(rules.get(room, []), enemies, team))})
        packs.sort(key=lambda p: (p["winrate"], p["attempts"]), reverse=True)
        scenarios.append({"room": room, "enemies": list(enemies), "packs": packs})

    history = tactics.BattleHistory(entries, settings)
    roster = tactics.own_titans(all_packs(cache), settings)
    golden = []
    for gold in tactics.golden_packs(history, settings, roster=roster):
        room = gold["room"]
        if room not in ROOMS or sorted(gold["team"]) in situational_packs(cache, room):
            continue
        if _rule_against(rules.get(room, []), gold["enemies"]) is not None:
            continue
        golden.append(gold)
    golden.sort(key=lambda g: (-g["wins"] * 100 / g["battles"], -g["battles"]))
    return {"files": files, "records": len(entries), "battles": battles, "wins": wins,
            "winrate": wins * 100 / battles if battles else 0.0, "scenarios": scenarios, "golden": golden}


def golden_rule(gold):
    """Правило — слово в слово как его записал бы бот (rules_engine.add_golden_rule)."""
    enemies = sorted(gold["enemies"])
    names = ", ".join(titan_name_ru(e) for e in enemies)
    return {"name": f"Золотое правило против: {names} (побед {gold['wins']} из {gold['battles']}, "
                    f"ХП {gold['avg_hp']:.0f}%)",
            "condition": {"enemies_contain": enemies}, "team": list(gold["team"]), "source": "golden"}


def apply_golden(chosen, read=rules_store.read_rules, write=rules_list.write_rules_file):
    """Записать выбранные золотые правила: по одному разу в файл стихии, каждое — на 1-е место.
    Файл перечитывается перед записью: правило против тех же врагов, появившееся за это время, не дублируется.
    Возвращает (добавленные [(стихия, правило)], пропущенные [gold], битые стихии)."""
    added, skipped, broken = [], [], []
    by_room = defaultdict(list)
    for gold in chosen:
        by_room[gold["room"]].append(gold)
    for room, golds in by_room.items():
        state, data = read(room)
        if state == rules_store.BROKEN:
            broken.append(room)
            skipped.extend(golds)
            continue
        if state == rules_store.MISSING:
            data = {"default_team": [], "rules": []}
        if not isinstance(data.get("rules"), list):
            data["rules"] = []
        new_rules = []
        for gold in golds:
            if _rule_against(new_rules + data["rules"], gold["enemies"]) is not None:
                skipped.append(gold)
                continue
            rule = golden_rule(gold)
            new_rules.insert(0, rule)
            added.append((room, rule))
        if new_rules:
            data["rules"] = new_rules + data["rules"]
            write(room, data)
    return added, skipped, broken
