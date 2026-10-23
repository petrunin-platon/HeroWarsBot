"""Задача 15, шаг 5в: «Мастер правил → Правила и перехваты» (ui/rules_intercepts.py) и окно «Новое правило»
(ui/rule_editor.py); что показать и как записать — ui/rules_list.py.

Без окна (ui/rules_list.py):
- значок по смыслу (ваш ответ 4.2), короткие имена правил бота (4.3), «Спросить вас» для пака [STOP];
- стрелки, тумблер (enabled: false — бот пропускает, rules_engine.rule_enabled), удалить и «Вернуть», «Очистить» —
  то, что видно; окно «Новое правило» не теряет скрытые поля (ошибка 4.4) и части условия, которых не показывает;
- «Сохранить настройки» пишет только стихии с правками и только список rules (основной пак остаётся); правила, которые
  бот запомнил, пока окно открыто, не теряются; бот читает сохранённое так же, как окно его показывает;
- новые надписи — на 13 языках.
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_intercepts.py):
- вкладка как в макете 03c, фильтры, ↑↓ только при одной стихии (как в старом окне, ваш ответ);
- тумблер, стрелки, ✕ и «Вернуть», «Очистить все правила» с вопросом → «Сохранить настройки» → файл;
- окно «Новое правило» как в макете 03d: новое правило, изменить правило, «+ Условие» с «Базы и комнат»;
- «Сохранить изменения?» называет вкладку правил; свежие правила бота видны после возврата на вкладку;
- наведение меняет только цвета; длинный список — лёгкие строки; процесс окна выходит сам после крестика.
"""
import copy
import importlib
import os
import subprocess
import sys
import textwrap
import time

import pytest

from test_ui_rules import PROFILE, ROOT, TEAMS, app, footer, needs_gui, open_dialog, pump, read_yaml, workdir, write_yaml  # noqa: F401

NEW_KEYS = ["ri_title", "ri_hint_room", "ri_hint_all", "ri_all", "ri_new", "ri_col_num", "ri_col_cond",
            "ri_col_action", "ri_col_on", "ri_clear", "ri_empty", "ri_tag_heal", "ri_tag_skip", "ri_tag_hp",
            "ri_tag_energy", "ri_tag_enemies", "ri_act_pack", "ri_act_ask", "ri_act_skip", "ri_cond_hp",
            "ri_cond_energy", "ri_cond_enemies", "ri_cond_fought", "ri_cond_none", "ri_name_auto", "ri_name_golden",
            "ri_by_auto", "ri_by_you", "ri_by_golden", "ri_up", "ri_down", "ri_edit", "ri_delete", "ri_switch",
            "ri_deleted", "ri_undo", "ri_cleared", "ri_added", "ri_clear_title", "ri_clear_text", "ri_clear_ok",
            "ri_where_all", "ri_broken", "re_title_new", "re_title_edit", "re_sub", "re_room", "re_name",
            "re_name_hint", "re_trigger", "re_by_hp", "re_by_energy", "re_by_enemies", "re_titan", "re_hp_below",
            "re_energy_below", "re_enemies", "re_enemies_count", "re_extra", "re_action", "re_ask", "re_skip",
            "re_skip_enemies", "re_fought", "re_fought_none", "re_fought_tip", "re_fought_clear", "re_pack",
            "re_pack_pick", "re_pack_none", "re_pack_not_needed", "re_save", "re_need_pack", "re_need_enemy",
            "re_need_number", "re_close", "pick_fought_title", "pick_fought_sub", "pick_need_one"]
PLACEHOLDERS = {"ri_cond_hp": ("{titan}", "{n}"), "ri_cond_energy": ("{titan}", "{n}"), "ri_cond_enemies": ("{names}",),
                "ri_cond_fought": ("{names}",), "ri_name_auto": ("{names}",), "ri_name_golden": ("{names}",),
                "ri_deleted": ("{name}",), "ri_cleared": ("{n}",), "ri_added": ("{name}",),
                "ri_clear_text": ("{n}", "{where}"), "ri_broken": ("{room}",), "re_enemies_count": ("{n}",),
                "re_extra": ("{text}",)}
# Одинаково с русским — по-украински и по-казахски так и пишут («№», «ХП», «Титан», «Триггер»)
SAME_AS_RU = {"UK": {"ri_col_num", "ri_tag_hp", "ri_cond_fought", "re_titan"},
              "KK": {"ri_col_num", "ri_tag_skip", "ri_tag_energy", "re_trigger", "re_titan"}}

