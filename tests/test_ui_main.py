"""Задача 15, шаг 3: главная нового окна (ui/main_page.py), журнал с таблетками, «Собери состав».

Без окна (обычный python):
- таблетки журнала (сверка 1.2): тег → «Бои / Правила / Система / Ошибки», строка без тега — туда же, куда строка над
  ней, ошибка Python считается один раз; проверяется и на настоящем логе сессии 07 (tests/data/session_07_bot_log.txt);
- цифры сессии из строк бота: комнаты, титанит, этажи, дверь, откаты, SOS, среднее время комнаты, итог [ИТОГ];
- «Конфигурация запуска» по profile.yml — по тем же правилам, что у бота (цель одна; без цели по титаниту бот берёт 120);
- кого можно в комнату: стихия, смешанная — все и Метида;
- новые надписи на 13 языках, без эмодзи, с теми же подстановками.
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_main.py): состояния главной (первый запуск,
конфигурация, готов, фарм, итог), таблетки фильтруют и запоминаются, «Очистить» спрашивает, наведение на новые кнопки
меняет только цвета.
"""
import json
import os
import re
import sys
import time
import types
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import i18n  # noqa: E402
from ui import launch_config, log_lines, theme  # noqa: E402
from ui.log_lines import ERRORS, FIGHTS, RULES, SYSTEM  # noqa: E402

LOG_07 = ROOT / "tests" / "data" / "session_07_bot_log.txt"


# ── Таблетки журнала ────────────────────────────────────────────────────────
@pytest.mark.parametrize("line, category", [
    ("10:25:48.475 [КОМБАТ] Успешный вход. Комната: WATER", FIGHTS),
    ("10:26:08.713 [ВРЕМЯ] Комната 1 (water): всего 36.8 с", FIGHTS),
    ("11:23:24.981 [ИТОГ] Причина остановки: Ctrl+Q", FIGHTS),
    ("10:25:49.738 [ТАКТИКА] Комната water | Пак: [...]", RULES),
    ("10:25:52.742 [КОМАНДА] Состав уже стоит в слотах", RULES),
    ("10:30:00.000 [SOS_CLOSE] Причина", RULES),
    ("10:25:23.956 [НАВИГАЦИЯ] Сканирую коридор", SYSTEM),
    ("10:25:15.892 [УМНЫЙ СТАРТ] Сканирую экран", SYSTEM),
    ("10:25:15.892 [НОВЫЙ ТЕГ] что-то новое", SYSTEM),
    ("10:25:21.450 [ВНИМАНИЕ] Окно игры перекрыто", ERRORS),
    ("10:25:21.450 [ОШИБКА ФОКУСА] не удалось", ERRORS),
    ("10:25:21.450 [ФАТАЛЬНАЯ ОШИБКА КОМАНДЫ] стоп", ERRORS),
    ("10:25:21.450 [СТОРОЖ] Зависание", ERRORS),
    ("10:25:21.450 [SOS] Причина: ARAJI", ERRORS),
])
def test_tags_go_to_their_pill(line, category):
    assert log_lines.Classifier().classify(line)[0] == category


def test_untagged_lines_follow_the_line_above_and_python_error_counts_once():
    c = log_lines.Classifier()
    assert c.classify("10:26:02.209 [АНАЛИЗАТОР] Окно результата:")[0] == FIGHTS
    assert c.classify("10:26:02.717  ---> HYPERION: ХП 100%")[0] == FIGHTS   # строка без тега — к своему бою
    counted = [c.classify(line)[3] for line in (
        "10:30:00.000 Traceback (most recent call last):", '  File "main.py", line 1', "ValueError: плохо")]
    assert counted == [True, False, False]
    assert c.last == ERRORS
    category, color, (time_end, span), _ = c.classify("10:30:00.000 [GUI] Язык")
    assert category == SYSTEM and color == log_lines.GUI   # строки окна — в «Систему», тег серый
    assert time_end == len("10:30:00.000") and span == (13, 18)


