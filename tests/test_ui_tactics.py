"""Задача 15, шаг 5б: «Мастер правил → Авто-тактика и ХП» (ui/rules_tactics.py) и окно Telegram (ui/telegram_window.py).

Без окна (ui/rules_store.py):
- значения вкладки — по правилам бота (tactics.read_tactics: те же ключи, что у окна «⚙️ Тактика»);
- «Сохранить настройки» пишет только поменянное, бот читает сохранённое так же (tactics.Settings);
- порядок дверей меняется местами, «Кого убирать» — без повторов и не больше 3, личные пороги;
- новые надписи — на 13 языках, пробное сообщение Telegram — тоже.
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_tactics.py):
- вкладка как в макете 03b, плашка предупреждает, когда «Бот решает сам» выключен;
- правки → «Есть несохранённые изменения» → «Сохранить настройки» → profile.yml; поле с ошибкой не даёт сохранить;
- окно личного порога: добавить, изменить, убрать; «Сохранить изменения?» называет вкладку с правками;
- окно Telegram: «Проверить Telegram» в фоне (окно не ждёт), ответ под кнопкой, «Применить» меняет только форму;
- наведение меняет только цвета; процесс окна выходит сам после крестика, даже пока идёт проверка Telegram.
"""
import os
import subprocess
import sys
import textwrap
import threading
import time


from test_ui_rules import PROFILE, ROOT, app, footer, needs_gui, open_dialog, pump, read_yaml, workdir, write_yaml  # noqa: F401

NEW_KEYS = ["rt_banner", "rt_banner_off", "rt_doors_title", "rt_doors_hint", "rt_criteria_title", "rt_tries",
            "rt_sos_timeout", "rt_sos_timeout_sub", "rt_group_label", "rt_group_titans", "rt_group_percent",
            "rt_group_unit", "rt_group_sub", "rt_heal_title", "rt_heal_hp", "rt_heal_hp_sub", "rt_remove_title",
            "rt_remove_sub", "rt_personal_title", "rt_personal_rest", "rt_personal_add", "rt_personal_none",
            "rt_personal_remove", "rt_personal_edit", "rt_range_error", "rt_pt_title", "rt_pt_sub", "rt_pt_titan",
            "rt_pt_value", "rt_pt_hint", "tw_title", "tw_sub", "tw_enable", "tw_enable_sub", "tw_token", "tw_chat",
            "tw_show", "tw_paste", "tw_check", "tw_checking", "tw_check_ok", "tw_check_fail", "tw_check_empty",
            "tw_note"]
PLACEHOLDERS = {"rt_remove_sub": "{auto}", "rt_personal_rest": "{n}", "rt_pt_hint": "{n}", "rt_range_error": "{lo}", "tw_check_fail": "{error}"}

TACTICS_PROFILE = {
    "settings": {**PROFILE["settings"], "auto_rollback": True, "auto_rollback_tries": 3, "sos_timeout_minutes": 5,
                 "heal_below_hp": 55, "heal_remove_order": ["amon", "lumira"]},
    "global_thresholds": {**PROFILE["global_thresholds"], "group_loss_percent": 45,
                          "titan_critical_hp": {"sigurd": 20, "rigel": 25}},
}


# ── Без окна ─────────────────────────────────────────────────────────────────
def test_new_texts_in_all_languages():
    import unicodedata

    import i18n
    for lang, words in i18n.TRANSLATIONS.items():
        for key in NEW_KEYS:
            text = words.get(key)
            assert text and (lang == "RU" or text != i18n.TRANSLATIONS["RU"][key]), (lang, key)
            assert not any(unicodedata.category(ch) == "So" for ch in text), (lang, key, text)
        for key, mark in PLACEHOLDERS.items():
            assert mark in words[key], (lang, key)
        assert "{hi}" in words["rt_range_error"], lang


def test_check_message_in_all_languages():
    import telegram_i18n
    import telegram_report
    for lang in telegram_i18n.TG_TEXTS:
        text = telegram_report.check_message(lang)
        assert text.startswith("✅ <b>") and telegram_i18n.tg_text(lang, "check_text") in text, lang