HEAL = {"name": "Авто-отхил", "condition": {"titan_hp_below": {"araji": 65}},
        "team": ["sigurd", "araji", "rigel", "iyari", "lumira"]}
LEARNED = {"name": "Анти-пак против: Ангус, Сильва (при Араджи < 50% ХП)",
           "condition": {"titan_hp_below": {"araji": 50}, "enemies_contain": ["angus", "silva"]},
           "team": ["hyperion", "araji", "sigurd", "iyari", "lumira"], "source": "auto", "allowed_delta": 45,
           "special_ult": "angus", "stats": {"wins": 3}}
ASK = {"name": "Тяжёлая смешанная", "condition": {"enemies_contain": ["sigurd", "angus", "araji"]}, "team": ["STOP"]}
SKIP = {"name": "Сигурд в опасности", "condition": {"titan_hp_below": {"sigurd": 35}}, "team": [], "action": "skip"}
ENERGY = {"name": "Ульта Ангуса", "condition": {"titan_energy_below": {"angus": 30}},
          "team": ["angus", "pallant", "eden", "silva", "avalon"]}
GOLDEN = {"name": "Золотое правило против: Ангус, Авалон, Эдем (побед 9 из 10, ХП 80%)",
          "condition": {"enemies_contain": ["angus", "avalon", "eden"]},
          "team": ["araji", "acheron", "ignis", "vulcan", "moloch"], "source": "golden"}
FIRE_OFF = {"name": "Араджи ранен", "condition": {"titan_hp_below": {"araji": 40}}, "team": [], "action": "skip",
            "enabled": False}
RULES = {"earth": [ENERGY], "water": [SKIP], "fire": [GOLDEN, FIRE_OFF], "mix": [HEAL, LEARNED, ASK]}


def write_rules(workdir, rules=RULES):
    for room, items in rules.items():
        write_yaml(workdir / "bot_data" / "rules" / f"{room}.yml", {"default_team": TEAMS[room], "rules": items})


def file_rules(workdir, room):
    return read_yaml(workdir / "bot_data" / "rules" / f"{room}.yml")


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
            assert not any(unicodedata.category(ch) == "So" and ch not in "№°" for ch in text), (lang, key, text)   # без эмодзи
            for mark in PLACEHOLDERS.get(key, ()):
                assert mark in text, (lang, key, mark)


def test_tag_and_action_by_meaning():
    """Значок по смыслу (ваш ответ 4.2) и действие: пак [STOP] — «Спросить вас» (окно «Нет подходящего пака»)."""
    from ui import rules_list as rl
    assert [rl.tag(r) for r in (HEAL, LEARNED, ASK, SKIP, ENERGY, GOLDEN, FIRE_OFF)] == \
        ["heal", "enemies", "enemies", "skip", "energy", "enemies", "skip"]
    assert rl.tag({"condition": {"titan_hp_below": {"araji": 30}}, "team": ["STOP"]}) == "hp"   # ХП, но без смены пака
    assert rl.tag({"condition": {}, "team": []}) is None
    assert [rl.action(r) for r in (HEAL, ASK, SKIP)] == ["pack", "ask", "skip"]


def test_titles_of_bot_rules_are_short():
    """Правила бота — коротко на языке окна (ваш ответ 4.3), в файле имя то же; переименовали — видно ваше."""
    from ui import rules_list as rl
    assert rl.title_and_sub(LEARNED, "RU") == ("Авто: Ангус + Сильва в комнате",
                                               "Запомнил бот после отката · Араджи: ХП ниже 50%")
    assert rl.title_and_sub(dict(LEARNED, source="gui"), "RU")[1].startswith("Ваш пак после отката")
    assert rl.title_and_sub(GOLDEN, "RU") == ("Золотое: Ангус + Авалон + Эдем в комнате",
                                              "Пак часто побеждал этих врагов")
    assert rl.title_and_sub(LEARNED, "EN")[0] == "Auto: Angus + Sylva in the room"
    assert rl.title_and_sub(dict(LEARNED, name="Мой анти-пак"), "RU") == (
        "Мой анти-пак", "Враги в комнате: Ангус, Сильва · Араджи: ХП ниже 50%")
    assert rl.title_and_sub(dict(GOLDEN, source=None), "RU")[0] == GOLDEN["name"]   # не бот — имя из файла
    assert rl.title_and_sub(ASK, "RU") == ("Тяжёлая смешанная", "Враги в комнате: Сигурд, Ангус, Араджи")
    fought = {"name": "", "condition": {"titan_energy_below": {"angus": 30}, "require_fought": ["angus", "eden"]}}
    assert rl.title_and_sub(fought, "RU")[0] == "Ангус: энергия ниже 30% · обкатка: Ангус, Эдем"


