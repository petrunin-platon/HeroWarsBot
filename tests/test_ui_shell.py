"""Задача 15, шаг 2: логика каркаса нового окна без Tk (проверяется в облаке обычным pytest).

- F9/F10 (ui/hotkeys.py): одно нажатие — одна команда, удержание не повторяет, в чужой программе не срабатывает;
- размер окна под экран (ui/window_fit.py): 1100×720, меньше на маленьком экране и при масштабе Windows, по центру;
- язык окна запоминается (ui/ui_settings.py, bot_data/ui_settings.json);
- плашка телефона и точка Telegram (ui/status.py): в очередь только изменения, profile.yml читается, когда поменялся;
- кнопки шапки (ui/phone.py) пишут в журнал те же строки, что старое окно;
- новые надписи есть на всех 13 языках.
"""
import queue
import sys
import types
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import data_paths  # noqa: E402
import i18n  # noqa: E402
from ui import hotkeys, phone, status, ui_settings, window_fit  # noqa: E402

NEW_KEYS = ["page_title_main", "page_title_stats", "nav_language", "nav_tg_on", "nav_tg_off", "hdr_connected",
            "hdr_waiting", "hdr_tip_sleep", "hdr_tip_restart", "hdr_tip_reset_size", "close_bot_title",
            "close_bot_text", "close_bot_ok"]


class Keyboard:
    """Поддельная клавиатура: какие клавиши сейчас опущены."""

    def __init__(self):
        self.down = set()

    def __call__(self, vk):
        return vk in self.down


# ── F9 / F10 ────────────────────────────────────────────────────────────────
def test_hotkey_press_once_hold_does_not_repeat():
    keys, edges = Keyboard(), hotkeys.KeyEdges()
    assert edges.poll(keys) == []
    keys.down.add(hotkeys.VK_F9)
    assert edges.poll(keys) == ["F9"]
    for _ in range(10):                          # держим клавишу полсекунды — команда одна
        assert edges.poll(keys) == []
    keys.down.clear()
    assert edges.poll(keys) == []
    keys.down.add(hotkeys.VK_F9)                 # нажали снова — снова команда
    assert edges.poll(keys) == ["F9"]


def test_f9_and_f10_are_separate():
    keys, edges = Keyboard(), hotkeys.KeyEdges()
    keys.down.add(hotkeys.VK_F9)
    assert edges.poll(keys) == ["F9"]
    keys.down.add(hotkeys.VK_F10)                # F9 ещё держим, нажали F10
    assert edges.poll(keys) == ["F10"]


def test_hotkey_ignored_in_other_program():
    """Ответ пользователя 22.10.2026: F10 в браузере бота не останавливает. И потом, когда переключились
    на игру с ещё опущенной клавишей, команды тоже нет."""
    keys, edges = Keyboard(), hotkeys.KeyEdges()
    ours = {"active": False}
    keys.down.add(hotkeys.VK_F10)
    assert edges.poll(keys, lambda: ours["active"]) == []
    ours["active"] = True
    assert edges.poll(keys, lambda: ours["active"]) == []
    keys.down.clear()
    edges.poll(keys, lambda: ours["active"])
    keys.down.add(hotkeys.VK_F10)
    assert edges.poll(keys, lambda: ours["active"]) == ["F10"]


def test_hotkey_watcher_puts_events_into_queue():
    events, keys = queue.Queue(), Keyboard()
    watcher = hotkeys.HotkeyWatcher(events, "HeroWarsBot_Arena", key_down=keys, allowed=lambda: True)
    assert watcher.available
    keys.down.add(hotkeys.VK_F10)
    watcher.check()
    watcher.check()
    assert events.get_nowait() == ("hotkey", "F10")
    assert events.empty()


def test_hotkey_watcher_off_outside_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    watcher = hotkeys.HotkeyWatcher(queue.Queue(), "HeroWarsBot_Arena")
    assert not watcher.available
    assert watcher.start() is watcher                # поток не запускается, окно работает и без клавиш


# ── Размер окна ─────────────────────────────────────────────────────────────
def test_window_default_size_on_big_screen():
    w, h, min_w, min_h, x, y = window_fit.fit_window((0, 0, 1920, 1040), 1.0)
    assert (w, h, min_w, min_h) == (1100, 720, 1000, 620)
    assert x == (1920 - 1116) // 2 and y == (1040 - 760) // 2      # по центру свободной части экрана


