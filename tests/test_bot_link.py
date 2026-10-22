"""Задача 15, шаг 3: связь нового окна и бота — на поддельном боте (tests/fake_bot.py). Прогоняется на каждом следующем шаге.

Без окна (обычный python):
- каждая строка бота разбирается так же, как в старом окне (ui/dashboard.py): [SOS_TRIGGER] трёх видов, [SOS_CLOSE],
  [ПАУЗА ОТЛАДКИ]; строки [SOS_TRIGGER] в журнал не идут;
- бот запускается той же командой с HEROWARS_LANG, строки читаются до конца (итог сессии не теряется),
  ответ из устаревшего окна не отправляется, STOP — бот останавливается сам, не отозвался — окно останавливает его;
- SOS в Telegram — с повторами при обрыве связи (поддельный сервер Telegram).
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_bot_link.py): каждая строка бота открывает нужное
окно, каждая кнопка окна шлёт боту нужную команду — те же, что старое окно.
"""
import json
import os
import queue
import shutil
import sys
import threading
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FAKE_BOT = ROOT / "tests" / "fake_bot.py"

from ui import bot_link  # noqa: E402

SOS_LINE = '10:00:05.000 [SOS_TRIGGER] {"titans": {"araji": 18, "ignis": 71, "acheron": 95}, "is_manual": false}'
SOS_MANUAL = '[SOS_TRIGGER] {"titans": {"angus": 0, "eden": 40}, "is_manual": true}'
NO_TEAM_LINE = ('[SOS_TRIGGER] {"type": "NO_VALID_TEAM", "room": "earth", "enemies": ["angus", "silva"], '
                '"reason": "Все паки под запретом"}')
TEST_LINE = '[SOS_TRIGGER] TEST_SUCCESS:{"titans": {"vulcan": {"hp": 90, "energy": 10}}, "source": "gui"}'
SOS_INFO = {"type": "SOS", "room": "fire", "room_no": 47, "enemies": ["angus", "silva", "verdok"],
            "reason": "ARAJI: ХП 18% ниже порога 30%", "team": {}, "hp_before": {"araji": 62}}


# ── Разбор строк ────────────────────────────────────────────────────────────
def test_parse_lines_like_old_window():
    kind, data = bot_link.parse_line(SOS_LINE)
    assert kind == bot_link.SOS and data == {"titans": {"araji": 18, "ignis": 71, "acheron": 95}, "is_manual": False}
    assert bot_link.parse_line(SOS_MANUAL) == (bot_link.SOS, {"titans": {"angus": 0, "eden": 40}, "is_manual": True})
    kind, data = bot_link.parse_line(NO_TEAM_LINE)
    assert kind == bot_link.NO_TEAM and data["room"] == "earth" and data["enemies"] == ["angus", "silva"]
    assert bot_link.parse_line(TEST_LINE) == (bot_link.TEST_OK, {"titans": {"vulcan": {"hp": 90, "energy": 10}},
                                                                  "source": "gui"})
    # Старый вид TEST_SUCCESS (без source) и SOS без "titans" — как в старом окне
    assert bot_link.parse_line('[SOS_TRIGGER] TEST_SUCCESS:{"rigel": 50}') == \
        (bot_link.TEST_OK, {"titans": {"rigel": 50}, "source": "gui"})
    assert bot_link.parse_line('[SOS_TRIGGER] {"rigel": 20}') == \
        (bot_link.SOS, {"titans": {"rigel": 20}, "is_manual": False})
    assert bot_link.parse_line("[SOS_TRIGGER] {сломано") == \
        (bot_link.SOS, {"titans": {"Неизвестно": 0}, "is_manual": False})
    assert bot_link.parse_line("11:00:00.000 [SOS_CLOSE] Причина\n") == (bot_link.SOS_CLOSE, "Причина")
    assert bot_link.parse_line("11:00:00.000 [ПАУЗА ОТЛАДКИ] Бой завершен.") == (bot_link.DEBUG_PAUSE, None)
    assert bot_link.parse_line("11:00:00.000 [ТАКТИКА] Комната fire") is None