def test_visible_order_and_numbers():
    from ui import rules_list as rl
    rules = copy.deepcopy(RULES)
    assert [(room, i) for room, i, _r in rl.visible(rules, None)] == \
        [("earth", 0), ("water", 0), ("fire", 0), ("fire", 1), ("mix", 0), ("mix", 1), ("mix", 2)]
    assert [(room, i) for room, i, _r in rl.visible(rules, "fire")] == [("fire", 0), ("fire", 1)]


def test_list_edits_in_form():
    from ui import rules_list as rl
    rules = copy.deepcopy(RULES)
    assert not rl.move(rules, "mix", 0, -1) and not rl.move(rules, "mix", 2, 1)   # край стихии
    assert rl.move(rules, "mix", 0, 1) and rules["mix"][:2] == [LEARNED, HEAL]
    rl.set_enabled(rules["mix"][0], False)
    assert rules["mix"][0]["enabled"] is False and not rl.enabled(rules["mix"][0])
    rl.set_enabled(rules["mix"][0], True)
    assert rules["mix"][0] == LEARNED                                            # пометка убрана совсем
    removed = rl.remove(rules, "mix", 1)
    assert removed == ("mix", 1, HEAL) and rules["mix"] == [LEARNED, ASK]
    rl.put_back(rules, [removed])
    assert rules["mix"] == [LEARNED, HEAL, ASK]
    cleared = rl.clear(rules, "mix")                                             # видно только «Смешанную»
    assert rules["mix"] == [] and rules["fire"] == [GOLDEN, FIRE_OFF] and len(cleared) == 3
    rl.put_back(rules, cleared)
    assert rules["mix"] == [LEARNED, HEAL, ASK]
    everything = rl.clear(rules, None)
    assert len(everything) == 7 and all(not items for items in rules.values())
    rl.put_back(rules, everything)
    assert rules["fire"] == [GOLDEN, FIRE_OFF] and rules["earth"] == [ENERGY]


def test_editor_keeps_hidden_fields_and_extra_condition():
    """Ошибка 4.4: изменение правила не теряет source, allowed_delta, special_ult, enabled и прочее; ХП Араджи
    в условии запомненного правила окно не показывает, но сохраняет."""
    from ui import rules_list as rl
    rule = dict(LEARNED, enabled=False)
    values = rl.editor_values(rule, "mix")
    assert (values["trigger"], values["enemies"], values["action"]) == ("enemies", ["angus", "silva"], "pack")
    assert values["extra"] == {"titan_hp_below": {"araji": 50}} and values["name"] == LEARNED["name"]
    values["enemies"] = ["angus", "silva", "eden"]
    new = rl.rule_from_editor(values, rule)
    assert new["condition"] == {"titan_hp_below": {"araji": 50}, "enemies_contain": ["angus", "silva", "eden"]}
    for key in ("source", "allowed_delta", "special_ult", "stats", "enabled", "name", "team"):
        assert new[key] == rule[key], key
    assert rule["condition"]["enemies_contain"] == ["angus", "silva"]   # исходное правило не тронуто
    # Сменили триггер на ХП: «ещё в условии» с тем же ключом заменяется новым значением
    values.update(trigger="hp", titan="sigurd", value=30)
    assert rl.rule_from_editor(values, rule)["condition"] == {"titan_hp_below": {"sigurd": 30}}


def test_rule_from_editor_actions_and_name():
    from ui import rules_list as rl
    values = rl.editor_values(None, "fire")
    assert (values["trigger"], values["titan"], values["value"]) == ("hp", "araji", 35)   # как старое окно
    values.update(action="ask")
    rule = rl.rule_from_editor(values, None, "RU")
    assert rule == {"name": "Араджи: ХП ниже 35%", "condition": {"titan_hp_below": {"araji": 35}}, "team": ["STOP"]}
    values.update(action="skip", fought=["vulcan"])
    rule = rl.rule_from_editor(values, None, "EN")
    assert rule == {"name": "Araji: HP below 35% · already fought: Vulcan",
                    "condition": {"titan_hp_below": {"araji": 35}, "require_fought": ["vulcan"]},
                    "team": [], "action": "skip"}
    values.update(action="pack", team=["araji", "ignis", "vulcan"], name="  Мой отхил ", fought=[])
    rule = rl.rule_from_editor(dict(values), dict(SKIP))
    assert "action" not in rule and rule["team"] == ["araji", "ignis", "vulcan"] and rule["name"] == "Мой отхил"


