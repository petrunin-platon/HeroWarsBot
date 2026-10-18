import builtins
import csv
import json
import os
import re
import sys
from datetime import datetime

import pytest

import session_log
from session_log import (
    RoomTimer, SessionLog, Stamper, format_room_line, format_stamp, fmt_duration,
)


class FakeClock:
    """Часы, которые идут только когда мы сами их двигаем."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


# --- время в строке --------------------------------------------------------
def test_format_stamp():
    assert format_stamp(datetime(2026, 10, 18, 14, 3, 21, 457000)) == "14:03:21.457"
    assert format_stamp(datetime(2026, 10, 18, 9, 5, 1, 7000)) == "09:05:01.007"
    assert format_stamp(datetime(2026, 10, 18, 9, 5, 1, 999999)) == "09:05:01.999"


def test_stamper_one_line():
    s = Stamper()
    out = s.process("[НАВИГАЦИЯ] Дверь\n", datetime(2026, 10, 18, 14, 3, 21, 457000))
    assert out == "14:03:21.457 [НАВИГАЦИЯ] Дверь\n"


def test_stamper_blank_lines_have_no_time():
    s = Stamper()
    out = s.process("\n[ИНФО] текст\n", datetime(2026, 10, 18, 14, 0, 0, 0))
    assert out == "\n14:00:00.000 [ИНФО] текст\n"


def test_stamper_multiline_text_every_line_stamped():
    s = Stamper()
    out = s.process("a\nb\n", datetime(2026, 10, 18, 14, 0, 0, 0))
    assert out == "14:00:00.000 a\n14:00:00.000 b\n"


def test_stamper_partial_line_gets_one_stamp():
    s = Stamper()
    t = datetime(2026, 10, 18, 14, 0, 0, 0)
    first = s.process("часть 1", t)
    second = s.process(" часть 2\n", datetime(2026, 10, 18, 14, 0, 5, 0))
    assert first + second == "14:00:00.000 часть 1 часть 2\n"


# --- GUI должен узнавать строки [SOS_TRIGGER] с временем -------------------
# Копия разбора из ui/dashboard.py (monitor_bot_output). Тест ниже следит, что в GUI он не изменился.
def gui_parse_sos(line):
    if "[SOS_TRIGGER]" not in line:
        return None
    if "TEST_SUCCESS:" in line:
        return "test", json.loads(line.split("TEST_SUCCESS:")[1].strip())
    return "sos", json.loads(line.split("[SOS_TRIGGER]")[1].strip())


@pytest.mark.parametrize("payload", [
    {"titans": {"araji": 0, "hyperion": 55}, "is_manual": False},
    {"type": "NO_VALID_TEAM", "room": "mix", "enemies": ["araji"], "reason": "Нет пака"},
])
def test_sos_line_with_time_is_recognized(payload):
    stamper = Stamper()
    # как в main.py: print(f"\n[SOS_TRIGGER] {json.dumps(...)}")
    text = stamper.process(f"\n[SOS_TRIGGER] {json.dumps(payload)}\n", datetime(2026, 10, 18, 14, 3, 21, 457000))
    lines = [l for l in text.split("\n") if l]
    assert len(lines) == 1 and lines[0].startswith("14:03:21.457 [SOS_TRIGGER]")
    assert gui_parse_sos(lines[0]) == ("sos", payload)


def test_test_success_line_with_time_is_recognized():
    payload = {"titans": {"araji": {"hp": 100}}, "source": "gui"}
    text = Stamper().process(f"\n[SOS_TRIGGER] TEST_SUCCESS:{json.dumps(payload)}\n", datetime(2026, 10, 18, 14, 3, 21, 457000))
    line = [l for l in text.split("\n") if l][0]
    assert gui_parse_sos(line) == ("test", payload)


def test_debug_pause_marker_with_time_is_recognized():
    text = Stamper().process("\n[ПАУЗА ОТЛАДКИ] Бой завершен.\n", datetime(2026, 10, 18, 14, 0, 0, 0))
    assert any("[ПАУЗА ОТЛАДКИ]" in l for l in text.split("\n"))


def test_sos_reason_line_is_not_a_trigger():
    # строка «[SOS] Причина: ...» не должна открывать окно вмешательства
    assert "[SOS_TRIGGER]" not in "14:00:00.000 [SOS] Причина: Критический порог!"


def test_gui_still_parses_sos_the_same_way():
    """Если кто-то изменит разбор в ui/dashboard.py, этот тест напомнит проверить время в строках."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "ui", "dashboard.py"), encoding="utf-8").read()
    assert 'if "[SOS_TRIGGER]" in line:' in src
    assert 'line.split("[SOS_TRIGGER]")[1]' in src
    assert 'line.split("TEST_SUCCESS:")[1]' in src
    assert 'if "[ПАУЗА ОТЛАДКИ]" in line:' in src
    assert "startswith" not in src[src.index("def monitor_bot_output"):src.index("def trigger_sos_dialog")]


