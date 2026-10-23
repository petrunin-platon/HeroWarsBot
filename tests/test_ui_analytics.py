"""Задача 15, шаг 6: «Аналитика» (ui/analytics_page.py, разбор истории — ui/analytics_data.py).

Без окна (ui/analytics_data.py):
- всего боёв и винрейт — как в старой вкладке; подробный отчёт (ваш ответ 5.1) с пометками «в базе / идеально / средне / опасно»;
- золотые правила — как у бота (ваш ответ 5.2): то же, что main.py:add_golden_rules записал бы сам (tactics.golden_packs
  и отказы rules_engine.add_golden_rule) — без базового пака, паков отхила и спасения, ваших запасных паков, чужих титанов;
  против врагов с правилом (и выключенным) — ничего; правило записывается слово в слово как у бота, по разу в файл стихии;
- то, что окно повторяет за rules_engine (all_packs, situational_packs), совпадает с ботом;
- новые надписи — на 13 языках.
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_analytics.py):
- до анализа — «Золотых правил пока нет»; анализ в фоне, кнопка выключена; карточки с галочками, «Выбрать все»,
  «Внедрить (N)» пишет только отмеченные; нет истории — сообщение; процесс окна выходит сам, пока анализ идёт.
"""
import json
import os
import subprocess
import sys
import textwrap

import pytest

from test_ui_rules import ROOT, needs_gui, pump, read_yaml, workdir, write_yaml  # noqa: F401

NEW_KEYS = ["an_total", "an_winrate", "an_golden", "an_golden_title", "an_golden_hint", "an_select_all",
            "an_empty_title", "an_empty_text", "an_none_title", "an_none_text", "an_fights", "an_winrate_short",
            "an_console", "an_last", "an_never", "an_today_at", "an_run", "an_running", "an_apply", "an_tag_system",
            "an_tag_ml", "an_tag_done", "an_tag_error", "an_log_loaded", "an_log_waiting", "an_log_read",
            "an_log_no_files", "an_log_battles", "an_log_found", "an_log_none", "an_log_added", "an_log_skipped",
            "an_log_broken", "an_log_applied", "an_log_error", "an_rep_title", "an_rep_enemies", "an_rep_pack",
            "an_rep_hp", "an_st_in_base", "an_st_perfect", "an_st_average", "an_st_danger", "an_toast_applied"]
PLACEHOLDERS = {"an_fights": "{n}", "an_today_at": "{time}", "an_log_read": "{records}", "an_log_no_files": "{folder}",
                "an_log_battles": "{n}", "an_log_found": "{n}", "an_log_added": "{enemies}", "an_log_skipped": "{room}",
                "an_log_broken": "{room}", "an_log_applied": "{n}", "an_log_error": "{error}", "an_rep_hp": "{hp}",
                "an_toast_applied": "{n}"}
# Одинаковые с русским по праву: «СИСТЕМА», «ГОТОВО», «Пак» по-украински, «Пак» по-казахски
SAME_AS_RU = {"UK": {"an_tag_system", "an_tag_done", "an_rep_pack"}, "KK": {"an_rep_pack"}}

WATER = ["hyperion", "sigurd", "tidus", "nova", "mairi"]
FIRE = ["araji", "ignis", "acheron", "vulcan", "moloch"]
FIRE_GOLD = ["alecto", "ignis", "araji", "acheron", "moloch"]
EARTH_GOLD = ["angus", "pallant", "eden", "silva", "avalon"]
MIX_BACKUP = ["sigurd", "araji", "rigel", "iyari", "lumira"]


def battles(room, enemies, team, wins, total, **extra):
    return [dict({"timestamp": f"2026-10-{10 + k % 9:02d}T10:{k:02d}:00", "room": room, "enemies": enemies, "team": team,
                  "action": "SUCCESS" if k < wins else "ROLLBACK",
                  "hp_status": {t: {"hp": 80, "energy": 50} for t in team}}, **extra) for k in range(total)]


