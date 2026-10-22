"""Задача 15, шаг 4: мини-бар под окном игры (ui/hud.py, ui/hud_place.py, ui/hud_events.py).

Без окна (обычный python):
- место мини-бара: вплотную под картинкой игры, никогда не на ней и не в той части окна, где бот ищет игру
  (vision._calibrate_geometry отрезает снизу 8 px); нет места снизу — над заголовком окна; нет и там — не показывается;
- две строки событий из строк бота: комната (стихия, время, меньше всего ХП), этаж, откат, SOS, пауза, «бот решил сам»,
  окно игры не активно, ошибки — в том числе на настоящем логе сессии 07;
- надписи мини-бара на 13 языках, без эмодзи, с теми же подстановками.
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_hud.py): бот запустился — окно в мини-баре
(ваш ответ 22.10.2026), мини-бар едет за окном игры и прячется без него, кнопки шлют те же команды, что главная,
SOS — красный и первая кнопка поднимает окно SOS, окно SOS встаёт над игрой само по себе; бот остановился — окно
развернулось; процесс выходит сам после крестика, даже если мини-бар на экране.
"""
import os
import re
import subprocess
import sys
import textwrap
import time
import types
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import i18n  # noqa: E402
from ui import hud_events, hud_place  # noqa: E402
from ui.hud_place import GameWindow, Rect  # noqa: E402

LOG_07 = ROOT / "tests" / "data" / "session_07_bot_log.txt"
SCREEN = Rect(0, 0, 1920, 1040)       # 1920×1080 без панели задач


def game_at(left=43, top=81, width=1590, height=709, border=7, title=31, work=SCREEN):
    """Окно scrcpy как в Windows 10: снаружи невидимая рамка border, сверху заголовок title."""
    client = Rect(left, top, left + width, top + height)
    frame = Rect(left - border, top - title - 1, left + width + border, top + height + border)
    return GameWindow(client, frame, work)


# ── Место ───────────────────────────────────────────────────────────────────
def test_hud_right_under_game_picture():
    game = game_at()
    x, y, w, h, side = hud_place.place(game, 60)
    assert (x, y, w, h, side) == (43, 790, 1590, 60, "below")
    assert y >= game.client.bottom                              # на картинку игры не заходит ни на пиксель
    assert y >= game.frame.bottom - hud_place.BOT_BOTTOM_CROP   # и туда, где бот при первом снимке ищет игру


def test_hud_below_bots_crop_when_border_is_thick():
    """Крупный масштаб Windows: невидимая рамка толще 8 px — мини-бар опускается ниже отрезанной ботом полосы."""
    game = game_at(border=12)
    _x, y, _w, _h, side = hud_place.place(game, 75)
    assert side == "below" and y == game.frame.bottom - 8 > game.client.bottom


def test_hud_above_window_when_no_room_below_and_hidden_when_nowhere():
    low = game_at(top=900, height=130)
    x, y, w, h, side = hud_place.place(low, 60)
    assert side == "above" and y + h == low.frame.top           # над заголовком окна — вне снимка бота
    tall = game_at(top=40, height=990)
    assert hud_place.place(tall, 60) is None
    assert hud_place.place(game_at(width=80, height=50), 60) is None


# ── События ─────────────────────────────────────────────────────────────────
def feed_lines(lines):
    feed = hud_events.HudFeed(clock=lambda: "12:00:00")
    for line in lines:
        feed.feed(line)
    return feed