def test_bot_command_is_the_same_as_old_window():
    assert bot_link.bot_command() == [sys.executable, "-X", "utf8", "-u", "main.py"]


# ── Поддельный бот ──────────────────────────────────────────────────────────
def scenario(tmp_path, steps, **extra):
    path = tmp_path / "fake_bot.json"
    path.write_text(json.dumps({"steps": steps, "sos_info": SOS_INFO, **extra}, ensure_ascii=False), encoding="utf-8")
    return [sys.executable, "-u", str(FAKE_BOT), str(path)]


def collect(events, until, timeout=10):
    """События из очереди окна, пока until(список) не вернёт True."""
    got = []
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            got.append(events.get(timeout=0.05))
        except queue.Empty:
            pass
        if until(got):
            return got
    raise AssertionError(f"не дождались: {got}")


def lines_of(events):
    return [v for k, v in events if k == "bot_line"]


@pytest.fixture
def link(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    created = []

    def make(steps, calibrate=lambda: True, **extra):
        events = queue.Queue()
        item = bot_link.BotLink(events, command=scenario(tmp_path, steps, **extra), calibrate=calibrate)
        created.append(item)
        return item, events
    yield make
    for item in created:
        item.close()


def test_start_reads_all_lines_and_hides_sos_trigger(link):
    steps = [[f"10:00:01.{i:03d} [НАВИГАЦИЯ] строка {i}" for i in range(300)] + [SOS_LINE, "@exit"]]
    bot, events = link(steps)
    assert bot.start("DE") and bot.running()
    assert not bot.start("DE")                            # второй раз не запускается
    got = collect(events, lambda g: ("bot_exit", bot.run_id) in g)
    lines = lines_of(got)
    assert lines[0].strip() == "10:00:00.000 [ТЕСТ] Язык: DE"  # язык окна — боту в HEROWARS_LANG
    assert len(lines) == 301                              # все строки до конца, даже после выхода бота
    assert not any("[SOS_TRIGGER]" in line for line in lines)
    sos = [v for k, v in got if k == "bot_event"]
    assert sos[0][0] == bot_link.SOS and sos[0][1]["titans"]["araji"] == 18
    assert ("log", "[СИСТЕМА] Калибровка окна игры...\n") in got
    assert bot.exited(bot.run_id) and not bot.running()


def test_answers_go_to_stdin_and_stale_ones_do_not(link):
    bot, events = link([[SOS_LINE], ["[SOS_CLOSE] Решение: запасной пак"], []])
    bot.start("RU")
    collect(events, lambda g: any(k == "bot_event" for k, _ in g))
    epoch = bot.epoch
    assert bot.answer("ROLLBACK:araji,vulcan,moloch", epoch)
    got = collect(events, lambda g: any(k == "bot_event" and v[0] == bot_link.SOS_CLOSE for k, v in g))
    assert "10:00:01.000 [ТЕСТ] Получено: 'ROLLBACK:araji,vulcan,moloch'\n" in lines_of(got)
    bot.sos_closed()                                      # окно разобрало [SOS_CLOSE]: бот решил сам
    assert not bot.answer("MANUAL", epoch)                # ответ из старого окна не уходит, как в старом окне
    assert ("log", "[GUI] Ответ «MANUAL» не отправлен: бот уже решил сам.\n") in collect(
        events, lambda g: any(k == "log" for k, _ in g))
    assert bot.answer("IGNORE", bot.epoch)


def test_stop_command_lets_bot_finish_its_summary(link):
    bot, events = link([[SOS_MANUAL]])
    bot.start("RU")
    collect(events, lambda g: any(k == "bot_event" for k, _ in g))
    assert bot.request_stop(bot.epoch)
    assert bot.stopping
    got = collect(events, lambda g: ("bot_exit", bot.run_id) in g)
    assert any("[ИТОГ] Причина остановки: Команда STOP из окна SOS" in line for line in lines_of(got))
    assert bot.ended_by is None                           # остановился сам, окно его не убивало
    assert bot.exited(bot.run_id) and not bot.stopping


def test_stop_command_ignored_then_window_stops_bot(link, monkeypatch):
    monkeypatch.setattr(bot_link, "STOP_GRACE_S", 0.5)
    bot, events = link([["10:00:00.500 [ТАКТИКА] жду"]], ignore_stop=True)
    bot.start("RU")
    collect(events, lambda g: any(k == "bot_line" and "жду" in v for k, v in g))
    proc = bot.process
    bot.request_stop(bot.epoch)
    got = collect(events, lambda g: ("bot_exit", bot.run_id) in g)
    assert any(k == "log" and "не остановился" in v for k, v in got)
    assert proc.poll() is not None and bot.ended_by == "main_reason_killed"


def test_kill_is_immediate_and_removes_pause(link, tmp_path):
    bot, events = link([["@sleep 30"]])
    bot.start("RU")
    collect(events, lambda g: ("bot_started", bot.run_id) in g)
    assert bot.toggle_pause() and (tmp_path / "pause.flag").exists()
    proc = bot.process
    started = time.monotonic()
    assert bot.kill()
    assert proc.poll() is not None and time.monotonic() - started < 3
    assert not (tmp_path / "pause.flag").exists()
    got = collect(events, lambda g: ("bot_exit", bot.run_id) in g)
    assert ("log", "[GUI] ЭКСТРЕННЫЙ СТОП. Процесс убит.\n") in got
    assert not any(k == "log" and "Сбой чтения" in v for k, v in got)  # своя остановка — не ошибка
    assert not bot.kill()                                 # второй стоп — нечего останавливать


def test_stop_during_calibration_does_not_start_bot(link):
    release = threading.Event()
    bot, events = link([["@sleep 30"]], calibrate=lambda: release.wait(5))
    bot.start("RU")
    assert bot.running() and bot.starting                 # ещё калибруется окно игры
    assert bot.kill()
    release.set()
    collect(events, lambda g: ("bot_exit", bot.run_id) in g)
    assert bot.process is None and not bot.running()


def test_debug_pause_continue_sends_empty_line(link):
    bot, events = link([["10:00:00.100 [ПАУЗА ОТЛАДКИ] Бой завершен."], []])
    bot.start("RU")
    got = collect(events, lambda g: any("[ПАУЗА ОТЛАДКИ]" in line for line in lines_of(g)))
    assert [v[0] for k, v in got if k == "bot_event"] == [bot_link.DEBUG_PAUSE]
    assert any("[ПАУЗА ОТЛАДКИ]" in line for line in lines_of(got))  # эта строка в журнале остаётся
    bot.debug_wait = True
    assert bot.continue_debug() and not bot.debug_wait
    got = collect(events, lambda g: any("Получено: ''" in line for line in lines_of(g)))


# ── Telegram с повторами ────────────────────────────────────────────────────
def test_sos_in_telegram_is_resent_when_network_comes_back(tmp_path, monkeypatch):
    from test_telegram import FakeTelegram, write_profile
    from ui import sos_telegram
    tg = sos_telegram.telegram_agent
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tg, "TIMEOUT", (0.5, 0.5))
    monkeypatch.setattr(tg, "API_URL", "http://127.0.0.1:9")   # связи нет
    write_profile(tmp_path)
    fake = FakeTelegram()
    logs, answers = [], []

    def log(text):
        logs.append(text)
        if "Пробую снова" in text and len(logs) == 2:
            monkeypatch.setattr(tg, "API_URL", fake.url)   # связь вернулась

    try:
        question = sos_telegram.TelegramQuestion(sos_telegram.SOS, {"araji": 18}, "RU", answers.append, log,
                                                 info=SOS_INFO, delays=(0.2, 0.2, 0.2, 0.2)).start()
        end = time.monotonic() + 15
        while not question.sent and time.monotonic() < end:
            time.sleep(0.05)
        fake.updates = [{"update_id": 9, "callback_query": {"id": "c", "data": "manual"}}]  # нажали «Пройти руками»
        while not answers and time.monotonic() < end:
            time.sleep(0.05)
    finally:
        fake.close()
    assert answers == ["manual"], logs
    assert question.sent and any("с 3-й попытки" in line for line in logs), logs
    assert "sendPhoto" in fake.methods() or "sendMessage" in fake.methods()


