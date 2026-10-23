"""Задача 15, шаг 5а: «Мастер правил → База и комнаты» (ui/rules_page.py, ui/rules_base.py, ui/rules_store.py).

Без окна (ui/rules_store.py):
- значения формы — по правилам бота (нет ключа — то, что взял бы бот), цель одна;
- «Сохранить настройки» пишет только поменянное: остальные ключи профиля и правки других окон остаются,
  нечего сохранять — файл не пишется (ваше замечание: беречь диск); битый профиль не трогается;
- бот читает сохранённое так же, как окно его показывает (tactics.Settings, ui/launch_config.py);
- основной пак — только default_team в bot_data/rules/<стихия>.yml; запасные паки; «Восстановить / Сброс».
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_rules.py):
- страница как в макете, правка → «Есть несохранённые изменения», «Сохранить настройки» → файлы и «Все изменения сохранены»;
- поле с ошибкой не даёт сохранить; уйти со страницы и закрыть окно с несохранёнными изменениями — «Сохранить изменения?»;
- смена языка не теряет несохранённое; пока бот работает — подсказка в футере; наведение меняет только цвета.
"""
import os
import sys
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NEW_KEYS = ["rb_tab_base", "rb_tab_tactics", "rb_tab_rules", "rb_session", "rb_goals_title", "rb_goal_label",
            "rb_goal_zero", "rb_goal_reset", "rb_reset_hour", "rb_tg_button", "rb_tg_on", "rb_tg_off",
            "rb_safety_title", "rb_panic", "rb_delta", "rb_percent_error", "rb_auto", "rb_auto_sub", "rb_angus",
            "rb_angus_sub", "rb_packs", "rb_packs_hint", "rb_main_pack", "rb_edit_pack", "rb_backups", "rb_pcs",
            "rb_add_pack", "rb_remove_pack", "rb_pack_exists", "rb_condition", "rb_saved_state", "rb_unsaved_state",
            "rb_bot_hint", "rb_save", "rb_saved_toast", "rb_fix_fields", "rb_broken_toast", "rb_leave_title",
            "rb_leave_text", "rb_leave_save", "rb_leave_discard", "rb_restore_title", "rb_restore_text",
            "rb_restore_ok"]
TEAMS = {"earth": ["angus", "avalon", "eden", "silva", "verdok"], "water": ["sigurd", "nova", "mairi", "hyperion", "tidus"],
         "fire": ["moloch", "vulcan", "ignis", "araji", "acheron"], "mix": ["sigurd", "araji", "rigel", "amon", "lumira"]}


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import data_paths
    data_paths._CHECKED.clear()
    (tmp_path / "bot_data" / "rules").mkdir(parents=True)
    for room, team in TEAMS.items():
        write_yaml(tmp_path / "bot_data" / "rules" / f"{room}.yml",
                   {"default_team": team, "rules": [{"name": f"Правило {room}", "condition": {"enemies_contain": ["eden"]},
                                                     "team": team, "source": "auto"}]})
    return tmp_path


def write_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


def read_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


PROFILE = {"settings": {"target_titanite": 0, "target_rooms": 40, "target_floors": 3, "target_time": 0,
                        "reset_hour": 4, "auto_rollback": False, "door_order": ["fire", "water", "earth", "mix"],
                        "telegram": {"active": True, "token": "123:abc", "chat_id": "42"},
                        "backup_teams": {"water": [["sigurd", "nova", "mairi", "hyperion", "orm"]]}},
           "global_thresholds": {"critical_hp": 30, "max_hp_delta": 60, "group_loss_titans": 2}}


# ── Без окна ─────────────────────────────────────────────────────────────────
def test_new_texts_in_all_languages():
    import unicodedata

    import i18n
    for lang, words in i18n.TRANSLATIONS.items():
        for key in NEW_KEYS:
            text = words.get(key)
            assert text and (lang == "RU" or text != i18n.TRANSLATIONS["RU"][key]), (lang, key)
            assert not any(unicodedata.category(ch) == "So" for ch in text), (lang, key, text)
        assert "{n}" in words["rb_pcs"] and "{tab}" in words["rb_leave_text"], lang