def test_room_event_with_element_time_and_lowest_hp():
    feed = feed_lines([
        "10:25:48.475 [КОМБАТ] Успешный вход. Комната: WATER | Враги: ['araji', 'ignis', 'vulcan']",
        "10:26:02.717  ---> HYPERION: ХП 100%, Энергия 79%",
        "10:26:03.212  ---> SIGURD: ХП 85%, Энергия 69%",
        "10:26:03.722  ---> TIDUS: ХП 91%, Энергия 79%",
        "10:26:05.379 [СТАТИСТИКА] Комнат: 45 | Титанит: 2838",
        "10:26:08.713 [ВРЕМЯ] Комната 45 (water): коридор 17.8 с | всего 28.4 с",
    ])
    (event,) = feed.latest()
    assert event.kind == "room" and event.time == "10:26:05"
    assert hud_events.text(event, "RU") == "Комната 45 пройдена · 28 с · меньше всего ХП: Сигурд 85%"
    assert hud_events.text(event, "EN") == "Room 45 cleared · 28 s · lowest HP: Sigurd 85%"
    name, color, _bg = hud_events.badge(event, "RU")
    assert name == "Вода" and color == "#00B4D8"


def test_events_from_bot_lines_newest_first():
    feed = feed_lines([
        "10:30:00.000 [СТАТИСТИКА] Этажей: 3",
        "10:31:00.000 [ОТКАТ] Запускаю протокол отката боя...",
        "10:32:00.000 [SOS] Причина: SIGURD: ХП 18% (ниже порога 20%)",
    ])
    newest, previous, _oldest = feed.latest()
    assert hud_events.text(newest, "RU") == "Сигурд: ХП 18% (ниже порога 20%)"
    assert hud_events.badge(newest, "RU")[0] == "SOS"
    assert hud_events.text(previous, "RU") == "Откат боя, переигрываю комнату"

    for n in range(4, 8):
        feed.feed(f"10:4{n}:00.000 [СТАТИСТИКА] Этажей: {n}")
    assert [e.data["n"] for e in feed.latest()] == [7, 6, 5, 4]  # только четыре последних, новое сверху


@pytest.mark.parametrize("line, kind, text", [
    ("11:00:00.000 [ВНИМАНИЕ] Окно игры перекрыто (Hero Wars: Kno...). Бот ждет фокуса...", "focus_lost",
     "Окно игры не активно — бот ждёт. Нажмите на игру"),
    ("11:00:01.000 [ИНФО] Окно снова активно. Продолжаем работу.", "focus_back", "Окно игры снова активно"),
    ("11:00:02.000 [МЯГКАЯ ПАУЗА] Бот ждет в коридоре...", "waiting", "Бот ждёт в коридоре"),
    ("11:00:03.000 [ТАКТИКА] Ответа нет 10 мин. Решаю сам.", "auto", "Ответа нет 10 мин — бот решил сам"),
    ("11:00:04.000 [ЛИМИТ] Лимит по времени. Дохожу до точки сохранения и останавливаюсь.", "limit",
     "Лимит сессии: бот дойдёт до точки сохранения"),
    ("11:00:05.000 [ПАУЗА ОТЛАДКИ] Бой завершен. Подтвердите продолжение в GUI.", "debug",
     "Пауза отладки: нажмите «Продолжить»"),
    ("11:00:06.000 [СТОРОЖ] Зависание: экран выбора команды за 30 с", "error",
     "Зависание: экран выбора команды за 30 с"),
    ("11:00:07.000 Traceback (most recent call last):", "python_error", "Ошибка программы — подробности в журнале"),
])
def test_other_events(line, kind, text):
    (event,) = feed_lines([line]).latest()
    assert event.kind == kind and hud_events.text(event, "RU") == text


def test_ordinary_lines_are_not_events():
    feed = feed_lines(["10:25:52.742 [КОМАНДА] Состав уже стоит в слотах",
                       "10:26:09.217 [НАВИГАЦИЯ] Сканирую коридор (динамическое ожидание)...",
                       "10:30:00.000 [SOS_CLOSE] Бот решил сам"])
    assert feed.latest() == []