def test_telegram_question_stops_retrying_when_answered_in_window(tmp_path, monkeypatch):
    from test_telegram import write_profile
    from ui import sos_telegram
    tg = sos_telegram.telegram_agent
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tg, "TIMEOUT", (0.3, 0.3))
    monkeypatch.setattr(tg, "API_URL", "http://127.0.0.1:9")
    write_profile(tmp_path)
    logs = []
    question = sos_telegram.TelegramQuestion(sos_telegram.SOS, {}, "RU", lambda d: None, logs.append,
                                             delays=(30, 30)).start()
    end = time.monotonic() + 10
    while not logs and time.monotonic() < end:
        time.sleep(0.05)
    assert logs and "Пробую снова через 30 с" in logs[0]
    question.stop()                                        # ответили в окне программы
    time.sleep(0.3)
    assert len(logs) == 1 and not question.sent


def test_no_team_telegram_has_no_ignore_button():
    import telegram_report
    keys = [b["callback_data"] for row in telegram_report.sos_keyboard(can_rollback=False)["inline_keyboard"]
            for b in row]
    assert keys == ["stop", "manual"]                      # «Продолжить» боту в этом окне непонятно (ошибка 3.1)


# ── Окно программы: строка бота → окно, кнопка → команда ────────────────────
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


