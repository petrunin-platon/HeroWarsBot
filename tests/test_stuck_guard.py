# Тесты задачи 8: защита от зависаний. Сторож и пределы времени — на поддельных часах,
# «Пройти руками» — на последовательности экранов, падение с ошибкой — в отдельном процессе Python.
import os
import subprocess
import sys

import stuck_guard as wd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


# --- Сторож ---

def test_watchdog_alarm_after_5_minutes_without_rooms():
    clock = FakeClock()
    dog = wd.Watchdog(clock=clock)
    clock.advance(299)
    assert not dog.due()
    clock.advance(1)
    assert dog.due()
    assert dog.alarms == 1
    # Сразу же вторая тревога не поднимается: следующая — ещё через 5 минут
    assert not dog.due()
    clock.advance(299)
    assert not dog.due()
    clock.advance(1)
    assert dog.due()
    assert dog.alarms == 2


def test_watchdog_room_resets_alarms():
    clock = FakeClock()
    dog = wd.Watchdog(clock=clock)
    clock.advance(300)
    assert dog.due()
    clock.advance(120)
    dog.progress()  # комната пройдена
    assert dog.alarms == 0
    clock.advance(299)
    assert not dog.due()


def test_watchdog_does_not_count_waiting_for_user():
    """Окно SOS висело 20 минут — это не зависание бота."""
    clock = FakeClock()
    dog = wd.Watchdog(clock=clock)
    clock.advance(200)
    clock.advance(1200)  # ждём решения
    dog.waited_for_user()
    clock.advance(200)
    assert not dog.due()


def test_watchdog_hallway_with_chat_open():
    """Сценарий из «Готово, когда»: в игре открыт чат, бот в коридоре не видит двери.
    Каждые 10 с — таймаут коридора. Через 5 мин тревога, через 15 мин (3 тревоги) — мягкая пауза."""
    clock = FakeClock()
    dog = wd.Watchdog(clock=clock)
    alarms_at = []
    paused_at = None
    for _ in range(200):
        clock.advance(10)  # одна попытка smart_navigate_hallway
        if dog.due():
            alarms_at.append(clock.now - 1000)
            if dog.should_pause():
                paused_at = clock.now - 1000
                break
    assert alarms_at == [300, 600, 900]
    assert paused_at == 900


# --- Пределы по состояниям ---

def test_state_clock_set_team_30s():
    clock = FakeClock()
    sc = wd.StateClock(clock=clock)
    assert sc.expired("SET_TEAM") is None
    clock.advance(29)
    assert sc.expired("SET_TEAM") is None
    clock.advance(1)
    assert sc.expired("SET_TEAM") == 30


def test_state_clock_battle_3_minutes():
    clock = FakeClock()
    sc = wd.StateClock(clock=clock)
    sc.expired("WAIT_FOR_OK")
    clock.advance(179)
    assert sc.expired("WAIT_FOR_OK") is None
    clock.advance(1)
    assert sc.expired("WAIT_FOR_OK") == 180


def test_state_clock_restarts_on_state_change_and_reset():
    clock = FakeClock()
    sc = wd.StateClock(clock=clock)
    sc.expired("SET_TEAM")
    clock.advance(25)
    assert sc.expired("PREP_AUTO") is None
    clock.advance(25)
    assert sc.expired("SET_TEAM") is None  # снова SET_TEAM — отсчёт заново
    clock.advance(25)
    sc.reset()  # ждали решения в окне «Нет подходящего пака»
    clock.advance(25)
    assert sc.expired("SET_TEAM") is None


def test_state_clock_hallway_has_no_limit():
    clock = FakeClock()
    sc = wd.StateClock(clock=clock)
    sc.expired("HALLWAY")
    clock.advance(10_000)
    assert sc.expired("HALLWAY") is None


# --- Пройти руками ---

def run_manual(screens, first=wd.RESULT, step=0.5):
    clock = FakeClock()
    play = wd.ManualPlay(clock=clock, first_screen=first)
    for i, screen in enumerate(screens):
        if play.observe(screen):
            return play, i
        clock.advance(step)
    return play, None