# --- таймер этапов ---------------------------------------------------------
def make_timer():
    clock = FakeClock()
    return RoomTimer(clock), clock


def test_stages_are_measured():
    timer, clock = make_timer()
    timer.restart("hallway")
    clock.advance(7.9)
    timer.begin("team")
    clock.advance(2.0)
    timer.begin("battle")
    clock.advance(12.4)
    timer.begin("result")
    clock.advance(4.1)
    rec = timer.finish(37, "mix", when=datetime(2026, 10, 18, 14, 3, 21))

    st = rec["stages"]
    assert st["hallway"] == pytest.approx(7.9)
    assert st["team"] == pytest.approx(2.0)
    assert st["battle"] == pytest.approx(12.4)
    assert st["result"] == pytest.approx(4.1)
    assert rec["total"] == pytest.approx(26.4)
    assert rec["time"] == "14:03:21"


def test_same_stage_twice_does_not_reset():
    timer, clock = make_timer()
    timer.restart("hallway")
    clock.advance(1)
    timer.begin("hallway")
    clock.advance(1)
    assert timer.finish(1, "water")["stages"]["hallway"] == pytest.approx(2.0)


def test_waiting_for_user_is_not_in_stage():
    timer, clock = make_timer()
    timer.restart("hallway")
    timer.begin("result")
    clock.advance(3.0)
    with timer.excluded("sos_wait"):
        clock.advance(120.0)
    clock.advance(1.0)
    rec = timer.finish(5, "fire")
    assert rec["stages"]["result"] == pytest.approx(4.0)
    assert rec["stages"]["sos_wait"] == pytest.approx(120.0)
    assert rec["total"] == pytest.approx(4.0)


def test_checkpoint_is_separate_from_hallway():
    timer, clock = make_timer()
    timer.restart("hallway")
    clock.advance(2.0)
    with timer.excluded("checkpoint"):
        clock.advance(15.0)
    clock.advance(3.0)
    rec = timer.finish(10, "water")
    assert rec["stages"]["hallway"] == pytest.approx(5.0)
    assert rec["stages"]["checkpoint"] == pytest.approx(15.0)
    assert rec["total"] == pytest.approx(5.0)


def test_exception_inside_excluded_still_closes_it():
    timer, clock = make_timer()
    timer.restart("hallway")
    with pytest.raises(RuntimeError):
        with timer.excluded("checkpoint"):
            clock.advance(2.0)
            raise RuntimeError("x")
    clock.advance(1.0)
    rec = timer.finish(1, "water")
    assert rec["stages"]["checkpoint"] == pytest.approx(2.0)
    assert rec["stages"]["hallway"] == pytest.approx(1.0)


def test_rollback_in_same_room_accumulates():
    timer, clock = make_timer()
    timer.restart("hallway")
    clock.advance(6.0)
    timer.begin("team"); clock.advance(1.0)
    timer.begin("battle"); clock.advance(10.0)
    timer.begin("result"); clock.advance(3.0)
    timer.begin("rollback"); clock.advance(9.0)
    timer.begin("hallway"); clock.advance(4.0)    # второй заход в комнату
    timer.begin("team"); clock.advance(5.0)
    timer.begin("battle"); clock.advance(11.0)
    timer.begin("result"); clock.advance(2.0)
    st = timer.finish(8, "mix")["stages"]
    assert st["hallway"] == pytest.approx(10.0)
    assert st["team"] == pytest.approx(6.0)
    assert st["battle"] == pytest.approx(21.0)
    assert st["result"] == pytest.approx(5.0)
    assert st["rollback"] == pytest.approx(9.0)