def test_window_shrinks_with_windows_scaling():
    """1920×1080, масштаб 150%, панель задач 48 px: свободно 1280×688 пикселей макета — 720 не влезает."""
    w, h, min_w, min_h, x, y = window_fit.fit_window((0, 0, 1920, 1032), 1.5)
    assert w == 1100 and h == 1032 // 1.5 - window_fit.FRAME_H
    assert (min_w, min_h) == (1000, 620)
    assert 0 <= y and y + (h + window_fit.FRAME_H) * 1.5 <= 1032 + 1


def test_window_smaller_than_minimum_on_tiny_screen():
    """Ноутбук 1366×768 при 125%: даже 1000×620 не влезает — окно и минимум по экрану, а не за его краем."""
    w, h, min_w, min_h, x, y = window_fit.fit_window((0, 0, 1366, 728), 1.25)
    assert w <= 1366 / 1.25 - window_fit.FRAME_W and h <= 728 / 1.25 - window_fit.FRAME_H
    assert (min_w, min_h) == (min(1000, w), min(620, h)) and h < 620
    assert x >= 0 and y >= 0


def test_window_on_second_part_of_screen():
    """Панель задач слева или сверху: окно внутри свободной части."""
    _w, _h, _mw, _mh, x, y = window_fit.fit_window((60, 40, 1860, 1040), 1.0)
    assert x >= 60 and y >= 40


# ── Язык окна ───────────────────────────────────────────────────────────────
def test_ui_settings_default_and_roundtrip(tmp_path):
    path = str(tmp_path / "ui_settings.json")
    assert ui_settings.load(path) == {"language": "RU"}
    ui_settings.save(path, language="EN")
    assert ui_settings.load(path)["language"] == "EN"
    ui_settings.save(path, other=1)
    assert ui_settings.load(path) == {"language": "EN", "other": 1}   # остальные настройки не теряются
    assert not (tmp_path / "ui_settings.json.tmp").exists()


@pytest.mark.parametrize("text", ["{не json", "[1, 2]", ""])
def test_ui_settings_broken_file_gives_defaults(tmp_path, text):
    path = tmp_path / "ui_settings.json"
    path.write_text(text, encoding="utf-8")
    assert ui_settings.load(str(path)) == {"language": "RU"}


def test_ui_settings_file_in_bot_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_paths._CHECKED.clear()
    assert data_paths.ui_settings_file() == "bot_data/ui_settings.json"
    ui_settings.save(language="DE")
    assert (tmp_path / "bot_data" / "ui_settings.json").is_file()
    assert ui_settings.load()["language"] == "DE"


def test_languages_list_matches_translations():
    assert list(i18n.LANGUAGES) == ["RU", "EN", "UK", "KK", "DE", "ES", "FR", "PL", "PT", "TR", "ZH", "KO", "JA"]
    assert set(i18n.LANGUAGES) == set(i18n.TRANSLATIONS)
    gui = (ROOT / "gui.py").read_text(encoding="utf-8")
    assert "LANGUAGE_MAP = {name: code for code, name in LANGUAGES.items()}" in gui   # старое окно — тот же список
    assert "open_old_window(sys.argv" in gui


def test_usual_start_opens_new_window():
    """start.bat и python gui.py открывают новое окно; старое — только по --old-ui (start_old.bat)."""
    assert ui_settings.open_old_window(["gui.py"]) is False
    assert ui_settings.open_old_window(["gui.py", "--old-ui"]) is True
    assert ui_settings.open_old_window(["gui.py", "--new-ui"]) is False
    assert ui_settings.open_old_window(["HeroWarsBot.exe"], frozen=True) is True      # до шага 9 (картинки окна в .exe)
    assert ui_settings.open_old_window(["HeroWarsBot.exe", "--new-ui"], frozen=True) is False
    start = (ROOT / "start.bat").read_text(encoding="utf-8")
    assert "python gui.py\n" in start.replace("\r\n", "\n") and "--old-ui" not in start
    old = (ROOT / "start_old.bat").read_text(encoding="utf-8")
    assert "python gui.py --old-ui" in old


def test_new_texts_in_all_languages():
    for lang, words in i18n.TRANSLATIONS.items():
        for key in NEW_KEYS:
            text = words.get(key)
            assert text and text != i18n.TRANSLATIONS["RU"][key] or lang == "RU", (lang, key)
            assert not any(unicodedata.category(ch) == "So" for ch in text), (lang, key, text)


# ── Плашка телефона и Telegram ──────────────────────────────────────────────
class Windows:
    def __init__(self):
        self.titles = []
        self.calls = 0

    def __call__(self, title):
        self.calls += 1
        return any(title in t for t in self.titles)