def test_manual_just_closed_result():
    """Окно результата просто закрыли «ОК»: бой засчитан как есть."""
    play, done_at = run_manual([wd.RESULT] * 4 + [wd.HALLWAY] * 10)
    assert done_at is not None
    assert play.room_cleared
    assert not play.replayed


def test_manual_replayed_and_won():
    """«Ещё раз», бой руками, окно результата, «ОК», коридор — комната пройдена."""
    screens = [wd.RESULT, None, None, wd.BATTLE, wd.BATTLE, wd.RESULT, wd.RESULT, None] + [wd.HALLWAY] * 10
    play, done_at = run_manual(screens)
    assert done_at is not None
    assert play.room_cleared
    assert play.replayed


def test_manual_retreated_to_hallway():
    """«Ещё раз», пауза, «Отступить», закрыли выбор команды — комната не пройдена."""
    screens = [wd.RESULT, wd.BATTLE, wd.BATTLE, wd.TEAM, wd.TEAM, None] + [wd.HALLWAY] * 10
    play, done_at = run_manual(screens)
    assert done_at is not None
    assert not play.room_cleared


def test_manual_waits_while_user_plays():
    """Пока на экране бой, выбор команды или что-то непонятное (чат), бот не продолжает."""
    screens = [wd.BATTLE] * 100 + [None] * 100 + [wd.TEAM] * 100
    play, done_at = run_manual(screens)
    assert done_at is None


def test_manual_hallway_must_hold_2_seconds():
    """Коридор мелькнул на один снимок — ещё не повод продолжать."""
    screens = [wd.RESULT, wd.HALLWAY, wd.BATTLE, wd.HALLWAY, wd.HALLWAY, wd.HALLWAY, wd.HALLWAY, wd.HALLWAY]
    play, done_at = run_manual(screens)
    assert done_at == 7  # коридор с 3-го по 7-й снимок: 4 шага по 0,5 с = 2 с
    assert not play.room_cleared  # последним перед коридором был бой


def test_manual_no_valid_team_start():
    """Окно «Нет подходящего пака»: начинаем с выбора команды, вы собрали пак и победили."""
    screens = [wd.TEAM, wd.BATTLE, wd.RESULT] + [wd.HALLWAY] * 10
    play, done_at = run_manual(screens, first=wd.TEAM)
    assert done_at is not None
    assert play.room_cleared and play.replayed


def test_manual_no_valid_team_closed():
    play, done_at = run_manual([wd.TEAM] + [wd.HALLWAY] * 10, first=wd.TEAM)
    assert done_at is not None
    assert not play.room_cleared


# --- Падение с ошибкой Python ---

def test_crash_prints_error_and_summary(tmp_path):
    """Бот упал: в выводе есть ошибка и итог сессии с причиной (как в main.py: excepthook + atexit)."""
    script = tmp_path / "crash.py"
    script.write_text(
        "import sys, atexit\n"
        f"sys.path.insert(0, {ROOT!r})\n"
        "import session_log\n"
        f"session_log.install(base_dir={str(tmp_path / 'bot_data')!r})\n"
        "atexit.register(lambda: session_log.SESSION.print_summary(3, 18))\n"
        "print('[НАВИГАЦИЯ] Сканирую коридор...')\n"
        "raise RuntimeError('экран заблокирован')\n",
        encoding="utf-8",
    )
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, "-X", "utf8", str(script)], capture_output=True, text=True,
                         encoding="utf-8", env=env, cwd=tmp_path, timeout=60).stdout
    assert "[ОШИБКА] Бот остановился из-за ошибки:" in out
    assert "RuntimeError: экран заблокирован" in out
    assert "[ИТОГ] Причина остановки: Ошибка: RuntimeError: экран заблокирован" in out
    assert "Комнат: 3 | Титанит: 18" in out
    # Итог — после ошибки
    assert out.index("[ОШИБКА] Бот остановился") < out.index("[ИТОГ] Причина остановки")
