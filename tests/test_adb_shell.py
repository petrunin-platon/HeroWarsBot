# Тесты задачи 11: одно постоянное соединение с телефоном (adb shell) вместо нового adb на каждое нажатие.
# Телефона нет: вместо `adb shell sh` запускается tests/fake_adb.py — он читает команды и отвечает метками, как sh.
import importlib
import os
import sys
import time
import types

import pytest

sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

import adb_shell  # noqa: E402
import click_logic  # noqa: E402

FAKE = os.path.join(os.path.dirname(__file__), "fake_adb.py")


class Clock:
    """Часы, которые двигает тест (переподключение не чаще раза в 5 с, зависшая команда — 5 с)."""

    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_shell(tmp_path, *args, clock=None):
    log_file = tmp_path / "commands.txt"
    logs = []
    shell = adb_shell.AdbShell(command=[sys.executable, FAKE, str(log_file), *args],
                               clock=clock or Clock(), log=logs.append)
    return shell, log_file, logs


def wait_exit(shell, timeout=5.0):
    """Ждём, пока поддельный adb завершится (или бот уже заметил обрыв)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = shell._proc
        if proc is None or proc.poll() is not None:
            return
        time.sleep(0.01)


def received(log_file):
    return log_file.read_text(encoding="utf-8").splitlines() if log_file.exists() else []


def test_taps_go_through_one_connection(tmp_path):
    shell, log_file, logs = make_shell(tmp_path)
    try:
        commands = [shell.run(f"input tap {x} 200") for x in (10, 20, 30, 40, 50)]
        assert all(c is not None for c in commands)
        assert [c.wait(5) for c in commands] == [0] * 5
        assert shell.connects == 1  # adb запущен один раз на все нажатия
        assert received(log_file) == [f"input tap {x} 200" for x in (10, 20, 30, 40, 50)]
        assert logs == []
    finally:
        shell.close()


def test_tap_watch_sees_when_tap_reached_phone(tmp_path):
    """TapWatch (повторное нажатие, ожидание окна) по-прежнему знает, когда нажатие дошло до телефона."""
    shell, _, _ = make_shell(tmp_path)
    try:
        cmd = shell.run("input tap 1 2")
        watch = click_logic.TapWatch(cmd)
        cmd.wait(5)
        assert watch.done_time() is not None
        assert cmd.done_at is not None and cmd.done_at >= cmd.sent_at
    finally:
        shell.close()


def test_phone_messages_go_to_log(tmp_path):
    shell, _, logs = make_shell(tmp_path)
    try:
        assert shell.run("input bad").wait(5) == 0
        assert any("Unknown command" in line and line.startswith("[ADB]") for line in logs)
    finally:
        shell.close()


def test_reconnects_after_connection_drop(tmp_path):
    """Соединение оборвалось (adb закрылся после 2 команд). Пока не прошло 5 с — нажимаем по-старому (None),
    потом бот переподключается сам."""
    clock = Clock()
    shell, log_file, logs = make_shell(tmp_path, "2", clock=clock)
    try:
        assert shell.run("input tap 1 1").wait(5) == 0
        assert shell.run("input tap 2 2").wait(5) == 0
        wait_exit(shell)  # поддельный adb вышел
        clock.now += 1
        assert shell.run("input tap 3 3") is None  # переподключаться рано: вызывающий нажмёт новым adb
        assert any("оборвалось" in line for line in logs)
        clock.now += adb_shell.RECONNECT_PAUSE_S
        cmd = shell.run("input tap 4 4")
        assert cmd is not None and cmd.wait(5) == 0
        assert shell.connects == 2
        assert any("снова открыто" in line for line in logs)
        assert received(log_file) == ["input tap 1 1", "input tap 2 2", "input tap 4 4"]
    finally:
        shell.close()


def test_stuck_phone_breaks_connection(tmp_path):
    """Телефон не отвечает: через COMMAND_TIMEOUT_S соединение закрывается, ждущая команда — «не выполнена»."""
    clock = Clock()
    shell, _, logs = make_shell(tmp_path, "0", "silent", clock=clock)
    try:
        first = shell.run("input tap 1 1")
        assert first is not None and first.poll() is None
        clock.now += adb_shell.COMMAND_TIMEOUT_S + 0.1
        second = shell.run("input tap 2 2")
        assert first.poll() == 1
        assert any("не ответил" in line for line in logs)
        # переподключение сразу (прошло больше 5 с с прошлого), вторая команда ушла в новое соединение
        assert second is not None and shell.connects == 2
    finally:
        shell.close()


def test_no_adb_means_old_way(tmp_path):
    logs = []
    shell = adb_shell.AdbShell(command=[str(tmp_path / "нет_такого_adb")], clock=Clock(), log=logs.append)
    assert shell.run("input tap 1 1") is None
    assert any("по-старому" in line for line in logs)


def test_ping_measures_round_trip(tmp_path):
    shell, _, _ = make_shell(tmp_path)
    try:
        assert shell.ping() is not None
    finally:
        shell.close()


def test_spawn_seconds_without_adb_is_empty():
    assert adb_shell.spawn_seconds(command=("/нет/такого/adb",), runs=2) == []


# ---------------------------------------------------------------------------
# vision: нажатие через постоянное соединение, без него — по-старому
# ---------------------------------------------------------------------------
@pytest.fixture
def vision():
    return importlib.import_module("vision")


def test_adb_input_uses_shell_then_old_way(vision, tmp_path, monkeypatch):
    shell, log_file, _ = make_shell(tmp_path)
    started = []
    monkeypatch.setattr(vision.subprocess, "Popen", lambda args, **k: started.append(args) or "proc")
    try:
        monkeypatch.setattr(vision, "ADB", shell)
        cmd, kind = vision.adb_input(["tap", "5", "6"])
        assert kind == "shell" and cmd.wait(5) == 0
        assert received(log_file) == ["input tap 5 6"] and started == []
        monkeypatch.setattr(vision, "ADB", None)
        proc, kind = vision.adb_input(["tap", "7", "8"])
        assert (proc, kind) == ("proc", "spawn")
        assert started == [["adb", "shell", "input", "tap", "7", "8"]]
    finally:
        shell.close()


# ---------------------------------------------------------------------------
# [ИТОГ]: из чего складывается задержка нажатия
# ---------------------------------------------------------------------------
class Done:
    """Как ShellCommand или процесс: уже выполнена."""

    def __init__(self, code=0, done_at=None):
        self.code, self.done_at = code, done_at

    def wait(self, timeout=None):
        return self.code


def test_summary_splits_tap_delay():
    import session_log
    log = session_log.SessionLog(clock=lambda: 10.0)
    log.track_adb_check([0.40, 0.44, 0.42], [0.01, 0.01, 0.01])
    for started in (9.94, 9.96):  # нажатия через постоянное соединение: 0.06 и 0.04 с
        log.track_tap(Done(0, 10.0), started, "shell").join()
    log.track_tap(Done(0), 9.6, "spawn").join()   # одно — новым adb (соединение было недоступно): 0.4 с
    log.track_tap(Done(1, 10.0), 9.0, "shell").join()  # соединение оборвалось — не замер
    text = "\n".join(log.summary_lines(0, 0))
    assert "Нажатия adb tap: 3 шт. | задержка среднее 0.17 с, максимум 0.40 с | через постоянное соединение 2 из 3" in text
    assert ("Из чего складывается нажатие: запуск нового adb на ПК ~0.41 с, связь с телефоном ~0.010 с, "
            "команда input на телефоне ~0.04 с") in text


def test_summary_without_adb_check_has_no_parts_line():
    import session_log
    log = session_log.SessionLog()
    assert not any("Из чего складывается" in line for line in log.summary_lines(0, 0))