def drain(events):
    out = []
    while not events.empty():
        out.append(events.get_nowait())
    return out


def test_status_reports_only_changes(tmp_path):
    events, windows = queue.Queue(), Windows()
    watcher = status.StatusWatcher(events, "HeroWarsBot_Arena", window_exists=windows,
                                   profile_path=str(tmp_path / "profile.yml"))
    watcher.check()
    assert drain(events) == [("phone", False), ("telegram", False)]
    watcher.check()
    assert drain(events) == []                         # ничего не поменялось — окно ничего не перерисовывает
    windows.titles.append("HeroWarsBot_Arena")
    watcher.check()
    assert drain(events) == [("phone", True)]
    windows.titles.clear()
    watcher.check()
    assert drain(events) == [("phone", False)]


def test_status_telegram_follows_profile(tmp_path, monkeypatch):
    profile = tmp_path / "profile.yml"
    reads = []
    real = status.telegram_ready
    monkeypatch.setattr(status, "telegram_ready", lambda path: reads.append(path) or real(path))
    events = queue.Queue()
    watcher = status.StatusWatcher(events, "X", window_exists=lambda _t: False, profile_path=str(profile))
    profile.write_text("settings:\n  telegram:\n    active: true\n    token: 'YOUR_BOT_TOKEN_HERE'\n"
                       "    chat_id: 'YOUR_CHAT_ID_HERE'\n", encoding="utf-8")
    watcher.check()
    assert ("telegram", False) in drain(events)        # заглушки из profile.example.yml — не настроен
    watcher.check()
    watcher.check()
    assert len(reads) == 1                              # profile.yml не менялся — не перечитываем
    profile.write_text("settings:\n  telegram:\n    active: true\n    token: '123:abc'\n    chat_id: '42'\n",
                       encoding="utf-8")
    import os
    os.utime(profile, (1, 1))                           # время файла другое — он поменялся
    watcher.check()
    assert drain(events) == [("telegram", True)]
    profile.write_text("settings:\n  telegram:\n    active: false\n    token: '123:abc'\n    chat_id: '42'\n",
                       encoding="utf-8")
    os.utime(profile, (2, 2))
    watcher.check()
    assert drain(events) == [("telegram", False)]


def test_status_window_search_error_means_no_phone():
    events = queue.Queue()

    def broken(_title):
        raise OSError("EnumWindows")

    status.StatusWatcher(events, "X", window_exists=broken, profile_path="нет.yml").check()
    assert ("phone", False) in drain(events)


# ── Кнопки шапки: те же строки журнала, что у старого окна ──────────────────
class FakeWin:
    def __init__(self):
        self.isMinimized = True
        self.restored = self.activated = False

    def restore(self):
        self.restored = True

    def activate(self):
        self.activated = True


def fake_window_modules(monkeypatch, windows):
    gw = types.ModuleType("pygetwindow")
    gw.getWindowsWithTitle = lambda title: windows
    gui = types.ModuleType("pyautogui")
    gui.pressed = []
    gui.hotkey = lambda *keys: gui.pressed.append(keys)
    monkeypatch.setitem(sys.modules, "pygetwindow", gw)
    monkeypatch.setitem(sys.modules, "pyautogui", gui)
    monkeypatch.setattr(phone.time, "sleep", lambda _s: None)
    return gui


def test_sleep_screen_sends_alt_o(monkeypatch):
    win = FakeWin()
    gui = fake_window_modules(monkeypatch, [win])
    lines = []
    phone.sleep_screen(lines.append)
    assert gui.pressed == [("alt", "o")] and win.restored and win.activated
    assert lines[0].startswith("[СИСТЕМА] Выключаю физический дисплей")
    assert lines[-1].startswith("[ИНФО] Экран телефона погашен")


def test_sleep_screen_without_window(monkeypatch):
    gui = fake_window_modules(monkeypatch, [])
    lines = []
    phone.sleep_screen(lines.append)
    assert gui.pressed == [] and lines[-1] == "[ОШИБКА] Окно трансляции не найдено.\n"


def test_reset_window_size_uses_reference_size(monkeypatch):
    calls = []
    env = types.ModuleType("environment")
    env.calibrate_window = lambda title, w, h: calls.append((title, w, h)) or True
    monkeypatch.setitem(sys.modules, "environment", env)
    lines = []
    phone.reset_window_size(lines.append)
    assert calls == [("HeroWarsBot_Arena", 1606, 748)]
    assert lines == ["[GUI] Сброс размеров окна к эталонным (1606x748)...\n"]