def test_form_like_bot_reads_it(workdir):
    import tactics
    from ui import rules_store
    write_yaml(workdir / "profile.yml", TACTICS_PROFILE)
    _state, profile, _ = rules_store.read_profile()
    form = rules_store.form_from_profile(profile)
    assert form["auto_rollback_tries"] == 3 and form["sos_timeout_minutes"] == 5
    assert form["group_loss_titans"] == 2 and form["group_loss_percent"] == 45
    assert form["door_order"] == ["fire", "water", "earth", "mix"]
    assert form["heal_below_hp"] == 55 and form["heal_remove_order"] == ["amon", "lumira"]
    assert form["titan_critical_hp"] == {"sigurd": 20, "rigel": 25}
    empty = rules_store.form_from_profile({})            # нет ключей — то, что взял бы бот
    assert empty["auto_rollback_tries"] == tactics.DEFAULT_TRIES
    assert empty["sos_timeout_minutes"] == tactics.DEFAULT_SOS_TIMEOUT
    assert (empty["group_loss_titans"], empty["group_loss_percent"]) == (3, 40)
    assert empty["door_order"] == tactics.DEFAULT_DOOR_ORDER and empty["heal_below_hp"] == tactics.DEFAULT_HEAL_HP
    assert empty["heal_remove_order"] == [] and empty["titan_critical_hp"] == {}


def test_save_writes_only_changed_tactics(workdir):
    import copy

    import tactics
    from ui import rules_store
    write_yaml(workdir / "profile.yml", TACTICS_PROFILE)
    _state, profile, _ = rules_store.read_profile()
    saved = rules_store.form_from_profile(profile)
    form = copy.deepcopy(saved)
    form["door_order"] = rules_store.choose_door(form["door_order"], 0, "mix")
    rules_store.set_personal(form, "araji", 35)
    rules_store.set_personal(form, "sigurd", None)
    form["group_loss_titans"] = 0
    state, keys = rules_store.save_profile(saved, form)
    assert state == rules_store.OK
    assert set(keys) == {"door_order", "titan_critical_hp", "group_loss_titans", "goal"}
    data = read_yaml(workdir / "profile.yml")
    assert data["settings"]["door_order"] == ["mix", "water", "earth", "fire"]
    assert data["global_thresholds"]["titan_critical_hp"] == {"rigel": 25, "araji": 35}
    assert data["global_thresholds"]["group_loss_titans"] == 0
    assert data["settings"]["heal_remove_order"] == ["amon", "lumira"]    # не трогали — как было
    settings = tactics.Settings(tactics.profile_getter(data))             # бот читает то же, что показывает окно
    assert settings.door_order == ["mix", "water", "earth", "fire"] and settings.group_loss == (0, 45)
    assert settings.panic_hp("araji") == 35 and settings.panic_hp("sigurd") == 30
    assert rules_store.save_profile(rules_store.form_from_profile(data), rules_store.form_from_profile(data)) == \
        (rules_store.OK, [])                                               # нечего сохранять — файл не пишется


def test_door_and_remove_order():
    from ui import rules_store
    order = ["water", "mix", "earth", "fire"]
    assert rules_store.choose_door(order, 0, "fire") == ["fire", "mix", "earth", "water"]   # меняются местами
    assert rules_store.choose_door(order, 1, "mix") == order
    assert rules_store.choose_door(order, 2, "dark") == order                              # неизвестная — нет
    assert rules_store.choose_remove([], 2, "amon") == ["amon"]                 # место дальше занятых — в конец
    assert rules_store.choose_remove(["amon"], 0, "lumira") == ["lumira"]
    assert rules_store.choose_remove(["amon", "lumira"], 1, "amon") == ["lumira", "amon"]   # повтор — местами
    assert rules_store.choose_remove(["amon", "lumira", "rigel"], 0, None) == ["lumira", "rigel"]   # «— сам —»
    assert rules_store.choose_remove(["amon", "lumira", "rigel"], 2, "mor") == ["amon", "lumira", "mor"]
    assert rules_store.parse_number("0", 3, 1) == (None, "range")
    assert rules_store.parse_number(" 2 ", 3, 1) == (2, None)


# ── На виртуальном экране ────────────────────────────────────────────────────
def open_tactics(app, workdir, profile=TACTICS_PROFILE):
    write_yaml(workdir / "profile.yml", profile)
    page = app.frames["rules"]
    page.load()
    page.rebuild_base()
    app.select_frame("rules")
    page.tabs.set(page.text("rb_tab_tactics"))
    page._tab_chosen(page.text("rb_tab_tactics"))
    pump(app)
    return page, page.tactics