def test_finish_starts_next_room_from_hallway():
    timer, clock = make_timer()
    timer.restart("hallway")
    clock.advance(5)
    timer.finish(1, "water")
    clock.advance(0.5)
    timer.begin("team"); clock.advance(2)
    rec = timer.finish(2, "water")
    assert rec["stages"]["hallway"] == pytest.approx(0.5)
    assert rec["stages"]["team"] == pytest.approx(2.0)


def test_restart_throws_away_old_numbers():
    timer, clock = make_timer()
    timer.restart("hallway")
    clock.advance(500)          # например, мягкая пауза
    timer.count("door_misses")
    timer.restart("hallway")
    clock.advance(3)
    rec = timer.finish(1, "water")
    assert rec["stages"]["hallway"] == pytest.approx(3.0)
    assert rec["counts"] == {}


def test_counts_are_per_room():
    timer, clock = make_timer()
    timer.restart("hallway")
    timer.count("door_misses")
    timer.count("repeat_clicks"); timer.count("repeat_clicks")
    assert timer.finish(1, "water")["counts"] == {"door_misses": 1, "repeat_clicks": 2}
    assert timer.finish(2, "water")["counts"] == {}


# --- строка [ВРЕМЯ] --------------------------------------------------------
def make_record(room_no, room_type, hallway=0.0, team=0.0, battle=0.0, result=0.0, rollback=0.0,
                checkpoint=0.0, sos_wait=0.0, counts=None):
    stages = dict(hallway=hallway, team=team, battle=battle, result=result, rollback=rollback,
                  checkpoint=checkpoint, sos_wait=sos_wait)
    return {"time": "14:00:00", "room_no": room_no, "room_type": room_type, "stages": stages,
            "total": hallway + team + battle + result + rollback, "counts": counts or {}}


def test_room_line_matches_plan_example():
    rec = make_record(37, "mix", hallway=7.9, team=0.0, battle=12.4, result=4.1)
    assert format_room_line(rec) == (
        "[ВРЕМЯ] Комната 37 (mix): коридор 7.9 с | сборка 0.0 с | бой 12.4 с | результат 4.1 с | всего 24.4 с"
    )


def test_room_line_shows_extras_only_when_present():
    rec = make_record(40, "water", hallway=8.0, battle=12.0, result=4.0, rollback=9.0, checkpoint=12.3,
                      sos_wait=75.2, counts={"door_misses": 1, "repeat_clicks": 2})
    line = format_room_line(rec)
    assert "откат 9.0 с" in line
    assert "всего 33.0 с" in line
    assert "точка сохранения 12.3 с" in line
    assert "ожидание решения 75.2 с" in line
    assert "промахи по двери 1" in line
    assert "повторные нажатия 2" in line
    assert "окна SOS" not in line


def test_room_line_hides_waits_that_round_to_zero():
    rec = make_record(1, "water", hallway=5.0, checkpoint=0.04, sos_wait=0.02, rollback=0.01)
    line = format_room_line(rec)
    assert "точка сохранения" not in line and "ожидание решения" not in line and "откат" not in line


# --- итог сессии -----------------------------------------------------------
def make_session(tmp_path=None):
    clock = FakeClock()
    log = SessionLog(clock=clock, directory=str(tmp_path) if tmp_path else None,
                     started=datetime(2026, 10, 18, 14, 0, 0))
    return log, clock


def play_room(log, clock, room_no, room_type, hallway, team, battle, result, **kw):
    log.timer.restart("hallway") if room_no == 1 else None
    clock.advance(hallway)
    log.timer.begin("team"); clock.advance(team)
    log.timer.begin("battle"); clock.advance(battle)
    log.timer.begin("result"); clock.advance(result)
    return log.finish_room(room_no, room_type)