def test_session_07_log_by_pills():
    """Сверка 1.2 на настоящем логе: бои — больше всего строк, ошибки — единицы на всю сессию."""
    c = log_lines.Classifier()
    counts = {FIGHTS: 0, RULES: 0, SYSTEM: 0, ERRORS: 0}
    errors = 0
    for line in LOG_07.read_text(encoding="utf-8").splitlines():
        if line.strip():
            category, _color, _parts, counted = c.classify(line)
            counts[category] += 1
            errors += counted
    assert counts[FIGHTS] > counts[SYSTEM] > counts[RULES] > counts[ERRORS] > 0
    assert errors == 11                                    # «Ошибки (11)» за сессию 07 (сверка 1.2)


def test_session_numbers_from_bot_lines():
    clock = [100.0]
    stats = log_lines.SessionStats(clock=lambda: clock[0])
    stats.start()
    for line in LOG_07.read_text(encoding="utf-8").splitlines():
        stats.feed(line)
    clock[0] += 3492
    stats.finish()
    assert (stats.rooms, stats.titanite) == (105, 1260)
    assert stats.rollbacks == 1 and stats.sos == 0         # точные числа из строки счётчиков [ИТОГ]
    assert stats.battles == 106
    assert len(stats.room_times) == 105 and round(stats.avg_room(), 1) == 31.3  # как «Среднее время комнаты» бота
    assert stats.stop_reason == "Ручная остановка пользователем (Ctrl+Q)" and stats.ended_by is None
    assert stats.summary[0].endswith("========== Итог сессии ==========") and len(stats.summary) == 14
    assert stats.door in ("water", "earth", "fire", "mix")
    assert log_lines.clock_text(stats.elapsed()) == "00:58:12"


def test_session_numbers_floors_door_and_killed_bot():
    stats = log_lines.SessionStats(clock=lambda: 0.0)
    stats.start()
    for line in ("[КОМБАТ] Успешный вход. Комната: FIRE | Враги: []", "[СТАТИСТИКА] Этажей: 3",
                 "[ОТКАТ] Запускаю протокол отката боя...", "[SOS] Причина: x"):
        stats.feed(line)
    assert (stats.door, stats.floors, stats.rollbacks, stats.sos) == ("fire", 3, 1, 1)
    stats.finish(log_lines.ENDED_KILLED)                   # «СТОП»: бот не написал [ИТОГ]
    assert stats.stop_reason is None and stats.ended_by == "main_reason_killed"
    assert log_lines.group_digits(7500) == "7 500"


# ── Конфигурация запуска ────────────────────────────────────────────────────
def test_launch_config_like_bot(tmp_path):
    cfg = launch_config.launch_config({})
    assert cfg["goal"] == ("titanite", 120)                # без profile.yml бот остановится на 120 титанита
    assert (cfg["auto"], cfg["panic"], cfg["reset_hour"], cfg["sos_timeout"]) == (False, 40, 5, 10)
    profile = {"global_thresholds": {"critical_hp": 30, "titan_critical_hp": {"rigel": 25}},
               "settings": {"auto_rollback": True, "reset_hour": 3, "target_titanite": 0, "target_rooms": 50,
                            "target_time": 60, "sos_timeout_minutes": 0}}
    cfg = launch_config.launch_config(profile)
    assert cfg["goal"] == ("rooms", 50)                    # цель одна: первая ненулевая (ваш ответ 22.10.2026)
    assert (cfg["auto"], cfg["panic"], cfg["reset_hour"], cfg["sos_timeout"]) == (True, 30, 3, 0)
    assert cfg["settings"].panic_hp("rigel") == 25 and cfg["settings"].panic_hp("araji") == 30
    zero = {"settings": {"target_titanite": 0, "target_rooms": 0, "target_floors": 0, "target_time": 0}}
    assert launch_config.launch_config(zero)["goal"] is None
    assert launch_config.goal_progress(("time", 60), 0, 0, 0, 1800) == (30.0, 60, 0.5)
    assert launch_config.goal_progress(("titanite", 100), 0, 150, 0, 0)[2] == 1.0
    (tmp_path / "profile.yml").write_text("settings: [сломано", encoding="utf-8")
    assert launch_config.read_profile(str(tmp_path / "profile.yml")) == (True, {})
    assert launch_config.read_profile(str(tmp_path / "нет.yml")) == (False, {})