@pytest.fixture
def history(workdir):
    """Правила и профиль: огонь и земля — золотые; вода — базовый пак; смешанная — ваш запасной пак;
    огонь против Ангуса — титан не из ваших паков; земля против Авалона — есть выключенное правило; отхил бота."""
    rules = workdir / "bot_data" / "rules"
    write_yaml(rules / "water.yml", {"default_team": WATER, "rules": [
        {"name": "Отхил", "condition": {"titan_hp_below": {"araji": 50}}, "team": ["sigurd", "nova", "mairi", "orm", "tidus"]}]})
    write_yaml(rules / "fire.yml", {"default_team": FIRE, "rules": []})
    write_yaml(rules / "earth.yml", {"default_team": ["angus", "avalon", "eden", "silva", "verdok"], "rules": [
        {"name": "Выключено", "condition": {"enemies_contain": ["avalon"]}, "team": ["angus"], "enabled": False}]})
    write_yaml(rules / "mix.yml", {"default_team": ["rigel", "araji", "iyari", "lumira", "hyperion"], "rules": []})
    write_yaml(workdir / "profile.yml", {"settings": {"backup_teams": {
        "fire": [["alecto", "ignis", "araji", "acheron", "vulcan"]], "mix": [MIX_BACKUP],
        "earth": [["angus", "pallant", "eden", "silva", "verdok"]]}}})
    entries = (battles("fire", ["moloch", "vulcan"], FIRE_GOLD, 34, 37)
               + battles("earth", ["eden", "silva"], EARTH_GOLD, 18, 21)
               + battles("water", ["nova"], WATER, 10, 10)                                     # базовый пак
               + battles("mix", ["angus", "araji"], MIX_BACKUP, 9, 9)                         # ваш запасной пак
               + battles("fire", ["angus"], ["umbra", "ignis", "araji", "acheron", "moloch"], 9, 9)  # чужой титан
               + battles("earth", ["avalon"], EARTH_GOLD, 9, 9)                               # есть выключенное правило
               + battles("fire", ["ignis"], FIRE_GOLD, 9, 9, heal_for=["araji"])              # пак отхила бота
               + battles("fire", ["eden"], FIRE, 3, 6)                                        # средне
               + battles("fire", ["tidus"], FIRE, 4, 4)                                       # мало боёв
               + [{"room": "unknown", "enemies": ["x"], "team": ["y"], "action": "SUCCESS"}])
    logs = workdir / "bot_data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    with open(logs / "battle_log_2026-10-20.jsonl", "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
        f.write("не json\n")
    return workdir


# ── Без окна ─────────────────────────────────────────────────────────────────
def test_new_texts_in_all_languages():
    import unicodedata

    import i18n
    ru = i18n.TRANSLATIONS["RU"]
    for lang, words in i18n.TRANSLATIONS.items():
        for key in NEW_KEYS:
            text = words.get(key)
            assert text, (lang, key)
            assert lang == "RU" or text != ru[key] or key in SAME_AS_RU.get(lang, ()), (lang, key)
            assert not any(unicodedata.category(ch) == "So" for ch in text), (lang, key, text)
        for key, mark in PLACEHOLDERS.items():
            assert mark in words[key], (lang, key)


def test_counts_and_report_like_old_tab(history):
    from ui import analytics_data
    result = analytics_data.analyze()
    assert result["files"] == 1 and result["records"] == 115
    assert result["battles"] == 114 and result["wins"] == 34 + 18 + 10 + 9 + 9 + 9 + 9 + 3 + 4
    assert round(result["winrate"], 1) == round(105 * 100 / 114, 1)
    fire = {tuple(s["enemies"]): s for s in result["scenarios"] if s["room"] == "fire"}
    assert fire[("moloch", "vulcan")]["packs"][0]["status"] == "perfect"
    assert fire[("eden",)]["packs"][0]["status"] == "average" and fire[("eden",)]["packs"][0]["winrate"] == 50
    assert fire[("moloch", "vulcan")]["packs"][0]["avg_hp"] == 80


def test_golden_like_the_bot(history):
    from ui import analytics_data
    golden = analytics_data.analyze()["golden"]
    assert [(g["room"], g["enemies"], sorted(g["team"])) for g in golden] == [
        ("fire", ["moloch", "vulcan"], sorted(FIRE_GOLD)), ("earth", ["eden", "silva"], sorted(EARTH_GOLD))]
    assert (golden[0]["wins"], golden[0]["battles"]) == (34, 37)