@pytest.fixture
def window(tmp_path, monkeypatch):
    """Новое окно; бот — поддельный: окно запускает его той же командой (python main.py в папке программы)."""
    for name in ("pygetwindow", "pyautogui"):
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name) or types.ModuleType(name))
    sys.modules["pygetwindow"].getAllWindows = lambda: []
    sys.modules["pygetwindow"].getWindowsWithTitle = lambda title: []
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").symlink_to(ROOT / "docs")
    shutil.copy(FAKE_BOT, tmp_path / "main.py")
    import data_paths
    data_paths._CHECKED.clear()
    from ui import app as app_mod
    from ui import icons, widgets
    icons.clear_cache()
    widgets._titan_picture.cache_clear()
    app = app_mod.App(settings_path=str(tmp_path / "ui_settings.json"), status_watcher=Quiet(),
                      hotkey_watcher=Quiet())
    app.update()
    yield app
    if not app._closing:
        app.shutdown()


def pump(app, seconds=0.3, until=None):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.update()
        if until and until():
            return True
        time.sleep(0.02)
    return bool(until and until())


def run_bot(app, tmp_path, steps, **extra):
    """Поддельный бот печатает steps[0], после каждой команды — следующий шаг. Возвращает главную."""
    (tmp_path / "fake_bot.json").write_text(json.dumps({"steps": steps, "sos_info": SOS_INFO, **extra},
                                                       ensure_ascii=False), encoding="utf-8")
    dash = app.frames["dash"]
    app.events.put(("phone", True))
    pump(app, 0.2)
    dash.start_bot()
    assert pump(app, 10, until=lambda: dash.stats.started is not None), dash.log_text()
    return dash


def received(dash):
    return [line.split("Получено: ", 1)[1] for line in dash.log_text().splitlines() if "Получено: " in line]


def wait_window(app, dash, count=1):
    assert pump(app, 10, until=lambda: len(dash.open_windows()) >= count), dash.log_text()
    pump(app, 0.2)
    return dash.open_windows()[-1].window


def wait_command(app, dash, command):
    assert pump(app, 10, until=lambda: repr(command) in received(dash)), received(dash)