def test_form_like_bot_reads_it(workdir):
    from ui import rules_store
    empty = rules_store.form_from_profile({})
    assert empty["goal"] == ("titanite", 120)          # без ключа бот берёт 120 (config.LIMITS)
    assert (empty["critical_hp"], empty["max_hp_delta"], empty["reset_hour"]) == (40, 30, 5)
    assert not empty["auto_rollback"] and not empty["angus_manual_control"] and empty["backup_teams"] == {}
    form = rules_store.form_from_profile(PROFILE)
    assert form["goal"] == ("rooms", 40)                # первая ненулевая цель (как на главной)
    assert (form["critical_hp"], form["max_hp_delta"], form["reset_hour"]) == (30, 60, 4)
    assert form["telegram"] == {"active": True, "token": "123:abc", "chat_id": "42"}
    assert form["backup_teams"] == {"water": [["sigurd", "nova", "mairi", "hyperion", "orm"]]}
    assert rules_store.telegram_on(form["telegram"])
    assert not rules_store.telegram_on({"active": True, "token": "YOUR_TOKEN", "chat_id": "1"})
    assert not rules_store.telegram_on({"active": False, "token": "1:a", "chat_id": "1"})


def test_parse_number():
    from ui.rules_store import parse_number
    assert parse_number("30", 100) == (30, None)
    assert parse_number(" 0 ", 100) == (0, None)
    assert parse_number("", 100) == (None, "empty")
    assert parse_number("101", 100) == (None, "range")
    assert parse_number("3a", 100) == (None, "range")
    assert parse_number("-5", 100) == (None, "range")


def test_save_writes_only_changes_and_keeps_the_rest(workdir):
    import tactics
    from ui import launch_config, rules_store
    write_yaml(workdir / "profile.yml", PROFILE)
    state, profile, _ = rules_store.read_profile()
    saved = rules_store.form_from_profile(profile)
    form = rules_store.form_from_profile(profile)
    form["auto_rollback"] = True
    form["critical_hp"] = 35
    # Пока окно открыто, другое окно («Тактика», «Telegram») поменяло профиль — эти правки не теряются
    other = read_yaml(workdir / "profile.yml")
    other["settings"]["telegram"]["chat_id"] = "777"
    other["global_thresholds"]["group_loss_percent"] = 50
    write_yaml(workdir / "profile.yml", other)
    assert rules_store.save_profile(saved, form)[0] == rules_store.OK
    result = read_yaml(workdir / "profile.yml")
    assert result["settings"]["auto_rollback"] is True and result["global_thresholds"]["critical_hp"] == 35
    assert result["settings"]["telegram"]["chat_id"] == "777"            # не наше — не трогаем
    assert result["global_thresholds"]["group_loss_percent"] == 50
    assert result["settings"]["door_order"] == ["fire", "water", "earth", "mix"]
    # Цель одна: лишняя цель по этажам (3) обнулилась, выбранная — комнаты 40
    assert [result["settings"][k] for k in ("target_titanite", "target_rooms", "target_floors", "target_time")] == \
        [0, 40, 0, 0]
    # Бот читает то же, что показало окно
    settings = tactics.Settings(tactics.profile_getter(result))
    assert settings.auto_rollback and settings.critical_hp == 35 and settings.max_hp_delta == 60
    assert launch_config.launch_config(result)["goal"] == ("rooms", 40)
    import data_paths
    assert read_yaml(data_paths.profile_backup_file()) == result      # копия для «Восстановить / Сброс»


def test_nothing_changed_writes_nothing(workdir):
    from ui import rules_store
    write_yaml(workdir / "profile.yml", PROFILE)
    form = rules_store.form_from_profile(rules_store.read_profile()[1])
    before = (workdir / "profile.yml").stat().st_mtime_ns
    time.sleep(0.01)
    assert rules_store.save_profile(form, dict(form)) == (rules_store.OK, [])
    assert (workdir / "profile.yml").stat().st_mtime_ns == before
    assert not (workdir / "profile.yml.tmp").exists()


def test_goal_change_zeroes_other_goals(workdir):
    from ui import rules_store
    write_yaml(workdir / "profile.yml", PROFILE)
    saved = rules_store.form_from_profile(rules_store.read_profile()[1])
    form = dict(saved, goal=("titanite", 500))
    rules_store.save_profile(saved, form)
    s = read_yaml(workdir / "profile.yml")["settings"]
    assert (s["target_titanite"], s["target_rooms"], s["target_floors"], s["target_time"]) == (500, 0, 0, 0)
    form2 = dict(form, goal=("titanite", 0))             # «без лимита»: бот берёт 0, а не 120
    rules_store.save_profile(form, form2)
    from ui import launch_config
    assert launch_config.launch_config(read_yaml(workdir / "profile.yml"))["goal"] is None