def test_window_reads_rules_like_the_bot(history):
    """all_packs и situational_packs окна — те же, что у rules_engine (окно его не импортирует: он при импорте
    правит файлы и печатает строку [ПРАВИЛА])."""
    import rules_engine
    from ui import analytics_data
    engine = rules_engine.RulesEngine()
    cache = analytics_data.read_rules_files()
    assert sorted(map(sorted, analytics_data.all_packs(cache))) == sorted(map(sorted, engine.all_packs()))
    for room in analytics_data.ROOMS:
        assert analytics_data.situational_packs(cache, room) == engine.situational_packs(room)
    assert analytics_data.titan_name_ru("araji") == rules_engine.titan_name_ru("araji")


def test_applied_rule_is_the_bots_rule(history, monkeypatch):
    import rules_engine
    from ui import analytics_data, rules_list
    golden = analytics_data.analyze()["golden"]
    writes = []
    original = rules_list.write_rules_file
    monkeypatch.setattr(rules_list, "write_rules_file", lambda room, data: (writes.append(room), original(room, data)))
    added, skipped, broken = analytics_data.apply_golden(golden, write=rules_list.write_rules_file)
    assert [room for room, _r in added] == ["fire", "earth"] and not skipped and not broken
    assert sorted(writes) == ["earth", "fire"]                                 # по разу в файл стихии
    fire = read_yaml(history / "bot_data" / "rules" / "fire.yml")
    # Бот записал бы то же самое (main.py:add_golden_rules: пак из tactics.golden_packs — по алфавиту) — в другой папке
    os.makedirs("bot_copy/bot_data/rules")
    write_yaml("bot_copy/bot_data/rules/fire.yml", {"default_team": FIRE, "rules": []})
    monkeypatch.chdir("bot_copy")
    bot_rule = rules_engine.RulesEngine().add_golden_rule("fire", ["vulcan", "moloch"], sorted(FIRE_GOLD), 34, 37, 80)
    assert fire["rules"][0] == bot_rule
    assert fire["rules"][0]["source"] == "golden" and "special_ult" not in fire["rules"][0]
    earth = read_yaml(history / "bot_data" / "rules" / "earth.yml")
    assert earth["rules"][1]["enabled"] is False and earth["rules"][1]["team"] == ["angus"]   # выключенное не тронуто


def test_apply_does_not_duplicate_and_skips_broken(history):
    from ui import analytics_data
    golden = analytics_data.analyze()["golden"]
    analytics_data.apply_golden(golden[:1])
    added, skipped, broken = analytics_data.apply_golden(golden)              # огонь уже есть — не дублируется
    assert [room for room, _r in added] == ["earth"] and [g["room"] for g in skipped] == ["fire"]
    assert len(read_yaml(history / "bot_data" / "rules" / "fire.yml")["rules"]) == 1
    (history / "bot_data" / "rules" / "fire.yml").write_text("rules: [oops", encoding="utf-8")
    added, skipped, broken = analytics_data.apply_golden(golden[:1])
    assert broken == ["fire"] and not added
    assert (history / "bot_data" / "rules" / "fire.yml").read_text(encoding="utf-8") == "rules: [oops"
    assert analytics_data.analyze()["golden"] == []      # после внедрения правило против этих врагов уже есть


def test_no_history(workdir):
    from ui import analytics_data
    result = analytics_data.analyze()
    assert (result["files"], result["battles"], result["winrate"], result["golden"]) == (0, 0, 0.0, [])


# ── На виртуальном экране ────────────────────────────────────────────────────
@pytest.fixture
def page(history):
    from test_ui_rules import Quiet
    import test_ui_app  # noqa: F401
    from ui import app as app_mod
    from ui import icons
    icons.clear_cache()
    window = app_mod.App(settings_path=str(history / "ui_settings.json"), status_watcher=Quiet(),
                         hotkey_watcher=Quiet())
    window.geometry("1100x720+0+0")
    window.select_frame("analytics")
    pump(window, 0.3)
    yield window.frames["analytics"]
    if not window._closing:
        window.shutdown()


def console(page):
    return page.console.get("1.0", "end")