def test_locate_rule_after_list_changed():
    from ui import rules_list as rl
    rules = copy.deepcopy(RULES)
    heal = rules["mix"][0]
    rules["mix"].insert(0, dict(GOLDEN))                 # бот запомнил правило, пока окно правила открыто
    assert rl.locate(rules, "mix", heal) == 1
    assert rl.locate(copy.deepcopy(rules), "mix", heal) == 1   # список перечитан с диска — такое же правило
    assert rl.locate(rules, "fire", heal) is None


def test_editor_problems():
    from ui import rules_list as rl
    values = rl.editor_values(None, "mix")
    assert rl.editor_problem(values) == "re_need_pack"
    values["team"] = ["sigurd", "araji", "rigel"]
    assert rl.editor_problem(values) is None
    values["value"] = None
    assert rl.editor_problem(values) == "re_need_number"
    values.update(value=40, trigger="enemies")
    assert rl.editor_problem(values) == "re_need_enemy"     # «По врагам» без врагов срабатывало бы в каждой комнате
    values.update(enemies=["eden"], action="skip")
    assert rl.editor_problem(values) == "re_skip_enemies"   # врагов бот видит только после выбора двери
    values["action"] = "ask"
    assert rl.editor_problem(values) is None


def test_fit_room():
    from ui import rules_list as rl
    values = rl.editor_values(None, "mix")
    values.update(titan="sigurd", team=["sigurd", "araji", "rigel", "nova", "orm"])
    rl.fit_room(values, "water")
    assert values["titan"] == "sigurd" and values["team"] == ["sigurd", "nova", "orm"]
    rl.fit_room(values, "fire")
    assert values["titan"] == "araji" and values["team"] == []   # в комнату огня — только огненные


def test_save_writes_only_changed_rooms(workdir):
    from ui import rules_list as rl
    write_rules(workdir)
    before = {room: (workdir / "bot_data" / "rules" / f"{room}.yml").read_text(encoding="utf-8")
              for room in rl.ROOMS}
    rules, broken = rl.read_all()
    saved = copy.deepcopy(rules)
    assert broken == [] and rules == RULES
    assert rl.save_rules(saved, rules) == ([], [], {})                      # нечего сохранять — ничего не пишется
    rl.set_enabled(rules["fire"][0], False)
    assert rl.save_rules(saved, rules) == (["fire"], [], {})
    data = file_rules(workdir, "fire")
    assert data["default_team"] == TEAMS["fire"] and data["rules"][0]["enabled"] is False
    assert data["rules"][0]["source"] == "golden" and saved == rules
    for room in ("earth", "water", "mix"):
        assert (workdir / "bot_data" / "rules" / f"{room}.yml").read_text(encoding="utf-8") == before[room]


def test_save_keeps_rules_the_bot_learned_meanwhile(workdir, capsys):
    """Окно открыто, бот тем временем запомнил правило (и обновил старое с тем же условием) — после «Сохранить» оно
    наверху, а старое не возвращается; бот берёт сохранённое так, как окно его показывает."""
    from ui import rules_list as rl
    write_rules(workdir)
    rules, _ = rl.read_all()
    saved = copy.deepcopy(rules)
    sys.modules.pop("rules_engine", None)
    engine = importlib.import_module("rules_engine").RulesEngine()
    try:
        engine.learn_new_rule("mix", ["angus", "silva"], ["rigel", "iyari", "lumira", "amon", "sigurd"],
                              base_condition={"titan_hp_below": {"araji": 50}}, source="auto")
        rl.set_enabled(rules["mix"][0], False)           # вы выключили «Авто-отхил»
        written, broken, added = rl.save_rules(saved, rules)
        assert written == ["mix"] and broken == [] and len(added["mix"]) == 1
        data = file_rules(workdir, "mix")["rules"]
        assert data[0]["team"] == ["rigel", "iyari", "lumira", "amon", "sigurd"]   # правило бота — наверху
        assert data[1] == dict(HEAL, enabled=False) and data[2] == ASK              # LEARNED бот заменил — его нет
        assert rules["mix"] == data and saved["mix"] == data
        engine = importlib.import_module("rules_engine").RulesEngine()
        assert "[ПРАВИЛА] Выключено правил: 2" in capsys.readouterr().out
        assert engine.battle_decision("mix", ["eden"], {"araji": {"hp": 40}})["team"] == TEAMS["mix"]   # отхил выключен
    finally:
        sys.modules.pop("rules_engine", None)