def test_room_titans_and_elarite():
    assert theme.room_titans("earth") == theme.TITANS["earth"] and "pallant" in theme.room_titans("earth")
    assert "orm" in theme.room_titans("water") and "alecto" in theme.room_titans("fire")
    mix = theme.room_titans("mix")
    assert len(mix) == 29 and "metida" in mix and theme.room_titans(None) == mix
    assert "metida" not in theme.room_titans("fire")
    assert theme.element_of("metida") == "elarite" and theme.element_style("elarite")["icon"] == "gem"


# ── Надписи ─────────────────────────────────────────────────────────────────
def step3_keys():
    keys = set()
    for path in ("ui/main_page.py", "ui/sos_dialogs.py", "ui/titan_picker.py"):
        text = (ROOT / path).read_text(encoding="utf-8")
        keys |= set(re.findall(r'"((?:main|log|sosw|nopack|testw|pick)_[a-z0-9_]+)"', text))
    keys.discard("log_filter")                             # это настройка окна, а не надпись
    return keys | {"elem_elarite", "titan_metida"}


def test_step3_texts_in_all_languages():
    ru = i18n.TRANSLATIONS["RU"]
    keys = step3_keys()
    assert len(keys) > 100
    for lang, words in i18n.TRANSLATIONS.items():
        for key in keys:
            text = words.get(key)
            assert text, (lang, key)
            assert not any(unicodedata.category(ch) == "So" for ch in text), (lang, key, text)
            assert set(re.findall(r"\{(\w+)\}", text)) == set(re.findall(r"\{(\w+)\}", ru[key])), (lang, key)
    english = i18n.TRANSLATIONS["EN"]
    assert sum(english[k] != ru[k] for k in keys) == len(keys)  # английский — правда английский
    assert set(i18n.TRANSLATIONS) == set(i18n.LANGUAGES)


# ── Окно ────────────────────────────────────────────────────────────────────
def _gui_available():
    try:
        import tkinter  # noqa: F401
        import customtkinter  # noqa: F401
    except ImportError:
        return False
    return sys.platform == "win32" or bool(os.environ.get("DISPLAY"))


gui = pytest.mark.skipif(not _gui_available(), reason="нет tkinter/customtkinter или экрана")


class Quiet:
    def start(self):
        return self

    def stop(self):
        pass


def make_app(tmp_path):
    from ui import app as app_mod
    from ui import icons, widgets
    icons.clear_cache()
    widgets._titan_picture.cache_clear()
    app = app_mod.App(settings_path=str(tmp_path / "ui_settings.json"), status_watcher=Quiet(), hotkey_watcher=Quiet())
    app.update()
    return app


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ("pygetwindow", "pyautogui"):
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name) or types.ModuleType(name))
    sys.modules["pygetwindow"].getAllWindows = lambda: []
    sys.modules["pygetwindow"].getWindowsWithTitle = lambda title: []
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").symlink_to(ROOT / "docs")
    import data_paths
    data_paths._CHECKED.clear()
    window = make_app(tmp_path)
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


def shown_lines(dash):
    return [line for line in dash.log_box.get("1.0", "end").splitlines() if line.strip()]


