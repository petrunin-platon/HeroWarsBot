"""Задача 15, шаг 2: каркас нового окна (ui/app.py) — на виртуальном экране.

В облаке: xvfb-run -a python3.12 -m pytest tests/test_ui_app.py (без tkinter, customtkinter или экрана тесты пропускаются).
Проверяется:
- полоска, шапка, шесть разделов (внутри — старые вкладки), заголовок раздела в шапке;
- язык меняет надписи окна и старых вкладок и запоминается до следующего запуска;
- события из фоновых потоков (телефон, Telegram, строки журнала) доходят до окна через очередь;
- F9 и F10 делают то же, что «Мягкая пауза» и «Экстренный СТОП» старой главной, и только когда бот запущен;
- кнопки шапки не замораживают окно (работа — в фоне или через after);
- крестик: бот работает — вопрос «Остановить бота?»; потом бот и scrcpy остановлены, а процесс окна выходит сам.
pygetwindow и pyautogui есть только в Windows — здесь вместо них заглушки.
"""
import os
import subprocess
import sys
import textwrap
import threading
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _gui_available():
    try:
        import tkinter  # noqa: F401
        import customtkinter  # noqa: F401
    except ImportError:
        return False
    return sys.platform == "win32" or bool(os.environ.get("DISPLAY"))


pytestmark = pytest.mark.skipif(not _gui_available(), reason="нет tkinter/customtkinter или экрана")

# Заглушки модулей Windows для старой главной (ui/dashboard.py) и environment.py — до их импорта
STUBS = '''
import sys, types
for _name in ("pygetwindow", "pyautogui"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except Exception:
            sys.modules[_name] = types.ModuleType(_name)
_gw = sys.modules["pygetwindow"]
if not hasattr(_gw, "getAllWindows"):
    _gw.getAllWindows = lambda: []
    _gw.getWindowsWithTitle = lambda title: []
'''
exec(STUBS)

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


class Quiet:
    """Вместо фоновых наблюдателей: тест сам кладёт события в очередь."""

    def start(self):
        return self

    def stop(self):
        pass


def make_app(tmp_path):
    from ui import app as app_mod
    from ui import icons, widgets
    icons.clear_cache()
    widgets._titan_picture.cache_clear()
    window = app_mod.App(settings_path=str(tmp_path / "ui_settings.json"), status_watcher=Quiet(),
                         hotkey_watcher=Quiet())
    window.update()
    return window


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").symlink_to(ROOT / "docs")
    import data_paths
    data_paths._CHECKED.clear()
    return tmp_path


@pytest.fixture
def app(workdir):
    window = make_app(workdir)
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


def log_text(window):
    return window.frames["dash"].log_box.get("1.0", "end")


def fake_process():
    return subprocess.Popen(SLEEPER, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)


def test_frame_like_design(app):
    from i18n import get_text
    from ui import app as app_mod
    from ui import theme
    icons = {p.stem for p in (ROOT / "ui" / "icons").glob("*.png")}
    assert {page[2] for page in app_mod.PAGES} <= icons
    assert app.nav["dash"].master.winfo_width() == theme.SIZES["rail_width"]
    assert app.title_label.master.winfo_height() == theme.SIZES["header_height"]
    assert app.title_label.cget("text") == get_text("RU", "page_title_main") == "Главная — Фарм"
    assert app.nav["dash"]._active and not app.nav["rules"]._active
    # Заголовок и кнопки старой главной теперь в шапке — в новом окне строка старой главной спрятана
    assert not app.frames["dash"].lbl_title.master.winfo_ismapped()
    assert set(app.header_buttons) == {"moon", "refresh-cw", "maximize-2"}
    assert app.plate.connected is False
    assert app.plate._status.cget("text") == "Ожидание телефона…"
    from ui.window_fit import fit_window, work_area
    assert (app.winfo_width(), app.winfo_height()) == fit_window(work_area(app), app._get_window_scaling())[:2]


def test_pages_switch_like_old_window(app, monkeypatch):
    from i18n import get_text
    from ui import app as app_mod
    from ui import theme
    refreshed = []
    monkeypatch.setattr(app.frames["stats"], "refresh_data", lambda: refreshed.append(1))
    for name, _page, _icon, _tip, title_key in app_mod.PAGES:
        app.nav[name].invoke()
        app.update()
        assert app.page == name
        # viewable, а не ismapped: «О программе» — прокручиваемая рамка, её внутренняя часть «на месте» и когда скрыта
        assert app.frames[name].winfo_viewable()
        assert not any(f.winfo_viewable() for n, f in app.frames.items() if n != name)
        assert app.nav[name]._active and sum(b._active for b in app.nav.values()) == 1
        assert app.title_label.cget("text") == theme.plain_text(get_text("RU", title_key))
    assert refreshed == [1]                               # статистика обновляется при открытии, как в старом окне