def test_broken_rules_file_is_not_touched(workdir):
    from ui import rules_list as rl
    write_rules(workdir)
    path = workdir / "bot_data" / "rules" / "water.yml"
    path.write_text("rules: [broken\n", encoding="utf-8")
    rules, broken = rl.read_all()
    assert broken == ["water"] and rules["water"] == []
    saved = copy.deepcopy(rules)
    rules["water"].append(dict(SKIP))
    assert rl.save_rules(saved, rules) == ([], ["water"], {})
    assert path.read_text(encoding="utf-8") == "rules: [broken\n"


# ── Окно на виртуальном экране ───────────────────────────────────────────────
def open_rules(app, workdir, rules=RULES):
    write_rules(workdir, rules)
    page = app.frames["rules"]
    page.load()
    page.rebuild_base()
    app.select_frame("rules")
    page.tabs.set(page.text("rb_tab_rules"))
    page._tab_chosen(page.text("rb_tab_rules"))
    pump(app)
    return page, page.intercepts


def shown_rows(tab):
    return [row for rows in tab.rows.values() for row in rows if row.winfo_ismapped()]


def open_editor(app, page):
    from ui.rule_editor import RuleEditor
    pump(app, 2, until=lambda: page._editor is not None and page._editor.winfo_viewable())
    assert isinstance(page._editor, RuleEditor)
    return page._editor


@needs_gui
def test_tab_like_mockup(app, workdir):
    page, tab = open_rules(app, workdir)
    assert tab.winfo_viewable() and page.shown_tab_widget() is tab
    rows = shown_rows(tab)
    assert [(r.room, r.index) for r in rows] == [("earth", 0), ("water", 0), ("fire", 0), ("fire", 1),
                                                 ("mix", 0), ("mix", 1), ("mix", 2)]
    assert tab.count_pill.cget("text") == "7" and tab.hint.cget("text") == "Порядок меняется, когда выбрана одна стихия"
    assert not rows[0].up.winfo_ismapped()                       # «Все» — без стрелок (как в старом окне)
    learned = tab.rows["mix"][1]
    assert learned.title.full == "Авто: Ангус + Сильва в комнате"
    assert learned.sub.full == "Запомнил бот после отката · Араджи: ХП ниже 50%"
    assert [t.titan for t in learned.action.winfo_children()[1].winfo_children()] == LEARNED["team"]
    ask = tab.rows["mix"][2]
    assert any(getattr(w, "cget", None) and w.cget("text") == "Спросить вас" for w in ask.action.winfo_children())
    off = tab.rows["fire"][1]
    assert not off.switch.on and off.title.cget("fg") != tab.rows["fire"][0].title.cget("fg")   # бледное
    tab.choose("fire")
    pump(app)
    rows = shown_rows(tab)
    assert [(r.room, r.index) for r in rows] == [("fire", 0), ("fire", 1)] and tab.count_pill.cget("text") == "2"
    assert rows[0].up.winfo_ismapped() and not rows[0].up.enabled and rows[0].down.enabled and not rows[1].down.enabled
    assert tab.hint.cget("text") == "Правило выше в списке проверяется первым"
    assert footer(page) == "Все изменения сохранены"


@needs_gui
def test_toggle_move_delete_undo_and_save(app, workdir):
    from ui.widgets import Toast
    page, tab = open_rules(app, workdir)
    tab.choose("mix")
    pump(app)
    tab.rows["mix"][0].switch._clicked()                         # тумблер «Авто-отхил» → выключен
    assert page.rules["mix"][0]["enabled"] is False and footer(page) == "Есть несохранённые изменения"
    tab.rows["mix"][2].up._clicked()                             # «Тяжёлая смешанная» — выше
    assert [r["name"] for r in page.rules["mix"]] == ["Авто-отхил", "Тяжёлая смешанная", LEARNED["name"]]
    assert [r.number.cget("text") for r in tab.rows["mix"]] == ["1", "2", "3"]
    assert tab.rows["mix"][1].title.full == "Тяжёлая смешанная"
    tab.rows["mix"][2].delete_button._clicked()
    assert len(page.rules["mix"]) == 2 and len(tab.rows["mix"]) == 2
    Toast._open[-1]._action()                                    # «Вернуть» в уведомлении
    pump(app)
    assert page.rules["mix"][2] == LEARNED and len(tab.rows["mix"]) == 3
    assert file_rules(workdir, "mix")["rules"] == [HEAL, LEARNED, ASK]   # до «Сохранить» файл не меняется
    page.save_button.invoke()
    data = file_rules(workdir, "mix")
    assert data["rules"] == [dict(HEAL, enabled=False), ASK, LEARNED] and data["default_team"] == TEAMS["mix"]
    assert footer(page) == "Все изменения сохранены"
    assert "[GUI] Правила сохранены: Смешанная." in app.frames["dash"].log_text()