@pytest.mark.parametrize("line, phase", [
    ("10:00:00.000 [НАВИГАЦИЯ] Сканирую коридор (динамическое ожидание)...", "corridor"),
    ("10:00:00.000 [НАВИГАЦИЯ] Этаж пройден! Активируем точку сохранения...", "checkpoint"),
    ("10:00:00.000 [УСПЕХ] Окно выбора комнат открылось.", "doors"),
    ("10:00:00.000 [КОМБАТ] Успешный вход. Комната: FIRE | Враги: ['angus']", "team"),
    ("10:00:00.000 [ТАКТИКА] Выполняю быстрый старт боя...", "battle"),
    ("10:00:00.000 [АНАЛИЗАТОР] Окно результата (через 1.2 с после появления «ОК»):", "result"),
    ("10:00:00.000 [ОТКАТ] Запускаю протокол отката боя...", "rollback"),
    ("10:00:00.000 [МЯГКАЯ ПАУЗА] Бот ждет в коридоре...", "paused"),
    ("10:00:00.000 [SOS] Причина: ARAJI: ХП 10%", "sos"),
    ("10:00:00.000 [ТАКТИКА] Ручной режим: бот ничего не нажимает и ждёт", "manual"),
])
def test_what_bot_is_doing_now(line, phase):
    feed = feed_lines([line])
    assert feed.phase == phase and hud_events.phase_text(feed, "RU")


def test_phase_text_with_room_and_seconds_and_focus_comes_back():
    now = [100.0]
    feed = hud_events.HudFeed(clock=lambda: "12:00:00", monotonic=lambda: now[0])
    feed.feed("10:00:00.000 [КОМБАТ] Успешный вход. Комната: FIRE | Враги: ['angus']")
    feed.feed("10:00:05.000 [ТАКТИКА] Выполняю быстрый старт боя...")
    now[0] += 12
    assert hud_events.phase_text(feed, "RU") == "Бой · Огонь · 12 с"
    feed.feed("10:00:06.000 [ВНИМАНИЕ] Окно игры перекрыто (Chrome...). Бот ждет фокуса...")
    assert hud_events.phase_text(feed, "RU") == "Ждёт окно игры · 0 с"
    feed.feed("10:00:09.000 [ИНФО] Окно снова активно. Продолжаем работу.")
    assert hud_events.phase_text(feed, "RU") == "Бой · Огонь · 12 с"     # вернулся к тому, что делал


def test_team_hp_after_battle_keeps_order_and_missing_icon():
    feed = feed_lines(["10:00:00.000 [КОМБАТ] Успешный вход. Комната: MIX | Враги: []",
                       "10:00:20.000  ---> RIGEL: ХП 95%, Энергия 80%",
                       "10:00:20.000  ---> IYARI: [МЕРТВ] (ХП = 0%, сходство иконки 0.80)",
                       "10:00:20.000  ---> AMON: [ОТСУТСТВУЕТ] (иконка не найдена: сходство 0.40, порог 0.62)"])
    assert feed.team == [("rigel", 95), ("iyari", 0), ("amon", None)]
    feed.feed("10:01:00.000 [КОМБАТ] Успешный вход. Комната: WATER | Враги: []")
    assert feed.team == [("rigel", 95), ("iyari", 0), ("amon", None)]  # до нового окна результата — прошлый бой
    feed.feed("10:01:20.000  ---> SIGURD: ХП 70%, Энергия 80%")
    assert feed.team == [("sigurd", 70)]


@pytest.mark.parametrize("goal, progress, elapsed, expected", [
    (("titanite", 7500), (2838, 7500, 0.38), 4360, (7500 - 2838) * 4360 / 2838),
    (("time", 120), (60.0, 120, 0.5), 3600, 3600),
    (("rooms", 100), (100, 100, 1.0), 4000, 0),
    (("rooms", 100), (0, 100, 0.0), 30, None),
    (None, None, 100, None),
])
def test_eta(goal, progress, elapsed, expected):
    assert hud_events.eta_seconds(goal, progress, elapsed) == expected