@needs_gui
def test_tab_like_mockup(app, workdir):
    page, tab = open_tactics(app, workdir)
    assert tab.winfo_viewable() and page.shown_tab_widget() is tab
    assert [d.get() for d in tab.doors] == ["fire", "water", "earth", "mix"]
    assert tab.doors[0]._label.cget("text") == "Огонь" and tab.doors[0]._badge.cget("text") == "1"
    assert {k: tab.entries[k].get() for k in tab.entries} == {
        "auto_rollback_tries": "3", "sos_timeout_minutes": "5", "group_loss_titans": "2", "group_loss_percent": "45",
        "heal_below_hp": "55"}
    assert [s.titan for s in tab.remove_slots] == ["amon", "lumira", None]
    assert tab.remove_slots[2].name_label.cget("text") == "— сам —"
    chips = [c for c in tab.chips.winfo_children() if hasattr(c, "titan")]
    assert [c.titan for c in chips] == ["sigurd", "rigel"] and chips[0].value_label.cget("text") == "20%"
    assert tab.personal_rest.cget("text") == "У остальных титанов — общий порог 30%"
    assert tab.banner_text.cget("text") == "Если бой прошёл плохо, бот откатывает его и переигрывает запасным паком. " \
        "Удачный пак сохраняется в правило — в следующий раз бот возьмёт его сразу."   # «Бот решает сам» включён
    assert not tab.notes["auto_rollback_tries"].winfo_ismapped()   # пустая подсказка — без пустой строки
    assert tab.notes["group_loss_titans"].cget("text") == "0 титанов — не проверять"
    assert tab.notes["group_loss_titans"].grid_info()["row"] == 0   # справа в строке «Считать бой плохим, если»
    assert footer(page) == "Все изменения сохранены"


@needs_gui
def test_tabs_are_prebuilt_and_switch_without_rebuild(app, workdir):
    """Проверка шага 5б: переключение вкладок и списки — без задержек. Вкладки строятся заранее и только поднимаются."""
    import time as clock
    app.select_frame("rules")
    page = app.frames["rules"]
    pump(app, 2, until=lambda: page.tactics is not None)
    tab, base = page.tactics, page.base
    assert tab is not None and page.shown_tab_widget() is base          # построена заранее, под открытой
    started = clock.perf_counter()
    for name in ("rb_tab_tactics", "rb_tab_rules", "rb_tab_base", "rb_tab_tactics"):
        page.tabs.set(page.text(name))
        page._tab_chosen(page.text(name))
        app.update()
    assert clock.perf_counter() - started < 1.0
    assert page.tactics is tab and page.base is base and page.shown_tab_widget() is tab   # ничего не перестроено


@needs_gui
def test_banner_warns_when_bot_does_not_decide(app, workdir):
    page, tab = open_tactics(app, workdir)
    page.tabs.set(page.text("rb_tab_base"))
    page._tab_chosen(page.text("rb_tab_base"))
    page.base.auto.switch.toggle()                        # выключили «Бот решает сам» на «Базе и комнатах»
    page.base.fields["critical_hp"].set("35")
    page.base._percent_typed("critical_hp")
    page._tab_chosen(page.text("rb_tab_tactics"))
    pump(app)
    text = tab.banner_text.cget("text")                   # продолжение того же белого текста, без значка
    assert page.tactics is tab and text.startswith("Если бой прошёл плохо") and "«Бот решает сам» выключен" in text
    assert tab.banner_text.cget("fg") == "#E8EAF0" and not tab.banner_text.cget("image")
    assert tab.personal_rest.cget("text").endswith("35%")


@needs_gui
def test_edit_and_save(app, workdir):
    page, tab = open_tactics(app, workdir)
    tab.doors[3]._chosen("Огонь")                         # огонь на 4-е место — смешанная на 1-е
    assert [d.get() for d in tab.doors] == ["mix", "water", "earth", "fire"]
    assert footer(page) == "Есть несохранённые изменения"
    tab.entries["sos_timeout_minutes"].set("0")
    tab._number_typed("sos_timeout_minutes")
    tab.remove_slots[2]._chosen("Ригель")
    tab.remove_slots[0]._chosen("— сам —")
    assert [s.titan for s in tab.remove_slots] == ["lumira", "rigel", None]
    tab.threshold_set("sigurd", None)
    page.save_button.invoke()
    assert footer(page) == "Все изменения сохранены"
    data = read_yaml(workdir / "profile.yml")
    assert data["settings"]["door_order"] == ["mix", "water", "earth", "fire"]
    assert data["settings"]["sos_timeout_minutes"] == 0
    assert data["settings"]["heal_remove_order"] == ["lumira", "rigel"]
    assert data["global_thresholds"]["titan_critical_hp"] == {"rigel": 25}
    assert data["settings"]["auto_rollback_tries"] == 3 and data["settings"]["telegram"]["chat_id"] == "42"


