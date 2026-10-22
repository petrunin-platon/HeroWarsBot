"""Задача 15: окно программы не зависает и закрывается само (замечание к шагу 1: витрину пришлось закрывать диспетчером задач).

Без экрана: сторож зависаний ui/freeze_guard.py на поддельном окне и поддельных часах.
С экраном (в облаке: xvfb-run -a python3.12 -m pytest tests/test_ui_safety.py):
- наведение на «таблетку» не трогает шрифт и не перекрашивает её снова и снова (в Windows смена шрифта под мышкой
  запускала круг «мышь вошла → перестроить надпись → мышь вошла»);
- окно подтверждения не использует вложенное ожидание wait_visibility;
- отдельный процесс открывает витрину, водит мышью по всему, открывает диалоги и уведомления, жмёт крестик — и обязан
  завершиться сам.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui.freeze_guard import FreezeGuard  # noqa: E402


class FakeRoot:
    """Окно без Tk: запоминает after, чтобы тест сам решал, когда «окно живо»."""

    def __init__(self):
        self.pending = []
        self.cancelled = []
        self.bound = []

    def after(self, ms, func, *args):
        self.pending.append((func, args))
        return f"after#{len(self.pending)}"

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)

    def bind(self, sequence, func, add=None):
        self.bound.append(sequence)

    def run_pending(self):
        pending, self.pending = self.pending, []
        for func, args in pending:
            func(*args)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_guard(tmp_path):
    root, clock = FakeRoot(), Clock()
    guard = FreezeGuard(root, folder=str(tmp_path), freeze_s=5.0, clock=clock)
    guard._beat()  # первая отметка (start() ещё и поток запускает — в тесте он не нужен)
    return guard, root, clock


def test_no_report_while_window_beats(tmp_path):
    guard, root, clock = make_guard(tmp_path)
    for _ in range(20):           # окно живо: каждые 0,5 с отметка
        clock.now += 0.5
        root.run_pending()
        assert guard.check() is None
    assert not list(tmp_path.iterdir())


def test_report_once_when_window_freezes_and_again_after_recovery(tmp_path):
    guard, root, clock = make_guard(tmp_path)
    clock.now += 4.9
    assert guard.check() is None                      # 4,9 с — ещё не зависание
    clock.now += 0.2
    path = guard.check()
    assert path and Path(path).is_file()
    text = Path(path).read_text(encoding="utf-8")
    assert "не отвечает 5 с" in text and "File" in text  # на какой строке каждый поток
    clock.now += 30
    assert guard.check() is None                      # то же зависание второй раз не пишем
    root.run_pending()                                # окно ожило
    clock.now += 6
    assert guard.check()                              # новое зависание — новый файл
    assert len(guard.reports) == 2


def test_stop_ends_beats_and_reports(tmp_path):
    guard, root, clock = make_guard(tmp_path)
    guard.stop()
    assert root.cancelled                             # отметки больше не ставятся
    root.run_pending()
    assert not root.pending
    clock.now += 60
    assert guard.check() is None                      # окно закрыто — это не зависание


def test_window_destroy_stops_guard(tmp_path):
    guard, root, _clock = make_guard(tmp_path)

    class Event:
        widget = root

    class ChildEvent:
        widget = object()

    guard._on_destroy(ChildEvent())                   # закрылся дочерний виджет — сторож работает
    assert not guard._stopped.is_set()
    guard._on_destroy(Event())                        # закрылось само окно
    assert guard._stopped.is_set()


def test_guard_thread_is_daemon(tmp_path):
    """Поток сторожа не держит программу после закрытия окна."""
    root = FakeRoot()
    guard = FreezeGuard(root, folder=str(tmp_path)).start()
    try:
        import threading
        threads = [t for t in threading.enumerate() if t.name == "ui-freeze-guard"]
        assert threads and all(t.daemon for t in threads)
        assert "<Destroy>" in root.bound
    finally:
        guard.stop()


def _gui_available():
    try:
        import tkinter  # noqa: F401
        import customtkinter  # noqa: F401
    except ImportError:
        return False
    return sys.platform == "win32" or bool(os.environ.get("DISPLAY"))


needs_gui = pytest.mark.skipif(not _gui_available(), reason="нет tkinter/customtkinter или экрана")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.chdir(ROOT)
    from ui import demo, icons, widgets
    icons.clear_cache()
    widgets._titan_picture.cache_clear()
    window = demo.Demo("RU")
    window.update()
    yield window
    try:
        window.close()
    except Exception:
        pass


@needs_gui
def test_chip_hover_does_not_touch_font_or_repaint(app):
    chip = app.chips[1]
    calls = []
    original = chip._label.configure

    def spy(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    chip._label.configure = spy
    chip._chip_enter()                 # навели: меняется только фон (рамка передаёт его надписи — bg_color)
    hovered = len(calls)
    assert not any("font" in c or "text" in c for c in calls)
    chip._chip_enter()                 # мышь «вошла» ещё раз (часть таблетки) — вид тот же, ничего не делаем
    chip._paint()
    assert len(calls) == hovered
    chip._hovering = False
    chip._paint()                      # ушли: снова только фон
    assert not any("font" in c or "text" in c for c in calls)
    chip.set_selected(True)            # выбор меняет и шрифт — это не наведение
    assert any("font" in c for c in calls)


@needs_gui
def test_confirm_dialog_without_nested_wait(app, monkeypatch):
    import tkinter
    from ui import widgets

    def forbidden(*_args, **_kwargs):
        raise AssertionError("wait_visibility — вложенное ожидание, в Windows может не кончиться")

    monkeypatch.setattr(tkinter.Misc, "wait_visibility", forbidden)
    answers = []
    dialog = widgets.ConfirmDialog(app, "?", "text", "OK", on_confirm=lambda: answers.append("ok"))
    for _ in range(20):
        app.update()
        app.after(20)
    dialog.body.confirm_button.invoke()
    dialog._finish("cancel")           # второй ответ (Esc после кнопки) не обрабатывается
    assert answers == ["ok"]
    assert not dialog.winfo_exists()


CLOSE_SCRIPT = textwrap.dedent('''
    import sys, os
    sys.path.insert(0, os.getcwd())
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    from ui import demo
    from ui.freeze_guard import FreezeGuard
    from ui.widgets import Toast
    app = demo.Demo("RU")
    guard = FreezeGuard(app).start()
    targets = []
    def collect():
        app.update()
        targets.extend(app.nav + app.chips)
        targets.extend(w for w in app.scroll.winfo_children())
    def hover(i=0):
        if i >= len(targets):
            app.open_delete(); app.after(300, step2); return
        w = targets[i]
        try:
            x = w.winfo_rootx() - app.winfo_rootx() + w.winfo_width() // 2
            y = w.winfo_rooty() - app.winfo_rooty() + w.winfo_height() // 2
            app.event_generate("<Motion>", warp=True, x=x, y=y)
        except Exception:
            pass
        app.after(60, hover, i + 1)
    def step2():
        Toast(app, "один"); Toast(app, "два", kind="deleted", action_text="Вернуть")
        app.after(300, press_close)
    def press_close():
        print("CLOSE", flush=True)
        app.tk.call(app.protocol("WM_DELETE_WINDOW"))   # то же, что крестик окна
    app.after(500, lambda: (collect(), hover()))
    app.mainloop()
    guard.stop()
    print("EXITED", flush=True)
''')


@needs_gui
def test_demo_process_exits_after_close_button():
    result = subprocess.run([sys.executable, "-c", CLOSE_SCRIPT], cwd=ROOT, capture_output=True, text=True,
                            timeout=30, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert "CLOSE" in result.stdout and "EXITED" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