def test_duration_text():
    assert hud_events.duration_text(30, "RU") == "меньше минуты"
    assert hud_events.duration_text(25 * 60, "RU") == "25 мин"
    assert hud_events.duration_text(70 * 60 + 5, "RU") == "1 ч 10 мин"


def test_session_07_log():
    feed = hud_events.HudFeed()
    rooms, kinds = 0, set()
    for line in LOG_07.read_text(encoding="utf-8").splitlines():
        before = feed.version
        feed.feed(line)
        if feed.version != before and feed.events:
            kinds.add(feed.events[-1].kind)
            rooms += feed.events[-1].kind == "room" and "[СТАТИСТИКА] Комнат" in line
    assert rooms == 105 and {"room", "rollback"} <= kinds
    room = next(e for e in reversed(feed.events) if e.kind == "room")
    assert room.data["seconds"] and room.data["low"] and room.data["door"]


def test_hud_texts_in_all_languages():
    keys = set()
    for path in ("ui/hud.py", "ui/hud_events.py"):
        keys |= set(re.findall(r'"(hud_[a-z0-9_]+)"', (ROOT / path).read_text(encoding="utf-8")))
    keys -= {"hud_height", "hud_height_tall"}                   # это размеры (ui/theme.py), а не надписи
    keys |= {f"hud_now_{phase}" for _marker, phase in hud_events.PHASES} | {"hud_now_focus"}
    keys |= {"main_note_ready"}
    assert len(keys) > 25
    ru, english = i18n.TRANSLATIONS["RU"], i18n.TRANSLATIONS["EN"]
    for lang, words in i18n.TRANSLATIONS.items():
        for key in keys:
            text = words.get(key)
            assert text, (lang, key)
            assert not any(unicodedata.category(ch) == "So" for ch in text), (lang, key, text)
            assert set(re.findall(r"\{(\w+)\}", text)) == set(re.findall(r"\{(\w+)\}", ru[key])), (lang, key)
    same = {k for k in keys if english[k] == ru[k]}
    assert same == {"hud_sos", "hud_badge_sos"}                 # «SOS» одинаково на всех языках


# ── Окно ────────────────────────────────────────────────────────────────────
def _gui_available():
    try:
        import tkinter  # noqa: F401
        import customtkinter  # noqa: F401
    except ImportError:
        return False
    return sys.platform == "win32" or bool(os.environ.get("DISPLAY"))


gui = pytest.mark.skipif(not _gui_available(), reason="нет tkinter/customtkinter или экрана")
SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


class Quiet:
    def start(self):
        return self

    def stop(self):
        pass


class Locator:
    """Вместо поиска окна scrcpy в Windows: тест сам двигает «окно игры» или убирает его."""

    def __init__(self):
        self.game = game_at(left=5, top=70, width=1270, height=432, work=Rect(0, 0, 1280, 1000))
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.game


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
    from ui import app as app_mod
    from ui import icons, widgets
    icons.clear_cache()
    widgets._titan_picture.cache_clear()
    locator = Locator()
    window = app_mod.App(settings_path=str(tmp_path / "ui_settings.json"), status_watcher=Quiet(),
                         hotkey_watcher=Quiet(), game_locator=locator)
    window.locator = locator
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