@needs_gui
def test_wrong_number_blocks_save(app, workdir):
    page, tab = open_tactics(app, workdir)
    for key, text, message in (("auto_rollback_tries", "0", "Число от 1 до 3"),
                               ("sos_timeout_minutes", "61", "Число от 0 до 60"),
                               ("group_loss_percent", "abc", "Число от 0 до 100")):
        tab.entries[key].set(text)
        tab._number_typed(key)
        pump(app, 0.1)
        note = tab.notes[key]
        assert tab.entries[key].error and message in note.cget("text") and note.winfo_ismapped(), key
    page.save()
    assert read_yaml(workdir / "profile.yml")["settings"]["auto_rollback_tries"] == 3   # не сохранилось
    assert page.dirty()
    app._language_chosen("English")                        # язык сменили — что было введено, видно снова
    pump(app)
    assert page.tactics.entries["auto_rollback_tries"].get() == "0" and page.tactics.entries["auto_rollback_tries"].error
    tab = page.tactics
    tab.entries["auto_rollback_tries"].set("2")
    tab._number_typed("auto_rollback_tries")
    pump(app)
    assert not tab.entries["auto_rollback_tries"].error and not tab.notes["auto_rollback_tries"].winfo_ismapped()


@needs_gui
def test_threshold_dialog(app, workdir):
    from ui.rules_tactics import ThresholdDialog
    page, tab = open_tactics(app, workdir)
    tab.add_threshold.invoke()
    pump(app, 1, until=lambda: tab._threshold.winfo_viewable())
    dialog = tab._threshold
    assert isinstance(dialog, ThresholdDialog) and dialog.titans.get() == "angus"    # первый без личного порога
    assert dialog.titans.enabled and dialog.field.get() == "30"                     # по умолчанию — общий порог
    dialog.titans._chosen("Араджи")
    dialog.field.set("120")
    dialog.apply()
    assert not dialog.done and "Число от 0 до 100" in dialog.field.note.cget("text")
    dialog.field.set("35")
    dialog.apply()
    assert dialog.done and page.form["titan_critical_hp"]["araji"] == 35
    chips = [c for c in tab.chips.winfo_children() if hasattr(c, "titan")]
    assert [c.titan for c in chips] == ["sigurd", "araji", "rigel"]                  # по стихиям, как в «Собери состав»
    chips[0]._frame_click()                                                         # щелчок по чипсу — изменить
    pump(app, 1, until=lambda: tab._threshold.winfo_viewable())
    dialog = tab._threshold
    assert dialog.titans.get() == "sigurd" and not dialog.titans.enabled and dialog.field.get() == "20"
    dialog.close()
    assert page.form["titan_critical_hp"]["sigurd"] == 20
    chips[0].remove_button.event_generate("<Button-1>")                                              # ✕ — убрать
    assert "sigurd" not in page.form["titan_critical_hp"]
    for titan in list(page.form["titan_critical_hp"]):
        tab.threshold_set(titan, None)
    assert "Личных порогов нет" in tab.chips.winfo_children()[0].cget("text")


@needs_gui
def test_leave_names_the_changed_tab(app, workdir):
    page, tab = open_tactics(app, workdir)
    tab.doors[0]._chosen("Вода")
    page.tabs.set(page.text("rb_tab_base"))
    page._tab_chosen(page.text("rb_tab_base"))
    app.nav["dash"].invoke()
    pump(app, 1, until=lambda: open_dialog(app) is not None)
    dialog = open_dialog(app)
    assert "«Авто-тактика и ХП»" in dialog.body.winfo_children()[2].cget("text")
    dialog._finish("discard")
    assert app.page == "dash" and page.form["door_order"][0] == "fire" and not page.dirty()