@gui
def test_sos_buttons_send_old_commands(window, tmp_path):
    from ui import sos_dialogs
    dash = run_bot(window, tmp_path, [["@info", SOS_LINE], [SOS_LINE], [SOS_LINE], []])
    sos = wait_window(window, dash)
    assert isinstance(sos, sos_dialogs.InterventionWindow) and set(sos.buttons) == {"manual", "ignore", "rollback"}
    assert dash.session_status.cget("text").strip() == "Ждёт вашего решения"
    sos.buttons["manual"].invoke()
    wait_command(window, dash, "MANUAL")
    assert sos.closed
    sos = wait_window(window, dash)
    sos.buttons["ignore"].invoke()
    wait_command(window, dash, "IGNORE")
    sos = wait_window(window, dash)
    sos.buttons["rollback"].invoke()                      # «Откатить бой» → «Собери состав»
    pump(window, 0.3)
    question = dash.questions[-1]
    picker = question.picker
    assert picker is not None and not sos.winfo_viewable()
    assert picker.chosen == ["araji", "ignis", "acheron"]  # сразу выбран пак, который проиграл
    assert not picker.rows["sigurd"].enabled and picker.rows["vulcan"].enabled  # комната огня — только огонь
    assert not picker.rows["metida"].enabled              # Метида — только в смешанную
    picker.cancel()                                       # закрыли выбор — окно SOS вернулось, бот ничего не получил
    pump(window, 0.3)
    assert sos.winfo_viewable() and not sos.closed and "ROLLBACK" not in "".join(received(dash))
    sos.buttons["rollback"].invoke()
    pump(window, 0.3)
    picker = question.picker
    picker.toggle("acheron")
    picker.toggle("vulcan")
    picker.toggle("moloch")
    picker.apply()
    wait_command(window, dash, "ROLLBACK:araji,ignis,vulcan,moloch")
    assert sos.closed and not dash.questions


@gui
def test_sos_cross_asks_and_stop_lets_bot_write_summary(window, tmp_path):
    dash = run_bot(window, tmp_path, [["@info", SOS_LINE]])
    sos = wait_window(window, dash)
    window.tk.call(sos.protocol("WM_DELETE_WINDOW"))      # крестик окна SOS — вопрос, бот работает
    pump(window, 0.3)
    question = dash.questions[-1]
    assert question.confirm is not None and dash.bot_running() and not sos.closed
    question.confirm._finish("cancel")                    # «Отмена» — всё как было
    pump(window, 0.2)
    assert dash.bot_running() and not sos.closed and not received(dash)
    window.tk.call(sos.protocol("WM_DELETE_WINDOW"))
    pump(window, 0.3)
    question.confirm.body.confirm_button.invoke()         # «Остановить бота» → STOP, бот пишет итог и выходит
    wait_command(window, dash, "STOP")
    assert pump(window, 10, until=lambda: not dash.bot_running())
    pump(window, 0.3)
    assert dash.left_mode == "summary"
    assert "Команда STOP из окна SOS" in dash.summary_reason.cget("text")
    assert dash.stats.sos == 1 and dash.link.ended_by is None


@gui
def test_manual_battle_sos_offers_stop(window, tmp_path):
    dash = run_bot(window, tmp_path, [[SOS_MANUAL]])
    sos = wait_window(window, dash)
    assert set(sos.buttons) == {"manual", "ignore", "stop"}
    sos.buttons["stop"].invoke()
    wait_command(window, dash, "STOP")


@gui
def test_no_team_window(window, tmp_path):
    dash = run_bot(window, tmp_path, [[NO_TEAM_LINE], [NO_TEAM_LINE], [NO_TEAM_LINE], []])
    window_ = wait_window(window, dash)
    assert set(window_.buttons) == {"stop", "manual", "new_pack"}  # без «Игнорировать» (ошибка 3.1)
    window_.buttons["manual"].invoke()
    wait_command(window, dash, "MANUAL")
    window_ = wait_window(window, dash)
    window_.buttons["new_pack"].invoke()
    pump(window, 0.3)
    picker = dash.questions[-1].picker
    assert picker.chosen == [] and picker.rows["pallant"].enabled and not picker.rows["araji"].enabled
    for titan in ("angus", "avalon", "eden"):
        picker.toggle(titan)
    picker.toggle("araji")                                # чужую стихию выбрать нельзя
    assert picker.chosen == ["angus", "avalon", "eden"]
    picker.apply()
    wait_command(window, dash, "NEW_PACK:angus,avalon,eden")
    window_ = wait_window(window, dash)
    window_.buttons["stop"].invoke()
    wait_command(window, dash, "STOP")