def test_first_save_creates_profile(workdir):
    from ui import rules_store
    saved = rules_store.form_from_profile({})
    assert rules_store.read_profile()[0] == rules_store.MISSING
    state, keys = rules_store.save_profile(saved, dict(saved))
    assert state == rules_store.OK and set(keys) == set(rules_store.PROFILE_KEYS)
    profile = read_yaml(workdir / "profile.yml")
    assert profile["global_thresholds"] == {"critical_hp": 40, "max_hp_delta": 30, "group_loss_titans": 3,
                                            "group_loss_percent": 40, "titan_critical_hp": {}}  # и вкладка 5б
    assert profile["settings"]["target_titanite"] == 120 and profile["settings"]["auto_rollback"] is False


def test_broken_profile_is_not_touched(workdir):
    from ui import rules_store
    (workdir / "profile.yml").write_text("settings: [oops\n", encoding="utf-8")
    state, _profile, where = rules_store.read_profile()
    assert state == rules_store.BROKEN and where
    form = rules_store.form_from_profile({})
    assert rules_store.save_profile(form, dict(form, auto_rollback=True))[0] == rules_store.BROKEN
    assert (workdir / "profile.yml").read_text(encoding="utf-8") == "settings: [oops\n"


def test_default_team_keeps_rules(workdir):
    from ui import rules_store
    teams, broken = rules_store.read_default_teams()
    assert teams == TEAMS and broken == []
    assert rules_store.save_default_team("fire", ["moloch", "vulcan", "alecto"])
    data = read_yaml(workdir / "bot_data" / "rules" / "fire.yml")
    assert data["default_team"] == ["moloch", "vulcan", "alecto"]
    assert data["rules"][0]["source"] == "auto"          # правила и их скрытые поля на месте
    (workdir / "bot_data" / "rules" / "mix.yml").write_text("rules: [broken\n", encoding="utf-8")
    assert rules_store.read_default_teams()[1] == ["mix"]
    assert not rules_store.save_default_team("mix", ["rigel", "amon", "lumira"])
    assert (workdir / "bot_data" / "rules" / "mix.yml").read_text(encoding="utf-8") == "rules: [broken\n"


def test_backup_teams_add_remove(workdir):
    from ui import rules_store
    form = rules_store.form_from_profile({})
    assert rules_store.add_backup(form, "fire", ["moloch", "vulcan", "ignis"])
    assert not rules_store.add_backup(form, "fire", ["ignis", "moloch", "vulcan"])   # тот же пак
    for i in range(4):
        assert rules_store.add_backup(form, "fire", ["moloch", "vulcan", ["araji", "acheron", "alecto", "keros"][i]])
    assert not rules_store.add_backup(form, "fire", ["araji", "acheron", "alecto"])   # уже 5
    assert len(form["backup_teams"]["fire"]) == rules_store.MAX_BACKUPS
    for _ in range(5):
        rules_store.remove_backup(form, "fire", 0)
    assert form["backup_teams"] == {}
    rules_store.add_backup(form, "water", ["sigurd", "nova", "mairi"])
    profile = rules_store.apply_form({}, form, ["backup_teams"])
    import tactics
    assert tactics.Settings(tactics.profile_getter(profile)).backup_teams == {"water": [["sigurd", "nova", "mairi"]]}


def test_restore_profile(workdir):
    import data_paths
    from ui import rules_store
    write_yaml(workdir / "profile.yml", PROFILE)
    rules_store.ensure_backup()
    (workdir / "profile.yml").write_text("broken: [\n", encoding="utf-8")
    rules_store.ensure_backup()                           # копия есть — не перезаписываем битым
    assert rules_store.restore_profile() == "restored"
    assert read_yaml(workdir / "profile.yml") == PROFILE
    os.remove(data_paths.profile_backup_file())
    assert rules_store.restore_profile() == "reset" and not (workdir / "profile.yml").exists()
    assert rules_store.restore_profile() == "nothing"


# ── Окно на виртуальном экране ───────────────────────────────────────────────
def _gui_available():
    try:
        import tkinter  # noqa: F401
        import customtkinter  # noqa: F401
    except ImportError:
        return False
    return sys.platform == "win32" or bool(os.environ.get("DISPLAY"))