def test_summary_on_invented_data():
    log, clock = make_session()
    play_room(log, clock, 1, "water", 6, 0, 12, 4)       # 22
    play_room(log, clock, 2, "mix", 7, 0, 13, 4)         # 24
    play_room(log, clock, 3, "earth", 6, 0, 30, 4)       # 40
    play_room(log, clock, 4, "water", 20, 0, 12, 4)      # 36
    log.count("door_misses")
    log.count("repeat_clicks"); log.count("repeat_clicks")
    log.count("sos")
    log.count("rollbacks")
    log.tap_delays.extend([0.2, 0.6, 0.4])
    log.set_stop_reason("Пройдено 4 комнаты.")
    clock.advance(7)

    text = "\n".join(log.summary_lines(rooms=4, titanite=24))
    assert "Причина остановки: Пройдено 4 комнаты." in text
    assert "Комнат: 4 | Титанит: 24" in text
    assert "Длительность: 2 мин 9 с" in text                   # 22+24+40+36 + 7 = 129 с
    assert "Среднее время комнаты (4 зам.): 30.5 с" in text
    assert "коридор 9.8 с | сборка 0.0 с | бой 16.8 с | результат 4.0 с" in text
    assert "earth 40.0 с (1)" in text and "mix 24.0 с (1)" in text and "water 29.0 с (2)" in text
    # три самые долгие: 40, 36, 24
    longest = [l for l in text.split("\n") if l.startswith("[ИТОГ]   Комната")]
    assert [l.split()[2] for l in longest] == ["3", "4", "2"]
    assert "дольше всего — бой 30.0 с" in longest[0]
    assert "дольше всего — коридор 20.0 с" in longest[1]
    assert "промахи по двери 1 | повторные нажатия 2 | окна SOS 1 | откаты 1" in text
    assert "Нажатия adb tap: 3 шт. | задержка среднее 0.40 с, максимум 0.60 с" in text


def test_summary_duration_value():
    log, clock = make_session()
    clock.advance(3725)
    assert "Длительность: 1 ч 2 мин 5 с" in "\n".join(log.summary_lines(0, 0))


def test_summary_without_rooms():
    log, clock = make_session()
    text = "\n".join(log.summary_lines(0, 0))
    assert "не пройдено ни одной комнаты" in text
    assert "Причина остановки: не указана" in text
    assert "замеров нет" in text


def test_summary_separate_waits():
    log, clock = make_session()
    log.timer.restart("hallway")
    with log.timer.excluded("checkpoint"):
        clock.advance(12)
    log.timer.begin("result")
    with log.timer.excluded("sos_wait"):
        clock.advance(100)
    log.finish_room(1, "fire")
    text = "\n".join(log.summary_lines(1, 6))
    assert "точка сохранения 12.0 с | ожидание решения 100.0 с" in text


def test_summary_printed_once(capsys):
    log, clock = make_session()
    log.print_summary(0, 0)
    first = capsys.readouterr().out
    log.print_summary(0, 0)
    assert "[ИТОГ]" in first
    assert capsys.readouterr().out == ""


def test_stop_reason_first_one_wins_unless_forced():
    log, _ = make_session()
    log.set_stop_reason("Ctrl+Q")
    log.set_stop_reason("другая")
    assert log.stop_reason == "Ctrl+Q"
    log.set_stop_reason("Ошибка", force=True)
    assert log.stop_reason == "Ошибка"


def test_fmt_duration():
    assert fmt_duration(5) == "5 с"
    assert fmt_duration(125) == "2 мин 5 с"
    assert fmt_duration(5400) == "1 ч 30 мин 0 с"


# --- задержка нажатия ------------------------------------------------------
class FakeProc:
    def __init__(self, clock, takes):
        self.clock, self.takes = clock, takes

    def wait(self):
        self.clock.advance(self.takes)


def test_tap_delay_measured_in_background():
    log, clock = make_session()
    started = clock()
    thread = log.track_tap(FakeProc(clock, 0.7), started)
    thread.join(2)
    assert log.tap_delays == [pytest.approx(0.7)]