@gui
def test_test_pack_window(window, tmp_path):
    dash = run_bot(window, tmp_path, [["@info", TEST_LINE], [TEST_LINE], []])
    test = wait_window(window, dash)
    assert set(test.buttons) == {"other", "confirm"}
    test.buttons["confirm"].invoke()
    wait_command(window, dash, "CONFIRM")
    test = wait_window(window, dash)
    test.buttons["other"].invoke()
    pump(window, 0.3)
    picker = dash.questions[-1].picker
    assert picker.chosen == ["vulcan"]
    picker.toggle("moloch")
    picker.toggle("araji")
    picker.apply()
    wait_command(window, dash, "ROLLBACK:vulcan,moloch,araji")


@gui
def test_sos_close_closes_windows_and_old_answers_are_not_sent(window, tmp_path):
    dash = run_bot(window, tmp_path, [[SOS_LINE, "@sleep 0.5", "10:00:09.000 [SOS_CLOSE] Причина\nРешение: пауза"]])
    sos = wait_window(window, dash)
    question = dash.questions[-1]
    assert pump(window, 10, until=lambda: sos.closed)      # бот решил сам — окно закрылось
    assert not dash.questions
    dash.questions.append(question)                        # ответ из устаревшего окна (например, из Telegram)
    dash._answer(question, "MANUAL")
    pump(window, 0.5)
    assert "[GUI] Ответ «MANUAL» не отправлен: бот уже решил сам." in dash.log_text()
    assert "'MANUAL'" not in received(dash)


@gui
def test_telegram_answer_closes_window_and_sends_command(window, tmp_path):
    dash = run_bot(window, tmp_path, [[SOS_LINE], []])
    sos = wait_window(window, dash)
    question = dash.questions[-1]
    window.events.put(("tg_answer", (question.id, "rb_custom:hyperion,sigurd,nova")))
    wait_command(window, dash, "ROLLBACK_TG:hyperion,sigurd,nova")
    assert sos.closed and "[TELEGRAM] Ответ из Telegram: ROLLBACK_TG:hyperion,sigurd,nova" in dash.log_text()


@gui
def test_debug_pause_button_becomes_continue(window, tmp_path):
    dash = run_bot(window, tmp_path, [["10:00:00.100 [ПАУЗА ОТЛАДКИ] Бой завершен."], []])
    assert pump(window, 10, until=lambda: dash.link.debug_wait)
    pump(window, 0.2)
    assert dash.pause_button.kind == "continue" and dash.pause_button._label.cget("text") == "Продолжить"
    window.on_hotkey("F9")                                # F9 — то же, что кнопка
    wait_command(window, dash, "")
    pump(window, 0.2)
    assert dash.pause_button.kind == "pause" and not dash.link.debug_wait


@gui
def test_closing_scrcpy_stops_bot(window, tmp_path):
    dash = run_bot(window, tmp_path, [["@sleep 30"]])
    proc = dash.link.process
    window.events.put(("phone", False))
    assert pump(window, 5, until=lambda: proc.poll() is not None)
    assert "[GUI] Окно scrcpy закрыто — останавливаю бота." in dash.log_text()
    assert pump(window, 5, until=lambda: dash.left_mode == "summary")
    assert "окно scrcpy закрыто" in dash.summary_reason.cget("text")


@gui
def test_telegram_test_question_falls_back_to_window(window, tmp_path, monkeypatch):
    """Пак прислали из Telegram — «Пак справился» спрашивается там же. Не ушло — окно открывается в программе."""
    from test_telegram import write_profile
    from ui import sos_telegram
    tg = sos_telegram.telegram_agent
    monkeypatch.setattr(tg, "TIMEOUT", (0.3, 0.3))
    monkeypatch.setattr(tg, "API_URL", "http://127.0.0.1:9")   # связи нет
    monkeypatch.setattr(tg, "ALERT_RETRY_S", ())               # без повторов, чтобы тест не ждал 18 минут
    write_profile(tmp_path)
    line = '[SOS_TRIGGER] TEST_SUCCESS:{"titans": {"vulcan": 90}, "source": "telegram"}'
    dash = run_bot(window, tmp_path, [[line], []])
    test = wait_window(window, dash)
    assert "[TELEGRAM] Проверка пака в Telegram не отправлен" in dash.log_text()
    test.buttons["confirm"].invoke()
    wait_command(window, dash, "CONFIRM")