needs_gui = pytest.mark.skipif(not _gui_available(), reason="нет tkinter/customtkinter или экрана")


class Quiet:
    def start(self):
        return self

    def stop(self):
        pass


@pytest.fixture
def app(workdir):
    import test_ui_app  # noqa: F401  (заглушки pygetwindow/pyautogui для старых вкладок)
    from ui import app as app_mod
    from ui import icons, widgets
    (workdir / "docs").symlink_to(ROOT / "docs")
    write_yaml(workdir / "profile.yml", PROFILE)
    icons.clear_cache()
    widgets._titan_picture.cache_clear()
    window = app_mod.App(settings_path=str(workdir / "ui_settings.json"), status_watcher=Quiet(),
                         hotkey_watcher=Quiet())
    window.update()
    yield window
    if not window._closing:
        window.shutdown()


def pump(window, seconds=0.3, until=None):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        window.update()
        if until and until():
            return True
        time.sleep(0.02)
    return bool(until and until())


def open_dialog(window):
    from ui.widgets import ConfirmDialog
    return next((w for w in window.winfo_children() if isinstance(w, ConfirmDialog) and not w.done), None)


def footer(page):
    return page.state_label.cget("text").strip()


@needs_gui
def test_page_like_mockup(app):
    from ui.rules_page import RulesPage
    app.select_frame("rules")
    pump(app)
    page = app.frames["rules"]
    assert isinstance(page, RulesPage) and page.winfo_viewable()
    assert page.tabs.cget("values") == ["База и комнаты", "Авто-тактика и ХП", "Правила и перехваты"]
    assert page.base.goal_kind.get() == "rooms" and page.base.goal_value.get() == "40"
    assert page.base.fields["critical_hp"].get() == "30" and page.base.fields["max_hp_delta"].get() == "60"
    assert page.base.reset_hour.get() == 4 and page.base.reset_hour._label.cget("text") == "04:00"
    assert not page.base.auto.switch.is_on() and not page.base.angus.switch.is_on()
    assert "SOS-уведомления включены" in page.base.tg_state.cget("text")
    assert list(page.base.rooms) == ["earth", "water", "fire", "mix"]
    assert footer(page) == "Все изменения сохранены"
    # Вкладки и футер — во всю ширину (без отступов окна)
    assert page.grid_info()["padx"] in (0, "0")
    page.expanded["water"] = True
    page.rebuild_room("water")
    pump(app)
    assert len(page.base.rooms["water"].backups.rows) == 1


@needs_gui
def test_edit_and_save(app, workdir):
    app.select_frame("rules")
    page = app.frames["rules"]
    pump(app)
    page.base.auto.switch.toggle()                       # как щелчок мышью по тумблеру
    assert page.form["auto_rollback"] is True and footer(page) == "Есть несохранённые изменения"
    page.base.goal_kind._chosen("Титанит")
    page.base.goal_value.delete(0, "end")
    page.base.goal_value.insert(0, "7a5")
    page.base._goal_typed()
    assert page.base.goal_value.get() == "75" and page.form["goal"] == ("titanite", 75)
    page.set_team("fire", ["moloch", "vulcan", "alecto"])
    page.add_backup("earth", ["angus", "avalon", "eden"])
    page.base.reset_hour._chosen("06:00")
    assert read_yaml(workdir / "profile.yml") == PROFILE  # до «Сохранить» ничего не пишется
    page.save_button.invoke()
    profile = read_yaml(workdir / "profile.yml")
    assert profile["settings"]["auto_rollback"] is True and profile["settings"]["reset_hour"] == 6
    assert profile["settings"]["target_titanite"] == 75 and profile["settings"]["target_rooms"] == 0
    assert profile["settings"]["backup_teams"]["earth"] == [["angus", "avalon", "eden"]]
    assert read_yaml(workdir / "bot_data" / "rules" / "fire.yml")["default_team"] == ["moloch", "vulcan", "alecto"]
    assert footer(page) == "Все изменения сохранены"
    assert "[GUI] Профиль настроек сохранен!" in app.frames["dash"].log_text()
    # Главная видит новый профиль (цель — титанит 75)
    pump(app, 1.5, until=lambda: app.frames["dash"].config["goal"] == ("titanite", 75))
    assert app.frames["dash"].config["goal"] == ("titanite", 75)