@needs_gui
def test_clear_asks_and_removes_what_is_shown(app, workdir):
    import customtkinter as ctk
    from ui.widgets import Toast
    page, tab = open_rules(app, workdir)
    tab.choose("fire")
    pump(app)
    tab.clear_button.invoke()
    dialog = open_dialog(app)
    assert dialog is not None and dialog.title() == "Удалить все правила?"
    texts = [w.cget("text") for w in dialog.body.winfo_children() if isinstance(w, ctk.CTkLabel)]
    assert any(t.startswith("Будут удалены правила: 2 (Огонь).") for t in texts), texts
    dialog._finish("cancel")
    pump(app)
    assert page.rules["fire"] and not page.dirty()               # «Отмена» — ничего не удалено
    tab.ask_clear()
    open_dialog(app)._finish("confirm")                          # «Удалить все»
    pump(app)
    assert page.rules["fire"] == [] and page.rules["mix"] == [HEAL, LEARNED, ASK] and shown_rows(tab) == []
    assert tab.empty.winfo_ismapped() and tab.clear_button.cget("state") == "disabled"
    Toast._open[-1]._action()                                    # «Вернуть»
    pump(app)
    assert page.rules == RULES and not page.dirty()


@needs_gui
def test_new_rule_from_editor(app, workdir):
    page, tab = open_rules(app, workdir)
    tab.new_button.invoke()
    editor = open_editor(app, page)
    assert editor.values["room"] == "mix" and not editor.save_button.cget("state") == "normal"
    assert editor.problem_label.cget("text") == "Выберите состав: от 3 до 5 титанов"
    editor.room_menu._chosen("Огонь")
    editor._trigger_chosen("По врагам")
    pump(app)
    assert editor.enemy_panel.winfo_ismapped() and not editor.number_panel.winfo_ismapped()
    assert editor.skip_box.cget("state") == "disabled" and editor.skip_note.winfo_ismapped()   # по врагам не запретить
    for enemy in ("vulcan", "moloch"):
        editor.enemy_tiles[enemy]._frame_click()
    assert editor.values["enemies"] == ["vulcan", "moloch"] and editor.enemy_tiles["moloch"].selected
    editor._pack_picked(["alecto", "ignis", "araji", "acheron", "moloch"])
    assert editor.save_button.cget("state") == "normal" and editor.problem_label.cget("text") == ""
    editor.save_button.invoke()
    pump(app)
    assert editor.done and page.rules["fire"][0] == {
        "name": "Враги в комнате: Вулкан, Молох", "condition": {"enemies_contain": ["vulcan", "moloch"]},
        "team": ["alecto", "ignis", "araji", "acheron", "moloch"]}
    assert tab.rows["fire"][0].title.full == "Враги в комнате: Вулкан, Молох"
    assert footer(page) == "Есть несохранённые изменения"
    page.save_button.invoke()
    assert file_rules(workdir, "fire")["rules"][0]["condition"] == {"enemies_contain": ["vulcan", "moloch"]}


@needs_gui
def test_edit_rule_keeps_hidden_fields(app, workdir):
    page, tab = open_rules(app, workdir)
    tab.rows["mix"][1].edit_button._clicked()
    editor = open_editor(app, page)
    assert editor.values["trigger"] == "enemies" and editor.extra_note is not None
    assert "Араджи: ХП ниже 50%" in editor.extra_note.cget("text")
    assert editor.name_entry.get() == LEARNED["name"]
    editor.enemy_tiles["eden"]._frame_click()
    editor.save_button.invoke()
    pump(app)
    rule = page.rules["mix"][1]
    assert rule["condition"] == {"titan_hp_below": {"araji": 50}, "enemies_contain": ["angus", "eden", "silva"]}
    assert all(rule[k] == LEARNED[k] for k in ("source", "allowed_delta", "special_ult", "stats", "name", "team"))
    # Стихию поменяли — правило переезжает на 1-е место новой стихии
    tab.rows["mix"][0].edit_button._clicked()
    editor = open_editor(app, page)
    editor.room_menu._chosen("Вода")
    assert editor.values["team"] == [] and editor.values["titan"] == "hyperion"
    editor._pack_picked(["sigurd", "nova", "mairi"])
    editor.save_button.invoke()
    pump(app)
    assert page.rules["water"][0]["team"] == ["sigurd", "nova", "mairi"] and len(page.rules["mix"]) == 2