@needs_gui
def test_telegram_window(app, workdir):
    from ui.telegram_window import TelegramWindow
    page = app.frames["rules"]
    app.tg_button.invoke()
    pump(app, 1, until=lambda: page._tg_window is not None and page._tg_window.winfo_viewable())
    window = page._tg_window
    assert isinstance(window, TelegramWindow)
    assert window.active.is_on() and window.token.get() == "123:abc" and window.chat.get() == "42"
    assert window.token.entry.cget("show") == "•"
    window.eye.invoke()
    assert window.token.entry.cget("show") == ""
    release = threading.Event()
    calls = []

    def slow_sender(token, chat_id, lang):                # как Telegram, который отвечает не сразу
        calls.append((token, chat_id, lang, threading.current_thread() is threading.main_thread()))
        release.wait(5)
        return True, None
    window.sender = slow_sender
    window.chat.set("777")                                # проверяет то, что введено, ещё до сохранения
    started = time.monotonic()
    window.check_button.invoke()
    assert time.monotonic() - started < 0.5               # окно не ждёт ответа
    pump(app, 0.3)
    assert window.check_label.cget("text").strip() == "Отправляю пробное сообщение…"
    assert window.check_button.cget("state") == "disabled"
    release.set()
    pump(app, 2, until=lambda: "ушло" in window.check_label.cget("text"))
    assert calls == [("123:abc", "777", "RU", False)]    # запрос — в фоновом потоке
    assert "Сообщение ушло" in window.check_label.cget("text") and window.check_button.cget("state") == "normal"
    info = window.check_label.grid_info()                 # справа от кнопки, не выше её
    assert info["row"] == window.check_button.grid_info()["row"] and info["column"] == 1
    assert window.check_label.winfo_height() <= window.check_button.winfo_height() + 1
    assert window.note.grid_info()["row"] == window.apply_button.grid_info()["row"]   # «Записать в файл» — слева
    window.sender = lambda token, chat_id, lang: (False, "Telegram ответил ошибкой: Unauthorized")
    window.check_button.invoke()
    pump(app, 2, until=lambda: "Не ушло" in window.check_label.cget("text"))
    assert "Unauthorized" in window.check_label.cget("text")
    window.token.set("")
    window.check_button.invoke()
    assert "Заполните токен" in window.check_label.cget("text")
    window.token.set("555:new")
    window.active.toggle()
    window.apply_button.invoke()
    assert window.done
    assert page.form["telegram"] == {"active": False, "token": "555:new", "chat_id": "777"} and page.dirty()
    assert read_yaml(workdir / "profile.yml")["settings"]["telegram"]["chat_id"] == "42"   # файл — только «Сохранить»
    app.tg_button.invoke()
    pump(app, 1, until=lambda: page._tg_window is not window and page._tg_window.winfo_viewable())
    page._tg_window.close()                               # крестик — без изменений
    assert page.form["telegram"]["token"] == "555:new"


@needs_gui
def test_hover_changes_only_colors(app, workdir):
    page, tab = open_tactics(app, workdir)
    chip = next(c for c in tab.chips.winfo_children() if hasattr(c, "titan"))
    for widget in (tab.doors[0], tab.remove_slots[0], tab.remove_slots[2], chip):
        calls = []
        original = widget.configure

        def spy(_orig=original, **kwargs):
            calls.append(kwargs)
            return _orig(**kwargs)
        widget.configure = spy
        widget._frame_enter()
        widget._frame_enter()
        assert len(calls) == 1 and set(calls[0]) <= {"fg_color", "border_color"}, widget   # один раз и только цвета
        widget._hovering = False
        widget._paint()
        assert len(calls) == 2 and set(calls[1]) <= {"fg_color", "border_color"}, widget
        widget.configure = original


CLOSE_SCRIPT = textwrap.dedent('''
    import os, sys, threading, types
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
    hang = threading.Event()
    def step1():
        page = app.frames["rules"]
        app.select_frame("rules")
        page._tab_chosen(page.text("rb_tab_tactics"))
        page.tactics.open_threshold(None)
        app.after(400, step2)
    def step2():
        page = app.frames["rules"]
        page.tactics._threshold.close()
        page.open_tg_dialog()
        page._tg_window.sender = lambda token, chat_id, lang: (hang.wait(60), (True, None))[1]   # Telegram молчит
        app.after(400, step3)
    def step3():
        page = app.frames["rules"]
        page._tg_window.check()
        print("CHECKING", page._tg_window._poll_id is not None, flush=True)
        app.after(300, lambda: app.tk.call(app.protocol("WM_DELETE_WINDOW")))   # то же, что крестик окна
    app.after(500, step1)
    app.mainloop()
    print("EXITED", flush=True)
''')


@needs_gui
def test_process_exits_while_telegram_check_hangs(workdir):
    write_yaml(workdir / "profile.yml", PROFILE)
    script = f"ROOT = {str(ROOT)!r}\n" + CLOSE_SCRIPT
    result = subprocess.run([sys.executable, "-c", script], cwd=workdir, capture_output=True, text=True,
                            timeout=60, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = result.stdout + result.stderr
    assert "CHECKING True" in result.stdout and "EXITED" in result.stdout, out
    assert result.returncode == 0 and "Traceback" not in result.stderr, out