@needs_gui
def test_field_error_blocks_save(app, workdir):
    app.select_frame("rules")
    page = app.frames["rules"]
    field = page.base.fields["critical_hp"]
    field.set("150")
    page.base._percent_typed("critical_hp")
    assert field.error == "Введи число от 0 до 100" and page.dirty()
    page.save_button.invoke()
    assert read_yaml(workdir / "profile.yml") == PROFILE
    field.set("25")
    page.base._percent_typed("critical_hp")
    assert field.error is None
    page.save()
    assert read_yaml(workdir / "profile.yml")["global_thresholds"]["critical_hp"] == 25


@needs_gui
def test_leave_page_asks_to_save(app, workdir):
    app.select_frame("rules")
    page = app.frames["rules"]
    pump(app)
    app.nav["dash"].invoke()                             # нет изменений — уходим сразу
    assert app.page == "dash"
    app.select_frame("rules")
    page.base.angus.switch.toggle()
    app.nav["dash"].invoke()
    pump(app, 1, until=lambda: open_dialog(app) is not None)
    dialog = open_dialog(app)
    assert dialog is not None and app.page == "rules"
    dialog._finish("cancel")                             # «Отмена» — остаёмся, изменения на месте
    assert app.page == "rules" and page.form["angus_manual_control"] is True
    app.nav["stats"].invoke()
    pump(app, 1, until=lambda: open_dialog(app) is not None)
    open_dialog(app)._finish("discard")                  # «Не сохранять» — уходим, форма как в файле
    assert app.page == "stats" and page.form["angus_manual_control"] is False and not page.dirty()
    assert "angus_manual_control" not in read_yaml(workdir / "profile.yml")["settings"]
    app.select_frame("rules")
    page.base.angus.switch.toggle()
    app.nav["dash"].invoke()
    pump(app, 1, until=lambda: open_dialog(app) is not None)
    open_dialog(app)._finish("confirm")                  # «Сохранить» — сохраняем и уходим
    assert app.page == "dash"
    assert read_yaml(workdir / "profile.yml")["settings"]["angus_manual_control"] is True


@needs_gui
def test_close_window_asks_to_save(app):
    app.select_frame("rules")
    page = app.frames["rules"]
    page.base.auto.switch.toggle()
    app.on_close()
    pump(app, 1, until=lambda: open_dialog(app) is not None)
    dialog = open_dialog(app)
    assert dialog is not None and not app._closing
    dialog._finish("cancel")
    assert not app._closing
    app.on_close()
    pump(app, 1, until=lambda: open_dialog(app) is not None)
    open_dialog(app)._finish("discard")
    assert app._closing                                  # бот не запущен — окно закрылось


@needs_gui
def test_telegram_dialog_changes_form_only(app, workdir, monkeypatch):
    import ui.telegram_window
    calls = []
    monkeypatch.setattr(ui.telegram_window, "TelegramWindow",
                        lambda master, lang, data, callback: calls.append((data, callback)))
    app.tg_button.invoke()                               # точка Telegram в полоске — окно настроек (шаг 5б — новое)
    assert app.page == "rules" and calls[0][0]["chat_id"] == "42"
    calls[0][1]({"active": False, "token": "123:abc", "chat_id": "42"})
    page = app.frames["rules"]
    assert "Telegram не настроен" in page.base.tg_state.cget("text") and page.dirty()
    assert read_yaml(workdir / "profile.yml")["settings"]["telegram"]["active"] is True
    page.save()
    assert read_yaml(workdir / "profile.yml")["settings"]["telegram"]["active"] is False


@needs_gui
def test_language_keeps_unsaved_values(app):
    from i18n import get_text
    app.select_frame("rules")
    page = app.frames["rules"]
    page.base.auto.switch.toggle()
    page.base.fields["max_hp_delta"].set("abc")
    page.base._percent_typed("max_hp_delta")
    app._language_chosen("Deutsch")
    pump(app)
    assert page.tabs.cget("values")[0] == get_text("DE", "rb_tab_base")
    assert page.base.auto.switch.is_on() and footer(page) == get_text("DE", "rb_unsaved_state")
    assert page.base.fields["max_hp_delta"].get() == "abc" and page.base.fields["max_hp_delta"].error
    assert page.save_button.cget("text") == get_text("DE", "rb_save")


@needs_gui
def test_bot_hint_while_farming(app):
    import subprocess
    app.select_frame("rules")
    page = app.frames["rules"]
    pump(app, 0.3)
    assert page.bot_label.cget("text") == ""
    dash = app.frames["dash"]
    dash.link.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        pump(app, 1, until=lambda: page.bot_label.cget("text") != "")
        assert page.bot_label.cget("text") == "Бот возьмёт новые настройки при следующем запуске"
    finally:
        dash.link.process.kill()
        dash.link.process.wait()