@needs_gui
def test_fought_picker_takes_one_titan(app, workdir):
    from ui.titan_picker import TitanPicker
    page, tab = open_rules(app, workdir)
    page.open_rule_editor("earth")
    editor = open_editor(app, page)
    editor.fought_row._frame_click()
    pump(app, 2, until=lambda: editor._picker is not None and editor._picker.winfo_viewable())
    picker = editor._picker
    assert isinstance(picker, TitanPicker) and picker.min_titans == 1
    picker.toggle("araji")                                       # любые стихии
    assert picker.apply_button.cget("state") == "normal"
    picker.apply()
    pump(app)
    assert editor.values["fought"] == ["araji"] and "Араджи" in editor.fought_row.value.cget("text")
    editor.clear_fought()
    assert editor.values["fought"] == [] and not editor.fought_row.clear.winfo_ismapped()
    editor.close()


@needs_gui
def test_condition_button_opens_new_editor(app, workdir):
    from ui.widgets import Toast
    page, _tab = open_rules(app, workdir)
    page.tabs.set(page.text("rb_tab_base"))
    page._tab_chosen(page.text("rb_tab_base"))
    pump(app)
    page.base.rooms["water"].condition.invoke()                  # «+ Условие» у Воды
    editor = open_editor(app, page)
    assert editor.values["room"] == "water" and editor.room_menu.get() == "water"
    editor.ask_box.toggle()                                      # «Остановиться и спросить меня» — состав не нужен
    assert editor.values["action"] == "ask" and editor.save_button.cget("state") == "normal"
    editor.save_button.invoke()
    pump(app)
    assert page.rules["water"][0] == {"name": "Гиперион: ХП ниже 35%", "condition": {"titan_hp_below": {"hyperion": 35}},
                                      "team": ["STOP"]}
    assert page.dirty_tab() == "rules" and Toast._open[-1].top is not None   # «Правило … добавлено во вкладку …»
    assert file_rules(workdir, "water")["rules"] == [SKIP]       # в файл — только «Сохранить настройки»


@needs_gui
def test_leave_names_rules_tab(app, workdir):
    page, tab = open_rules(app, workdir)
    tab.rows["earth"][0].switch._clicked()
    app.select_frame("main")
    dialog = open_dialog(app)
    assert dialog is not None and app.page == "rules"
    assert page.dirty_tab() == "rules"
    dialog.close()
    pump(app)


@needs_gui
def test_fresh_rules_from_disk_when_tab_shown(app, workdir):
    page, tab = open_rules(app, workdir)
    rules = copy.deepcopy(RULES)
    rules["earth"].insert(0, {"name": "Новое от бота", "condition": {"enemies_contain": ["nova"]},
                              "team": ["angus", "avalon", "eden"], "source": "auto"})
    write_rules(workdir, rules)
    page.tabs.set(page.text("rb_tab_base"))
    page._tab_chosen(page.text("rb_tab_base"))
    page.tabs.set(page.text("rb_tab_rules"))
    page._tab_chosen(page.text("rb_tab_rules"))
    pump(app)
    assert len(tab.rows["earth"]) == 2 and page.rules == rules and not page.dirty()


@needs_gui
def test_hover_changes_only_colors(app, workdir):
    page, tab = open_rules(app, workdir)
    row = tab.rows["mix"][0]
    for widget in (row.edit_button, row.delete_button):
        calls = []
        original = widget.configure

        def spy(_orig=original, **kwargs):
            calls.append(kwargs)
            return _orig(**kwargs)
        widget.configure = spy
        widget._paint(True)
        widget._paint(True)
        widget._paint(False)
        assert len(calls) == 2 and all(set(c) == {"bg"} for c in calls), widget
        widget.configure = original
    page.open_rule_editor("mix")
    editor = open_editor(app, page)
    for widget in (editor.enemy_tiles["eden"], editor.fought_row):
        calls = []
        original = widget.configure

        def spy(_orig=original, **kwargs):
            calls.append(kwargs)
            return _orig(**kwargs)
        widget.configure = spy
        widget._frame_enter()
        widget._frame_enter()
        assert len(calls) == 1 and set(calls[0]) == {"border_color"}, widget
        widget.configure = original
    editor.close()