@needs_gui
def test_before_analysis(page):
    assert page.empty.winfo_ismapped() and not page.scroll.winfo_ismapped()
    assert page.empty_title.cget("text") == "Золотых правил пока нет"
    assert page.last_value.cget("text") == "ещё не запускался"
    assert page.apply_button.cget("state") == "disabled"
    assert "[СИСТЕМА] Ожидаю запуска анализа" in console(page)


@needs_gui
def test_analysis_cards_and_apply(page, history):
    page.run_analysis()
    assert page.run_button.cget("state") == "disabled" and page.run_button.cget("text") == "Идёт анализ…"
    assert pump(page, 5, until=lambda: not page.running)
    assert page.tiles["battles"][1].cget("text") == "114" and page.tiles["golden"][1].cget("text") == "2"
    assert len(page.cards) == 2 and all(card.on for card in page.cards)          # найденные сразу отмечены
    assert page.apply_button.cget("text") == "Внедрить золотые правила (2)"
    text = console(page)
    assert "[АНАЛИЗ] Читаю историю боёв: записей 115, файлов 1" in text
    assert "ИДЕАЛЬНО | Пак: Ашерон, Алекто, Араджи, Игнис, Молох" in text and "СРЕДНЕ" in text
    assert "[ГОТОВО] Найдено золотых правил: 2" in text
    assert page.last_value.cget("text").startswith("сегодня, ")
    page.cards[1].check.toggle()                                               # землю не внедряем
    assert page.apply_button.cget("text") == "Внедрить золотые правила (1)"
    page.toggle_all()
    assert all(card.on for card in page.cards)
    page.toggle_all()
    assert not any(card.on for card in page.cards) and page.apply_button.cget("state") == "disabled"
    page.cards[0].check.toggle()
    page.apply_golden()
    fire = read_yaml(history / "bot_data" / "rules" / "fire.yml")
    assert fire["rules"][0]["name"].startswith("Золотое правило против: Молох, Вулкан")
    assert len(read_yaml(history / "bot_data" / "rules" / "earth.yml")["rules"]) == 1   # землю не отмечали
    assert len(page.cards) == 1 and page.cards[0].gold["room"] == "earth" and not page.cards[0].on
    assert "[ГОТОВО] Огонь: правило против Молох, Вулкан" in console(page)
    assert "Внедрено правил: 1" in console(page)


@needs_gui
def test_language_and_no_history(page, history):
    for path in (history / "bot_data" / "logs").glob("*.jsonl"):
        path.unlink()
    page.run_analysis()
    assert pump(page, 5, until=lambda: not page.running)
    assert "[ОШИБКА] История боёв не найдена" in console(page)
    assert page.empty_title.cget("text") == "Новых золотых правил нет"
    page.winfo_toplevel().set_language("EN")
    pump(page, 0.2)
    assert "[ERROR] No battle history found" in console(page) and page.run_button.cget("text") == "Run log analysis"


CLOSE_SCRIPT = textwrap.dedent('''
    import os, sys, threading
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_ui_app  # noqa: F401
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    from ui import analytics_data
    from ui import app as app_mod
    hang = threading.Event()
    analytics_data.analyze = lambda folder=None: (hang.wait(60), {})[1]      # анализ «завис»
    class Quiet:
        def start(self): return self
        def stop(self): pass
    app = app_mod.App(settings_path=os.path.join(os.getcwd(), "ui_settings.json"), status_watcher=Quiet(),
                      hotkey_watcher=Quiet())
    def step1():
        app.select_frame("analytics")
        app.frames["analytics"].run_analysis()
        print("RUNNING", app.frames["analytics"].running, flush=True)
        app.after(300, lambda: app.tk.call(app.protocol("WM_DELETE_WINDOW")))
    app.after(500, step1)
    app.mainloop()
    print("EXITED", flush=True)
''')


@needs_gui
def test_process_exits_while_analysis_hangs(history):
    script = f"ROOT = {str(ROOT)!r}\n" + CLOSE_SCRIPT
    result = subprocess.run([sys.executable, "-c", script], cwd=history, capture_output=True, text=True,
                            timeout=60, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = result.stdout + result.stderr
    assert "RUNNING True" in result.stdout and "EXITED" in result.stdout, out
    assert result.returncode == 0 and "Traceback" not in result.stderr, out