@needs_gui
def test_restore_asks_and_reloads(app, workdir):
    app.select_frame("rules")
    page = app.frames["rules"]
    page.base.auto.switch.toggle()
    page.save()
    write_yaml(workdir / "profile.yml", PROFILE)          # профиль поменяли снаружи
    page.restore_button.invoke()
    pump(app, 1, until=lambda: open_dialog(app) is not None)
    open_dialog(app)._finish("confirm")
    assert read_yaml(workdir / "profile.yml")["settings"]["auto_rollback"] is True   # из копии
    assert page.base.auto.switch.is_on() and not page.dirty()


@needs_gui
def test_hover_changes_only_colors(app):
    app.select_frame("rules")
    page = app.frames["rules"]
    pump(app)
    for widget, parts in ((page.base.goal_kind, ("_label", "_icon_label", "_arrow")),
                          (page.base.rooms["water"].backups.toggle, ())):
        calls = []
        original = widget.configure

        def spy(_orig=original, **kwargs):
            calls.append(kwargs)
            return _orig(**kwargs)
        widget.configure = spy
        parts_calls = []
        for name in parts:
            getattr(widget, name).configure = lambda **kw: parts_calls.append(kw)
        widget._frame_enter()
        widget._frame_enter()
        assert calls == [{"fg_color": calls[0]["fg_color"]}]    # один раз и только цвет фона
        widget._hovering = False
        widget._paint()
        assert len(calls) == 2 and set(calls[1]) == {"fg_color"}
        # Части — обычные надписи Tk (шаг 5б): им — только цвет фона; надпись, шрифт и картинка не меняются
        assert all(set(kw) in ({"bg_color"}, {"bg"}) for kw in parts_calls)


@needs_gui
def test_expand_and_edits_do_not_rebuild_the_row(app):
    """Проверка шага 5а: при прокрутке и раскрытии списков элементы дорисовывались с задержкой. Теперь раскрытие
    только показывает готовый список, а правка пака перестраивает только свою часть строки."""
    app.select_frame("rules")
    page = app.frames["rules"]
    room = page.base.rooms["water"]
    box = room.backups
    pump(app, 1, until=lambda: all(r.backups._filled for r in page.base.rooms.values()))
    assert all(r.backups._filled for r in page.base.rooms.values())   # списки построены заранее
    rows = list(box.rows)
    box.toggle._frame_click()
    pump(app)
    assert box.list.winfo_ismapped() and box.rows == rows and box.toggle.expanded
    assert box.toggle.pill.cget("text") == "1 шт."
    box.toggle._frame_click()
    pump(app)
    assert not box.list.winfo_ismapped() and box.rows == rows and not page.expanded["water"]
    page.set_team("water", ["sigurd", "nova", "mairi"])
    assert page.base.rooms["water"] is room and room.backups is box               # строка та же
    assert [t.titan for t in room.pack_frame.winfo_children() if hasattr(t, "titan")] == ["sigurd", "nova", "mairi"]
    page.add_backup("water", ["sigurd", "tidus", "orm"])
    pump(app)
    assert room.backups is box and box.expanded and len(box.rows) == 2 and box.toggle.pill.cget("text") == "2 шт."
    page.remove_backup("water", 0)
    pump(app)
    assert len(box.rows) == 1 and box.toggle.pill.cget("text") == "1 шт."
    assert page.form["backup_teams"]["water"] == [["sigurd", "tidus", "orm"]]


@needs_gui
def test_titan_tile_is_one_light_widget(app, monkeypatch):
    import tkinter as tk

    from ui import theme, widgets
    tile = widgets.TitanTile(app, "araji", lang="RU")
    assert isinstance(tile, tk.Label) and not tile.winfo_children()             # без холстов CustomTkinter
    assert tile.cget("image") and tile.tooltip is not None
    monkeypatch.setattr(theme, "titan_icon_source", lambda titan: None)
    blank = widgets.TitanTile(app, "araji", lang="RU", bg=theme.COLORS["bg_primary"])
    assert blank.cget("text") == "Ар" and blank.cget("bg") == theme.COLORS["bg_primary"]
    tile.destroy()
    blank.destroy()