@needs_gui
def test_old_skip_by_enemies_can_be_unticked(app, workdir):
    """Старое окно давало сделать «Skip по врагам» (бот его не выполняет): галочку можно снять, а поставить снова — нет."""
    rule = {"name": "Skip по врагам", "condition": {"enemies_contain": ["eden"]}, "team": [], "action": "skip"}
    page, tab = open_rules(app, workdir, {**RULES, "earth": [rule]})
    tab.rows["earth"][0].edit_button._clicked()
    editor = open_editor(app, page)
    assert editor.skip_box.get() and editor.skip_box.cget("state") == "normal"
    assert editor.save_button.cget("state") == "disabled"
    editor.skip_box.toggle()
    assert editor.values["action"] == "pack" and editor.skip_box.cget("state") == "disabled"
    editor.close()


@needs_gui
def test_long_title_is_cut_with_ellipsis(app, workdir):
    long_name = "Очень длинное название правила, которое не помещается в строку списка ни при какой ширине окна " * 2
    page, tab = open_rules(app, workdir, {**RULES, "water": [dict(SKIP, name=long_name)]})
    row = tab.rows["water"][0]
    pump(app, 1, until=lambda: row.title.cget("text").endswith("…"))
    shown = row.title.cget("text")
    assert shown.endswith("…") and long_name.startswith(shown[:-1].rstrip()) and row.title.full == long_name.strip()
    assert row.winfo_width() <= tab.list.winfo_width()            # строка не шире списка


@needs_gui
def test_long_list_is_light(app, workdir):
    """Бот запоминает правила сам — список бывает длинным. В строке — только обычные элементы Tk; список строится
    частями (окно между ними отвечает), фильтр строки не перестраивает."""
    import customtkinter as ctk
    many = {room: [dict(LEARNED, name=f"Правило {room} {i}") for i in range(12)] for room in ("earth", "water", "fire",
                                                                                               "mix")}
    page, tab = open_rules(app, workdir, many)
    started = time.perf_counter()
    tab.rebuild()                                                # первые строки — сразу, остальные — частями
    first = time.perf_counter() - started
    assert sum(len(items) for items in tab.rows.values()) < 48 and tab._pending
    assert tab.count_pill.cget("text") == "48"
    tab.finish_building()
    rows = [row for items in tab.rows.values() for row in items]
    assert len(rows) == 48 and [r.index for r in tab.rows["fire"]] == list(range(12))

    def ctk_widgets(widget):
        found = 1 if isinstance(widget, ctk.CTkBaseClass) else 0
        return found + sum(ctk_widgets(child) for child in widget.winfo_children())
    assert all(ctk_widgets(row) == 0 for row in rows)           # в строке нет холстов CustomTkinter
    assert first < 0.5
    started = time.perf_counter()
    tab.choose("water")
    app.update()
    tab.choose(None)
    app.update()
    assert time.perf_counter() - started < 0.5                   # фильтр не перестраивает строки
    assert [row for items in tab.rows.values() for row in items] == rows


CLOSE_SCRIPT = textwrap.dedent('''
    import os, sys
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_ui_app  # noqa: F401  (заглушки pygetwindow/pyautogui для старых вкладок)
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    from ui import app as app_mod
    class Quiet:
        def start(self): return self
        def stop(self): pass
    app = app_mod.App(settings_path=os.path.join(os.getcwd(), "ui_settings.json"), status_watcher=Quiet(),
                      hotkey_watcher=Quiet())
    def step1():
        page = app.frames["rules"]
        app.select_frame("rules")
        page._tab_chosen(page.text("rb_tab_rules"))
        page.open_rule_editor("mix")
        app.after(500, step2)
    def step2():
        page = app.frames["rules"]
        page._editor._pick_pack()
        app.after(500, step3)
    def step3():
        page = app.frames["rules"]
        print("OPEN", page._editor.winfo_exists() == 1, page._editor._picker is not None, flush=True)
        app.tk.call(app.protocol("WM_DELETE_WINDOW"))   # то же, что крестик окна программы
    app.after(500, step1)
    app.mainloop()
    print("EXITED", flush=True)
''')


@needs_gui
def test_process_exits_with_rule_editor_open(workdir):
    write_yaml(workdir / "profile.yml", PROFILE)
    write_rules(workdir)
    script = f"ROOT = {str(ROOT)!r}\n" + CLOSE_SCRIPT
    result = subprocess.run([sys.executable, "-c", script], cwd=workdir, capture_output=True, text=True,
                            timeout=60, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = result.stdout + result.stderr
    assert "OPEN True True" in result.stdout and "EXITED" in result.stdout, out
    assert result.returncode == 0 and "Traceback" not in result.stderr, out