def test_tap_tracking_survives_broken_process():
    class Broken:
        def wait(self):
            raise OSError("нет adb")

    log, _ = make_session()
    log.track_tap(Broken()).join(2)
    assert log.tap_delays == []


# --- CSV -------------------------------------------------------------------
def test_csv_rows(tmp_path):
    log, clock = make_session(tmp_path)
    play_room(log, clock, 1, "water", 6, 1, 12, 4)
    log.count("door_misses")
    play_room(log, clock, 2, "mix", 7, 0, 13, 4)

    files = list(tmp_path.glob("timings_*.csv"))
    assert [f.name for f in files] == ["timings_2026-10-18_14-00-00.csv"]
    rows = list(csv.DictReader(open(files[0], encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["room_no"] == "1" and rows[0]["room_type"] == "water"
    assert float(rows[0]["hallway_s"]) == pytest.approx(6.0)
    assert float(rows[0]["team_s"]) == pytest.approx(1.0)
    assert float(rows[0]["total_s"]) == pytest.approx(23.0)
    assert rows[1]["room_type"] == "mix" and float(rows[1]["total_s"]) == pytest.approx(24.0)
    assert list(rows[0].keys()) == session_log.CSV_COLUMNS


def test_csv_failure_does_not_break_bot(tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    log, clock = make_session(blocker / "sub")      # папку создать нельзя
    play_room(log, clock, 1, "water", 6, 0, 12, 4)
    play_room(log, clock, 2, "water", 6, 0, 12, 4)
    assert len(log.records) == 2
    assert capsys.readouterr().out.count("Не удалось записать замеры") == 1


# --- print с временем и автосохранение -------------------------------------
@pytest.fixture
def restore_print():
    saved_print, saved_hook = builtins.print, sys.excepthook
    saved_session = (session_log.SESSION.stop_reason, session_log.SESSION.directory)
    yield
    builtins.print, sys.excepthook = saved_print, saved_hook
    session_log.SESSION.stop_reason, session_log.SESSION.directory = saved_session


def test_install_writes_stamped_lines_to_file_immediately(tmp_path, restore_print, capsys):
    log_file = session_log.install(str(tmp_path))
    print("[НАВИГАЦИЯ] Дверь зафиксирована")
    print("\n[СТАТИСТИКА] Комнат: 1")

    # файл читаем, пока бот «работает» — запись должна быть уже на диске
    content = open(log_file.path, encoding="utf-8").read()
    assert re.search(r"^\d\d:\d\d:\d\d\.\d{3} \[НАВИГАЦИЯ\] Дверь зафиксирована$", content, re.M)
    assert re.search(r"^\d\d:\d\d:\d\d\.\d{3} \[СТАТИСТИКА\] Комнат: 1$", content, re.M)
    assert os.path.dirname(log_file.path) == os.path.join(str(tmp_path), "logs")
    assert re.fullmatch(r"bot_log_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.txt", os.path.basename(log_file.path))

    # то же самое видит окно программы
    out = capsys.readouterr().out
    assert re.search(r"^\d\d:\d\d:\d\d\.\d{3} \[НАВИГАЦИЯ\] Дверь зафиксирована$", out, re.M)


def test_install_does_not_touch_stderr_prints(tmp_path, restore_print, capsys):
    session_log.install(str(tmp_path))
    print("ошибка", file=sys.stderr)
    assert capsys.readouterr().err == "ошибка\n"


def test_install_survives_unwritable_folder(tmp_path, restore_print, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert session_log.install(str(blocker / "bot_data")) is None
    print("[ИНФО] живём без файла")
    out = capsys.readouterr().out
    assert "Не удалось создать файл лога" in out
    assert "[ИНФО] живём без файла" in out


def test_excepthook_prints_error_and_sets_reason(tmp_path, restore_print, capsys):
    log_file = session_log.install(str(tmp_path))
    session_log.SESSION.stop_reason = None
    try:
        raise ValueError("сломалось")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    assert session_log.SESSION.stop_reason == "Ошибка: ValueError: сломалось"
    out = capsys.readouterr().out
    assert "ValueError: сломалось" in out
    assert "ValueError: сломалось" in open(log_file.path, encoding="utf-8").read()