def test_language_changes_texts_and_is_remembered(app, workdir):
    from i18n import get_text
    from ui import ui_settings
    app._language_chosen("Deutsch")
    app.update()
    assert app.current_lang == "DE"
    assert app.title_label.cget("text") == get_text("DE", "page_title_main")
    assert app.lang_button.cget("text") == "DE"
    assert app.frames["dash"].btn_launch_scrcpy.cget("text") == get_text("DE", "dash_btn_connect")  # старые вкладки
    assert "[GUI] Язык интерфейса изменен: Deutsch (DE)" in log_text(app)
    assert ui_settings.load(str(workdir / "ui_settings.json"))["language"] == "DE"
    app.shutdown()
    second = make_app(workdir)                            # следующий запуск — сразу на немецком
    try:
        assert second.current_lang == "DE"
        assert second.title_label.cget("text") == get_text("DE", "page_title_main")
    finally:
        second.shutdown()


def test_events_from_background_threads(app):
    from ui import theme
    app.events.put(("phone", True))
    app.events.put(("telegram", True))
    threading.Thread(target=app.log_later, args=("[ТЕСТ] строка из потока\n",)).start()
    assert pump(app, 2, until=lambda: "[ТЕСТ] строка из потока" in log_text(app) and app.telegram_on)
    assert app.plate.connected and app.plate._name.winfo_ismapped()
    assert app.plate._status.cget("text") == "подключено"
    assert app.tg_button._dot_color == theme.COLORS["success"]
    assert app._telegram_tip() == "Telegram: включён"
    app.events.put(("phone", False))
    assert pump(app, 2, until=lambda: not app.plate.connected)
    assert not app.plate._name.winfo_ismapped()


def test_hotkeys_do_what_old_buttons_do(app, workdir):
    dash = app.frames["dash"]
    app.on_hotkey("F9")
    assert "[GUI] Нажата F9, но бот не запущен." in log_text(app)
    assert not (workdir / "pause.flag").exists()
    dash.bot_process = fake_process()
    proc = dash.bot_process
    app.on_hotkey("F9")
    assert (workdir / "pause.flag").exists()              # мягкая пауза — тот же pause.flag
    app.on_hotkey("F9")
    assert not (workdir / "pause.flag").exists()          # снять паузу
    app.on_hotkey("F10")
    assert proc.poll() is not None and dash.bot_process is None
    assert "[GUI] ЭКСТРЕННЫЙ СТОП. Процесс убит." in log_text(app)


def test_close_asks_when_bot_runs(app):
    dash = app.frames["dash"]
    dash.bot_process, dash.scrcpy_process = fake_process(), fake_process()
    bot, scrcpy = dash.bot_process, dash.scrcpy_process
    app.on_close()
    dialog = app._close_dialog
    assert dialog is not None and not app._closing
    app.on_close()                                        # второй крестик — то же окно вопроса, не новое
    assert app._close_dialog is dialog
    pump(app, 0.3)
    dialog._finish("cancel")                              # «Отмена»: бот работает дальше
    assert not app._closing and bot.poll() is None and scrcpy.poll() is None
    app.on_close()
    pump(app, 0.3)
    app._close_dialog.body.confirm_button.invoke()        # «Остановить и закрыть»
    assert app._closing
    assert bot.poll() is not None and scrcpy.poll() is not None


def test_close_without_bot_is_immediate(app):
    dash = app.frames["dash"]
    dash.scrcpy_process = fake_process()
    scrcpy = dash.scrcpy_process
    app.on_close()
    assert app._close_dialog is None and app._closing
    assert scrcpy.poll() is not None                      # scrcpy, запущенный окном, остановлен, как в старом окне


def test_restart_scrcpy_does_not_freeze_window(app, monkeypatch):
    dash = app.frames["dash"]
    dash.scrcpy_process = fake_process()
    old = dash.scrcpy_process
    launched = []
    monkeypatch.setattr(dash, "launch_phone", lambda: launched.append(time.monotonic()))
    started = time.monotonic()
    app.header_buttons["refresh-cw"].invoke()
    assert time.monotonic() - started < 0.3               # в старом окне здесь было time.sleep(1)
    assert old.wait(timeout=5) is not None
    assert "[ADB] Перезапуск scrcpy..." in log_text(app)
    assert pump(app, 3, until=lambda: launched)
    assert launched[0] - started >= 0.9 and len(launched) == 1