@gui
def test_states_first_config_ready(app, tmp_path):
    dash = app.frames["dash"]
    assert dash.left_mode == "first" and dash.right_mode == "connect"
    assert [s._look for s in dash.steps] == ["now", "todo", "todo"]
    assert not dash.pause_button.enabled and not dash.stop_button.enabled  # бот не работает — бледные
    (tmp_path / "profile.yml").write_text(
        "global_thresholds:\n  critical_hp: 30\nsettings:\n  auto_rollback: true\n  reset_hour: 5\n"
        "  target_titanite: 7500\n", encoding="utf-8")
    assert pump(app, 3, until=lambda: dash.left_mode == "config")  # профиль сохранили — конфигурация
    tiles = dash.config_tiles
    assert tiles[0].value.cget("text") == "Титанит — 7 500"
    assert tiles[1].value.cget("text") == "Бот решает сам" and tiles[1].badge.cget("text") == "ВКЛ"
    assert tiles[2].value.cget("text") == "30%" and tiles[3].value.cget("text") == "05:00"
    app.events.put(("phone", True))
    assert pump(app, 2, until=lambda: dash.right_mode == "start")
    assert dash.note.cget("text") == "Окно игры встанет в размер 1606×748"


@gui
def test_first_run_steps_follow_phone_and_telegram(app):
    dash = app.frames["dash"]
    app.events.put(("phone", True))
    app.events.put(("telegram", True))
    assert pump(app, 2, until=lambda: dash.steps[2]._look == "done")
    assert [s._look for s in dash.steps] == ["done", "now", "done"]


@gui
def test_session_tiles_from_bot_lines_and_summary(app, tmp_path):
    from ui import bot_link
    dash = app.frames["dash"]
    (tmp_path / "profile.yml").write_text("settings:\n  target_titanite: 0\n  target_rooms: 4\n", encoding="utf-8")
    dash._reload_profile()
    dash.run_config = launch_config.launch_config(launch_config.read_profile()[1])
    dash.link.process = __import__("subprocess").Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                                       stdin=-1, stdout=-1, text=True)
    dash.stats.start()
    for line in ("10:00:00.000 [КОМБАТ] Успешный вход. Комната: WATER | Враги: []",
                 "10:00:10.000 [ВРЕМЯ] Комната 1 (water): коридор 1.0 с | всего 28.0 с",
                 "10:00:10.100 [СТАТИСТИКА] Комнат: 1 | Титанит: 6",
                 "10:00:11.000 [ОТКАТ] Запускаю протокол отката боя..."):
        app.events.put(("bot_line", line + "\n"))
    assert pump(app, 2, until=lambda: dash.session_tiles[0].value.cget("text") == "6")
    pump(app, 1.2)
    tiles = dash.session_tiles
    assert dash.left_mode == "session" and dash.right_mode == "running"
    assert tiles[1].extra.cget("text") == "· дверь: Вода"
    assert tiles[2].value.cget("text") == "1 побед из 2"
    assert tiles[2].right.cget("text") == "25% из 4" and tiles[2]._shown["bar"]   # цель — комнаты: полоска здесь
    assert tiles[3].right.cget("text") == "комната в среднем 28 с"
    assert dash.session_status.cget("text").strip() == "Фарм идёт"
    dash.stop_bot()
    app.events.put(("bot_exit", dash.link.run_id))         # процесс закончился (его читатель шлёт это сам)
    assert pump(app, 5, until=lambda: dash.left_mode == "summary")
    assert dash.summary_reason.cget("text") == "Причина остановки: остановлен кнопкой «СТОП»"
    assert not dash.summary_more.winfo_ismapped()          # [ИТОГ] бот не написал — «Подробно» нечего показать
    dash.hide_summary()
    assert dash.left_mode == "config"
    assert bot_link.SOS  # модуль связи на месте