def start_fake_bot(app):
    """Бот «запустился»: процесс — спящий, событие — как от ui/bot_link.py."""
    dash = app.frames["dash"]
    dash.link.process = subprocess.Popen(SLEEPER, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    dash.on_event("bot_started", dash.link.run_id)
    pump(app, 0.3)
    return dash


def hud_rect(app):
    top = app.hud.top
    return top.winfo_x(), top.winfo_y(), top.winfo_width(), top.winfo_height()


@gui
def test_bot_start_collapses_into_hud_under_game(app):
    dash = start_fake_bot(app)
    assert app.mini and app.hud.visible
    assert pump(app, 2, until=lambda: app.hud.shown and hud_rect(app)[1] > 0)
    x, y, w, h = hud_rect(app)
    client = app.locator.game.client
    assert (x, w) == (client.left, client.width) and y == client.bottom and h == 100
    assert app.hud.status.cget("text") == "ФАРМ ИДЁТ"
    assert app.hud.event_rows[0][2].cget("text") == "Бот запущен"
    assert app.hud.team_empty.cget("text") == "боёв ещё не было"
    for line in ("10:00:00.000 [КОМБАТ] Успешный вход. Комната: WATER | Враги: ['araji']",
                 "10:00:20.000  ---> HYPERION: ХП 100%, Энергия 79%",
                 "10:00:20.100  ---> SIGURD: ХП 18%, Энергия 69%",
                 "10:00:21.000 [СТАТИСТИКА] Комнат: 1 | Титанит: 12",
                 "10:00:22.000 [СТАТИСТИКА] Этажей: 2",
                 "10:00:23.000 [НАВИГАЦИЯ] Сканирую коридор (динамическое ожидание)..."):
        dash.add_bot_line(line)
    dash.refresh()
    hud = app.hud
    assert hud.counters.cget("text") == "Комнат: 1 · этажей: 2"
    assert hud.now.cget("text").startswith("Коридор · ")
    assert hud.clock.cget("text").startswith("Время 00:00:")
    shown = [(avatar.titan, hp.cget("text"), hp.cget("text_color")) for cell, avatar, hp in hud.team_slots
             if cell.winfo_manager()]
    assert shown == [("hyperion", "100%", "#E8EAF0"), ("sigurd", "18%", "#F87171")]   # ниже порога паники — красным
    assert hud.event_rows[0][2].cget("text") == "Этаж пройден, всего 2"
    assert hud.event_rows[1][2].cget("text").startswith("Комната 1 пройдена")


@gui
def test_hud_follows_game_window_and_hides_without_it(app):
    start_fake_bot(app)
    assert pump(app, 2, until=lambda: app.hud.shown)
    app.locator.game = game_at(left=200, top=120, width=800, height=360, work=Rect(0, 0, 1280, 1000))
    assert pump(app, 2, until=lambda: hud_rect(app)[:3] == (200, 480, 800))
    app.locator.game = None                                       # окно игры свернули
    assert pump(app, 2, until=lambda: not app.hud.shown)
    assert app.hud.top.state() == "withdrawn" and app.mini
    app.locator.game = game_at(left=40, top=70, width=960, height=432, work=Rect(0, 0, 1280, 1000))
    assert pump(app, 2, until=lambda: app.hud.shown)


@gui
def test_hud_buttons_send_what_main_buttons_send(app, tmp_path, monkeypatch):
    dash = start_fake_bot(app)
    app.hud.buttons["pause"].invoke()
    assert (tmp_path / "pause.flag").exists()                     # мягкая пауза — тот же pause.flag
    assert app.hud.status.cget("text") == "ПАУЗА" and app.hud._button_look[0] == "play-filled"
    app.hud.buttons["pause"].invoke()
    assert not (tmp_path / "pause.flag").exists()
    slept = []
    monkeypatch.setattr(app, "sleep_phone", lambda: slept.append(True))
    app.hud.buttons["sleep"].invoke()
    assert slept == [True]
    app.hud.buttons["expand"].invoke()
    assert not app.mini and not app.hud.visible
    app.frames["dash"].minimize_window()                          # «Свернуть в мини-бар» на главной
    assert app.mini
    proc = dash.link.process
    app.hud.buttons["stop"].invoke()
    assert proc.poll() is not None and not dash.bot_running()     # «СТОП» — сразу, как F10
    dash.on_event("bot_exit", dash.link.run_id)
    assert not app.mini and dash.summary_visible                  # бот остановился — окно развернулось, там итог


@gui
def test_sos_turns_hud_red_and_window_appears_over_game(app):
    from ui import bot_link
    dash = start_fake_bot(app)
    assert pump(app, 2, until=lambda: app.hud.shown)
    dash.add_bot_line("10:45:17.000 [SOS] Причина: SIGURD: ХП 18% (ниже порога 20%)")
    dash.on_event("bot_event", (bot_link.SOS, {"titans": {"sigurd": 18}, "is_manual": False}, time.monotonic()))
    window = dash.questions[0].window
    assert pump(app, 2, until=lambda: window.winfo_viewable())
    assert app.hud.status.cget("text") == "SOS" and app.hud.body.cget("bg") == "#302129"
    assert app.hud._button_look[0] == "play-filled"
    assert app.mini and window.wm_transient() == ""               # окно SOS само по себе, окно программы свёрнуто
    client = app.locator.game.client
    center = window.winfo_rootx() + window.winfo_width() // 2
    assert abs(center - (client.left + client.width // 2)) <= 2   # по центру картинки игры
    raised = []
    dash.raise_questions = lambda open_missing=False: raised.append(open_missing)
    app.hud.buttons["pause"].invoke()                             # на SOS первая кнопка — показать окно SOS
    assert raised == [True] and not os.path.exists("pause.flag")
    window.answer("IGNORE")
    pump(app, 0.2)
    assert app.hud.status.cget("text") == "ФАРМ ИДЁТ"


@gui
def test_hud_language(app):
    start_fake_bot(app)
    app.set_language("DE")
    assert app.hud.status.cget("text") == "FARMEN LÄUFT"
    assert app.hud.event_rows[0][2].cget("text") == "Bot gestartet"
    assert app.hud.team_title.cget("text") == "LP nach dem Kampf"


@gui
def test_restoring_window_from_taskbar_leaves_mini(app):
    start_fake_bot(app)
    assert app.mini
    app.deiconify()                                                # окно развернули кнопкой на панели задач
    assert pump(app, 2, until=lambda: not app.mini)
    assert not app.hud.visible


CLOSE_SCRIPT = textwrap.dedent('''
    import os, subprocess, sys, types
    sys.path.insert(0, ROOT)
    for name in ("pygetwindow", "pyautogui"):
        sys.modules.setdefault(name, types.ModuleType(name))
    class Win:
        title = "HeroWarsBot_Arena"
    sys.modules["pygetwindow"].getAllWindows = lambda: [Win()]          # «телефон подключён»: бот не остановится
    sys.modules["pygetwindow"].getWindowsWithTitle = lambda title: []
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    from ui import app as app_mod
    from ui.hud_place import GameWindow, Rect
    game = GameWindow(Rect(40, 70, 1000, 502), Rect(33, 40, 1007, 509), Rect(0, 0, 1280, 1000))
    app = app_mod.App(settings_path=os.path.join(os.getcwd(), "ui_settings.json"), game_locator=lambda: game)
    dash = app.frames["dash"]
    dash.link.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    print("PID", dash.link.process.pid, flush=True)
    def collapse():
        dash.on_event("bot_started", dash.link.run_id)
        app.after(800, close)
    def close():
        print("HUD", app.hud.shown, flush=True)
        app.tk.call(app.protocol("WM_DELETE_WINDOW"))       # то же, что крестик (на панели задач)
        app.after(400, lambda: app._close_dialog.body.confirm_button.invoke())
    app.after(500, collapse)
    app.mainloop()
    print("EXITED", flush=True)
''')


@gui
def test_process_exits_after_close_with_hud_shown(tmp_path):
    script = f"ROOT = {str(ROOT)!r}\n" + CLOSE_SCRIPT
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True,
                            timeout=60, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = result.stdout + result.stderr
    assert "HUD True" in result.stdout and "EXITED" in result.stdout, out
    assert result.returncode == 0 and "Traceback" not in result.stderr, out
    pid = int(result.stdout.split("PID", 1)[1].split()[0])
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