def test_header_buttons_work_in_background(app, monkeypatch):
    from ui import phone
    threads = []

    def slow(log, *_args):
        threads.append(threading.current_thread() is threading.main_thread())
        time.sleep(0.5)
        log("[ТЕСТ] готово\n")

    monkeypatch.setattr(phone, "sleep_screen", slow)
    monkeypatch.setattr(phone, "reset_window_size", slow)
    for name in ("moon", "maximize-2"):
        started = time.monotonic()
        app.header_buttons[name].invoke()
        assert time.monotonic() - started < 0.2
    assert pump(app, 3, until=lambda: log_text(app).count("[ТЕСТ] готово") == 2)
    assert threads == [False, False]


def test_telegram_button_opens_settings(app, monkeypatch):
    opened = []
    monkeypatch.setattr(app.frames["rules"], "open_tg_dialog", lambda: opened.append(app.page))
    app.tg_button.invoke()
    assert opened == ["rules"]                            # «Сохранить профиль» — на этой же странице


def test_icon_with_dot_is_wider_than_icon(app):
    from ui.icons import icon_with_dot
    image = icon_with_dot("send", "#A9AFC2", 18, "#4ADE80")
    assert image.cget("size") == (26, 26)


CLOSE_SCRIPT = STUBS + textwrap.dedent('''
    import os, subprocess, sys
    sys.path.insert(0, ROOT)
    class Win:
        title = "HeroWarsBot_Arena"
    sys.modules["pygetwindow"].getAllWindows = lambda: [Win()]
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    from ui import app as app_mod
    from ui import hotkeys
    keys = set()
    app = app_mod.App(settings_path=os.path.join(os.getcwd(), "ui_settings.json"))
    # Поддельная клавиатура вместо Windows: F9 «нажимается» в потоке наблюдателя, как настоящая
    app.hotkeys = hotkeys.HotkeyWatcher(app.events, "x", key_down=lambda vk: vk in keys, allowed=lambda: True).start()
    sleeper = [sys.executable, "-c", "import time; time.sleep(60)"]
    dash = app.frames["dash"]
    dash.bot_process = subprocess.Popen(sleeper, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    dash.scrcpy_process = subprocess.Popen(sleeper)
    print("PIDS", dash.bot_process.pid, dash.scrcpy_process.pid, flush=True)
    targets = []
    def collect():
        app.update()
        targets.extend(app.nav.values())
        targets.extend([app.tg_button, app.lang_button])
        targets.extend(app.header_buttons.values())
    def hover(i=0):
        if i >= len(targets):
            app.after(100, pages); return
        w = targets[i]
        x = w.winfo_rootx() - app.winfo_rootx() + w.winfo_width() // 2
        y = w.winfo_rooty() - app.winfo_rooty() + w.winfo_height() // 2
        app.event_generate("<Motion>", warp=True, x=x, y=y)
        app.after(450 if i % 4 == 0 else 60, hover, i + 1)   # иногда ждём подсказку
    def pages():
        for name in ("rules", "analytics", "stats", "guide", "about", "dash"):
            app.nav[name].invoke(); app.update()
        app._language_chosen("English")
        keys.add(hotkeys.VK_F9)                               # F9 из «окна игры» — через поток и очередь
        app.after(400, check_pause)
    def check_pause():
        keys.clear()
        print("PAUSED" if os.path.exists("pause.flag") else "NOT PAUSED", flush=True)
        print("PHONE", app.plate.connected, flush=True)
        app.tk.call(app.protocol("WM_DELETE_WINDOW"))         # то же, что крестик окна
        app.after(400, confirm)
    def confirm():
        print("DIALOG", app._close_dialog is not None, flush=True)
        app._close_dialog.body.confirm_button.invoke()
    app.after(500, lambda: (collect(), hover()))
    app.mainloop()
    print("EXITED", flush=True)
''')


def test_app_process_exits_after_close_button(workdir):
    script = f"ROOT = {str(ROOT)!r}\n" + CLOSE_SCRIPT
    result = subprocess.run([sys.executable, "-c", script], cwd=workdir, capture_output=True, text=True,
                            timeout=60, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = result.stdout + result.stderr
    assert "PAUSED" in result.stdout and "NOT PAUSED" not in result.stdout, out
    assert "PHONE True" in result.stdout, out
    assert "DIALOG True" in result.stdout and "EXITED" in result.stdout, out
    assert result.returncode == 0, out
    assert "Traceback" not in result.stderr, out
    pids = [int(p) for p in result.stdout.split("PIDS", 1)[1].split()[:2]]
    for pid in pids:                                      # бот и scrcpy остановлены, ничего не осталось
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