@gui
def test_pills_filter_count_and_are_remembered(app, tmp_path):
    from ui import ui_settings
    dash = app.frames["dash"]
    for line in ("10:00:00.000 [ТАКТИКА] Пак: rigel", "10:00:01.000 [ОШИБКА] Кнопка не найдена",
                 "10:00:02.000 [НАВИГАЦИЯ] Коридор", "10:00:03.000 [КОМБАТ] Вход", "10:00:03.500  ---> RIGEL: ХП 50%",
                 "10:00:04.000 [СТОРОЖ] Зависание"):
        app.events.put(("bot_line", line + "\n"))
    assert pump(app, 2, until=lambda: len(shown_lines(dash)) == 6)
    assert dash.chips[ERRORS]._count.cget("text") == "2"
    dash.chips[FIGHTS]._on_click()
    pump(app, 0.2)
    assert shown_lines(dash) == ["10:00:03.000 [КОМБАТ] Вход", "10:00:03.500  ---> RIGEL: ХП 50%"]
    dash.chips[ERRORS]._on_click()
    pump(app, 0.2)
    assert len(shown_lines(dash)) == 2 and all("ОШИБКА" in x or "СТОРОЖ" in x for x in shown_lines(dash))
    app.events.put(("bot_line", "10:00:05.000 [ТАКТИКА] ещё правило\n"))  # строка другой таблетки не показывается
    pump(app, 0.3)
    assert len(shown_lines(dash)) == 2
    assert ui_settings.load(str(tmp_path / "ui_settings.json"))["log_filter"] == ERRORS
    app.shutdown()
    second = make_app(tmp_path)                            # следующий запуск — та же таблетка
    try:
        assert second.frames["dash"].filter == ERRORS and second.frames["dash"].chips[ERRORS].selected
    finally:
        second.shutdown()


@gui
def test_empty_pill_and_clear_asks(app):
    dash = app.frames["dash"]
    assert dash.empty.winfo_ismapped() and dash.empty_title.cget("text") == "Журнал пока пуст"
    dash.append_log("[GUI] строка окна\n")
    assert pump(app, 1, until=lambda: not dash.empty.winfo_ismapped())
    assert re.match(r"\d\d:\d\d:\d\d\.\d{3} \[GUI\] строка окна", shown_lines(dash)[0])  # время, как у бота
    dash.set_filter(RULES)
    pump(app, 0.2)
    assert dash.empty.winfo_ismapped() and dash.empty_title.cget("text") == "Здесь пока пусто"
    dash.set_filter("all")
    dash.ask_clear_log()
    pump(app, 0.3)
    dialog = dash._clear_dialog
    dialog._finish("cancel")
    assert dash.lines                                      # «Отмена» — строки на месте
    dash.ask_clear_log()
    pump(app, 0.3)
    dash._clear_dialog.body.confirm_button.invoke()
    pump(app, 0.2)
    assert not dash.lines and dash.empty.winfo_ismapped()


@gui
def test_main_page_language(app):
    from i18n import get_text
    app._language_chosen("Deutsch")
    pump(app, 0.2)
    dash = app.frames["dash"]
    assert dash.cta["connect"].cget("text") == get_text("DE", "main_btn_connect")
    assert dash.chips["fights"]._label.cget("text") == "Kämpfe"
    assert dash.stop_button._label.cget("text") == "STOPP"


@gui
def test_new_buttons_hover_changes_colors_only(app):
    """Правило ui/widgets.py: при наведении только цвета — шрифт, текст и картинка не трогаются."""
    from ui.titan_picker import TitanPicker
    dash = app.frames["dash"]
    picker = TitanPicker(app, "RU", on_apply=lambda team: None, room="fire")
    pump(app, 0.3)
    dash.pause_button.set_enabled(True)                    # неактивная кнопка на наведение не отвечает вовсе
    for widget, label in ((dash.pause_button, dash.pause_button._label), (picker.rows["araji"], picker.rows["araji"].name)):
        calls = []
        original = label.configure

        def spy(_original=original, **kwargs):
            calls.append(kwargs)
            return _original(**kwargs)
        label.configure = spy
        widget._frame_enter()
        widget._frame_enter()
        widget._hovering = False
        widget._paint()
        assert not any(set(c) & {"font", "text", "image"} for c in calls), calls
    picker.cancel()
