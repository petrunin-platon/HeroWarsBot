# Тесты задачи 4: надёжные нажатия без двойных кликов и промахов по двери.
# Игры и телефона нет, поэтому часы и экран подделываем: FakeTime двигает время только когда бот «спит».
import importlib
import sys
import types

import numpy as np
import pytest

sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

import click_logic  # noqa: E402
from click_logic import (  # noqa: E402
    DONE, RETRY, WAIT, RetryPolicy, StableTracker, TapWatch, after_failed_battle_start, door_click_point,
    door_click_zone,
)


class FakeTime:
    """Подмена модуля time: время идёт только в sleep()."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += seconds


class FakeProc:
    """Подмена процесса `adb shell input tap`: завершается через delay секунд после создания."""

    def __init__(self, clock, delay):
        self.clock = clock
        self.finish_at = clock.now + delay

    def poll(self):
        return 0 if self.clock.now >= self.finish_at else None


@pytest.fixture
def clock():
    return FakeTime()


# ---------------------------------------------------------------------------
# RetryPolicy: когда можно нажать кнопку ещё раз
# ---------------------------------------------------------------------------
def make_policy(clock, tap_delay=0.3, score=0.95, pos=(100, 100)):
    proc = FakeProc(clock, tap_delay)
    return RetryPolicy(TapWatch(proc, clock=clock.monotonic), score, pos, clock=clock.monotonic)


def test_policy_button_gone_is_done(clock):
    policy = make_policy(clock)
    assert policy.observe(False) == DONE


def test_policy_waits_while_tap_command_is_running(clock):
    """Медленный adb: команда ещё выполняется — повторять нельзя, сколько бы времени ни прошло с её запуска."""
    policy = make_policy(clock, tap_delay=3.0)
    clock.now += 2.9
    assert policy.observe(True, 0.95, (100, 100)) == WAIT


def test_policy_retry_only_after_pause_from_tap_done(clock):
    policy = make_policy(clock, tap_delay=1.0)
    clock.now += 1.0  # команда дошла до телефона
    assert policy.observe(True, 0.95, (100, 100)) == WAIT
    clock.now += click_logic.RETRY_AFTER_S - 0.1
    assert policy.observe(True, 0.95, (100, 100)) == WAIT
    clock.now += 0.2
    assert policy.observe(True, 0.95, (100, 100)) == RETRY


def test_policy_window_closing_delays_retry(clock):
    """Совпадение с кнопкой упало — окно закрывается. Повтор откладывается..."""
    policy = make_policy(clock, tap_delay=0.2)
    clock.now += 1.0
    assert policy.observe(True, 0.70, (100, 100)) == WAIT
    clock.now += 0.6  # прошло 1.6 с после нажатия, без закрытия уже был бы повтор
    assert policy.observe(True, 0.70, (100, 100)) == WAIT


def test_policy_closing_delay_is_limited(clock):
    """...но не бесконечно: если окно «закрывается» дольше 2 × RETRY_AFTER_S, жмём снова."""
    policy = make_policy(clock, tap_delay=0.2)
    done = clock.now + 0.2
    verdict = WAIT
    while clock.now < done + 2 * click_logic.RETRY_AFTER_S + 0.5:
        clock.now += 0.1
        verdict = policy.observe(True, 0.60, (100, 100))
        if verdict == RETRY:
            break
    assert verdict == RETRY
    assert clock.now - done <= 2 * click_logic.RETRY_AFTER_S + 0.15


def test_policy_button_moved_counts_as_reaction(clock):
    policy = make_policy(clock, tap_delay=0.2)
    clock.now += 1.7
    assert policy.observe(True, 0.95, (100 + click_logic.REACT_MOVE_PX, 100)) == WAIT


def test_tap_watch_hard_limit(clock):
    """Если adb завис, через TAP_HARD_LIMIT_S считаем нажатие выполненным."""
    watch = TapWatch(FakeProc(clock, 999), clock=clock.monotonic)
    assert watch.done_time() is None
    clock.now += click_logic.TAP_HARD_LIMIT_S
    assert watch.done_time() is not None


def test_tap_watch_without_process_is_done_at_once(clock):
    assert TapWatch(None, clock=clock.monotonic).done_time() is not None


# ---------------------------------------------------------------------------
# find_and_click_bulletproof на подделке экрана
# ---------------------------------------------------------------------------
@pytest.fixture
def vision(clock, monkeypatch):
    module = importlib.import_module("vision")
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module, "click_point_from_info", lambda name, info, rect: (50, 50))
    # run_button подменяет их прямо в модуле: после теста вернуть настоящие (их проверяет tests/test_waits.py)
    monkeypatch.setattr(module, "click_human", module.click_human)
    monkeypatch.setattr(module, "get_match_info", module.get_match_info)
    module.taps = []
    return module


def run_button(vision, clock, visible, tap_delay=0.3, timeout=6.0, score=lambda t: 0.95):
    """visible(t) — видна ли кнопка через t секунд после первого нажатия (до него видна всегда)."""
    state = {"first_tap": None}
    taps = []

    def fake_info(name, rect, sct, threshold):
        if state["first_tap"] is None:
            return {"x": 100, "y": 100, "w": 40, "h": 20, "score": 0.95, "ox": 0, "oy": 0}
        since = clock.now - state["first_tap"]
        if visible(since, len(taps)):
            return {"x": 100, "y": 100, "w": 40, "h": 20, "score": score(since), "ox": 0, "oy": 0}
        return None

    def fake_click(x, y, **kwargs):
        if state["first_tap"] is None:
            state["first_tap"] = clock.now
        taps.append(clock.now - state["first_tap"])
        clock.sleep(0.15)  # как настоящий click_human: пауза после нажатия
        return FakeProc(clock, tap_delay)

    vision.get_match_info = fake_info
    vision.click_human = fake_click
    result = vision.find_and_click_bulletproof("btn_ok.png", {}, None, 0.8, timeout=timeout)
    return result, taps


def test_normal_click_taps_once(vision, clock):
    """Окно закрылось через 0,6 с после нажатия — второго нажатия быть не должно (раньше было)."""
    result, taps = run_button(vision, clock, lambda since, n: since < 0.6)
    assert result is True
    assert len(taps) == 1


def test_slow_adb_does_not_cause_second_tap(vision, clock):
    """Команда нажатия выполнялась 1,2 с, окно закрылось через 1,4 с. Раньше бот жал повторно уже на 0,5–0,8 с."""
    result, taps = run_button(vision, clock, lambda since, n: since < 1.4, tap_delay=1.2)
    assert result is True
    assert len(taps) == 1


def test_closing_window_is_not_tapped_again(vision, clock):
    """Кнопка бледнеет (окно закрывается) и пропадает через 2,2 с — повторного нажатия нет."""
    result, taps = run_button(
        vision, clock,
        visible=lambda since, n: since < 2.2,
        score=lambda since: 0.95 if since < 0.6 else 0.70,
        tap_delay=0.2,
    )
    assert result is True
    assert len(taps) == 1


def test_lost_tap_is_repeated_once_after_pause(vision, clock):
    """Первое нажатие потерялось: повтор через RETRY_AFTER_S после первого, не раньше."""
    result, taps = run_button(vision, clock, lambda since, n: n < 2, tap_delay=0.3)
    assert result is True
    assert len(taps) == 2
    assert taps[1] - taps[0] >= click_logic.RETRY_AFTER_S + 0.3


def test_button_flicker_is_not_success(vision, clock):
    """Задача 11: снимки частые и ловят мгновенное «мигание» кнопки при нажатии. Кнопка пропала на один снимок
    и снова видна — это не закрытие окна. Успех — когда её нет и на снимке через GONE_CONFIRM_S."""
    start = clock.now
    result, taps = run_button(vision, clock, lambda since, n: not (0.3 <= since < 0.4) and since < 2.0)
    assert result is True and len(taps) == 1
    assert clock.now - start >= 2.0 + click_logic.GONE_CONFIRM_S - 0.1


def test_button_that_never_reacts_gives_up(vision, clock):
    result, taps = run_button(vision, clock, lambda since, n: True, timeout=3.0)
    assert result is False
    assert len(taps) <= 3


def test_no_button_no_taps(vision, clock):
    vision.get_match_info = lambda *a, **k: None
    vision.click_human = lambda *a, **k: pytest.fail("нажатия быть не должно")
    assert vision.find_and_click_bulletproof("btn_ok.png", {}, None, 0.8, timeout=1.0) is False


# ---------------------------------------------------------------------------
# Дверь: флажок должен стоять на месте
# ---------------------------------------------------------------------------
def test_door_not_pressed_while_flag_moves(clock):
    tracker = StableTracker(clock=clock.monotonic, tol=3)
    for step in range(10):  # камера едет: флажок смещается на 10 пикселей за снимок
        assert tracker.update((400 - 10 * step, 200)) is False
        clock.now += 0.1


def test_door_pressed_when_flag_stands_still(clock):
    tracker = StableTracker(clock=clock.monotonic, tol=3)
    results = []
    for x in (400, 380, 360, 350, 350, 351, 349):
        results.append(tracker.update((x, 200)))
        clock.now += 0.1
    assert results[:5] == [False, False, False, False, False]  # на 350 только второй снимок
    assert results[5] is True  # 350, 350, 351 подряд, прошло ≥ 0,2 с
    assert tracker.gave_up is False


def test_door_stable_needs_min_span(clock):
    """Три снимка за долю секунды — ещё не «стоит»."""
    tracker = StableTracker(clock=clock.monotonic, tol=3)
    assert [tracker.update((100, 100)) for _ in range(3)] == [False, False, False]
    clock.now += 0.25
    assert tracker.update((100, 100)) is True


def test_door_flag_lost_resets_streak(clock):
    tracker = StableTracker(clock=clock.monotonic, tol=3)
    tracker.update((100, 100))
    clock.now += 0.1
    tracker.update((100, 100))
    tracker.reset()
    clock.now += 0.1
    assert tracker.update((100, 100)) is False


def test_door_gives_up_if_flag_never_settles(clock):
    """Флажок дрожит и не встаёт — через DOOR_STABLE_GIVE_UP_S жмём как есть, чтобы не зависнуть."""
    tracker = StableTracker(clock=clock.monotonic, tol=3)
    pressed = False
    for step in range(100):
        if tracker.update((100 + 10 * (step % 2), 100)):
            pressed = True
            break
        clock.now += 0.1
    assert pressed and tracker.gave_up
    assert 2.9 <= step * 0.1 <= 3.2


def test_door_click_point_is_in_central_part():
    scale = 0.978
    x1, y1, x2, y2 = door_click_zone(500, 100, 60, 40, scale)
    full_w, full_h = int(165 * scale), int(245 * scale)
    assert x2 - x1 <= full_w * 0.55 and y2 - y1 <= full_h * 0.55
    assert (x1 + x2) // 2 == 500 + 60 // 2 or abs((x1 + x2) / 2 - 530) <= 1
    assert y1 > 140  # ниже флажка
    for _ in range(300):
        px, py = door_click_point(500, 100, 60, 40, scale)
        assert x1 <= px <= x2 and y1 <= py <= y2


# ---------------------------------------------------------------------------
# navigation.py: дверь и переход на этаж на подделке экрана
# ---------------------------------------------------------------------------
def look_on_frame(module):
    """С задачи 11 коридор делает один снимок на шаг и ищет на нём (find_on_frame). В тестах ответы берутся
    из подделок get_match_info (флажок) и get_match_loc (кнопки), как раньше."""
    def look(frame, name, threshold, area=None):
        if name == "flag_enter.png":
            return module.get_match_info(name, {}, None, threshold)
        loc = module.get_match_loc(name, {}, None, threshold)
        return None if loc is None else {"x": loc[0], "y": loc[1], "w": 10, "h": 10, "score": 0.9, "ox": 0, "oy": 0}
    return look


@pytest.fixture
def navigation(clock, vision, monkeypatch):
    module = importlib.import_module("navigation")
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module, "click_point_from_info", lambda name, info, rect: (info["x"], info["y"]))
    monkeypatch.setattr(module, "game_frame", lambda *a, **k: None)
    monkeypatch.setattr(module, "find_on_frame", look_on_frame(module))
    module.misses = []
    monkeypatch.setattr(module.session_log, "count", lambda name: module.misses.append(name))
    return module


def flag_info(x):
    return {"x": x, "y": 200, "w": 60, "h": 40, "score": 0.9, "ox": 0, "oy": 0}


def test_hallway_waits_until_door_stops_then_taps_once(navigation, clock, monkeypatch):
    """Камера едет 0,5 с, потом дверь стоит. Нажатие — только после остановки, и ровно одно."""
    start = clock.now
    taps = []

    def fake_info(name, rect, sct, threshold):
        since = clock.now - start
        x = 600 - int(since * 100) if since < 0.5 else 550
        return flag_info(x)

    monkeypatch.setattr(navigation, "get_match_loc", lambda *a, **k: None)
    monkeypatch.setattr(navigation, "get_match_info", fake_info)
    monkeypatch.setattr(navigation, "click_human", lambda x, y, **k: taps.append(clock.now - start) or "proc")
    monkeypatch.setattr(navigation, "wait_after_tap", lambda *a, **k: (100, 100))

    assert navigation.smart_navigate_hallway({}, None) == "ROOM_SELECTION"
    assert len(taps) == 1
    assert taps[0] >= 0.5 + 0.2  # после остановки не меньше DOOR_STABLE_MIN_SPAN_S
    assert navigation.misses == []


def test_hallway_door_miss_returns_at_once(navigation, clock, monkeypatch):
    """Окно атаки не открылось: считаем промах и сразу возвращаемся смотреть флажок (без паузы 4 с)."""
    monkeypatch.setattr(navigation, "get_match_loc", lambda *a, **k: None)
    monkeypatch.setattr(navigation, "get_match_info", lambda *a, **k: flag_info(550))
    monkeypatch.setattr(navigation, "click_human", lambda x, y, **k: "proc")
    monkeypatch.setattr(navigation, "wait_after_tap", lambda *a, **k: None)
    start = clock.now

    assert navigation.smart_navigate_hallway({}, None) == "HALLWAY"
    assert navigation.misses == ["door_misses"]
    assert clock.now - start < 1.0


def test_wait_after_tap_counts_from_tap_done(vision, clock, monkeypatch):
    """Медленный adb (1 с). Окно открылось на 2,5 с — это успех; промах считаем только через DOOR_REACT_S после нажатия."""
    start = clock.now
    info = {"x": 10, "y": 10, "w": 40, "h": 20, "score": 0.9, "ox": 5, "oy": 3}
    monkeypatch.setattr(vision, "get_match_info", lambda *a, **k: info if clock.now - start >= 2.5 else None)
    proc = FakeProc(clock, 1.0)
    seen_at, center = vision.wait_after_tap("btn_attack.png", {}, None, proc, 0.68, react_s=2.0)
    assert center == (5 + 10 + 20, 3 + 10 + 10)  # центр кнопки в координатах окна (для find_smart_door)
    assert 2.5 <= seen_at - start <= 2.6

    start = clock.now
    proc = FakeProc(clock, 1.0)
    monkeypatch.setattr(vision, "get_match_info", lambda *a, **k: None)
    assert vision.wait_after_tap("btn_attack.png", {}, None, proc, 0.68, react_s=2.0) is None
    assert 2.9 <= clock.now - start <= 3.3  # 1 с команда + 2 с ожидания


def test_checkpoint_pressed_once_then_waits_for_new_floor(navigation, clock, monkeypatch):
    """Точка сохранения: «Активировать» один раз, потом награда и ожидание нового этажа вместо паузы 4 с.
    Задача 11: пауза реакции перед «Забрать» — от того, как окно награды появилось (без повторных поисков)."""
    clicks, calls = [], []
    monkeypatch.setattr(navigation, "get_match_info", lambda *a, **k: None)
    monkeypatch.setattr(navigation, "get_match_loc",
                        lambda name, *a, **k: (300, 300) if name == "btn_activate.png" else None)
    monkeypatch.setattr(navigation, "click_human", lambda x, y, **k: clicks.append((x, y)) or "proc")
    claim_seen = clock.now + 1.5
    waited = []
    monkeypatch.setattr(navigation, "wait_after_tap",
                        lambda name, rect, sct, tap, thr, **k: waited.append((name, tap)) or (claim_seen, (400, 400)))
    monkeypatch.setattr(navigation, "find_and_click_bulletproof",
                        lambda name, *a, seen_at=None, **k: calls.append((name, seen_at)) or True)
    monkeypatch.setattr(navigation, "wait_for_new_floor", lambda *a, **k: calls.append("floor"))

    assert navigation.smart_navigate_hallway({}, None) == "HALLWAY"
    assert clicks == [(300, 300)]
    assert waited == [("btn_claim.png", "proc")]  # окно награды ждём после того, как нажатие дошло
    assert calls == [("btn_claim.png", claim_seen), "floor"]


def test_new_floor_waits_for_door_flag_not_fixed_pause(navigation, clock, monkeypatch):
    """Сессия 04: спуск на этаж идёт ~8–10 с. Бот ждёт появления флажка, а не фиксированные 4 с,
    и не дольше FLOOR_FLAG_WAIT_S."""
    start = clock.now
    monkeypatch.setattr(navigation, "get_match_info",
                        lambda *a, **k: flag_info(500) if clock.now - start >= 8.0 else None)
    navigation.wait_for_new_floor({}, None)
    assert 8.0 <= clock.now - start <= 8.3


def test_new_floor_gives_up_after_limit(navigation, clock, monkeypatch):
    start = clock.now
    monkeypatch.setattr(navigation, "get_match_info", lambda *a, **k: None)
    navigation.wait_for_new_floor({}, None)
    assert click_logic.FLOOR_FLAG_WAIT_S <= clock.now - start <= click_logic.FLOOR_FLAG_WAIT_S + 0.3


def test_hallway_timeout_on_team_screen_returns_to_set_team(navigation, clock, monkeypatch):
    """Сессия 04, 03:02:08: «Авто» не сработала, на экране выбор команды, а бот в состоянии HALLWAY.
    Раньше он бесконечно искал дверь. Теперь после таймаута возвращается к выбору команды."""
    monkeypatch.setattr(navigation, "get_match_info", lambda *a, **k: None)
    monkeypatch.setattr(navigation, "get_match_loc",
                        lambda name, *a, **k: (500, 500) if name == "btn_auto.png" else None)
    assert navigation.smart_navigate_hallway({}, None) == "SET_TEAM"


def test_hallway_timeout_on_unknown_screen_stays_in_hallway(navigation, clock, monkeypatch):
    monkeypatch.setattr(navigation, "get_match_info", lambda *a, **k: None)
    monkeypatch.setattr(navigation, "get_match_loc", lambda *a, **k: None)
    assert navigation.smart_navigate_hallway({}, None) == "HALLWAY"


# ---------------------------------------------------------------------------
# Начало боя: потерянное нажатие «Авто»
# ---------------------------------------------------------------------------
def test_failed_start_on_team_screen_tries_again():
    assert after_failed_battle_start(True, 0) == ("SET_TEAM", 1)
    assert after_failed_battle_start(True, 1) == ("SET_TEAM", 2)


def test_failed_start_stops_after_limit():
    state, attempts = after_failed_battle_start(True, click_logic.START_BATTLE_ATTEMPTS - 1)
    assert state == "STOP" and attempts == click_logic.START_BATTLE_ATTEMPTS


def test_failed_start_on_other_screen_goes_to_hallway_and_resets_counter():
    assert after_failed_battle_start(False, 2) == ("HALLWAY", 0)


def test_lost_auto_tap_is_repeated_by_bulletproof(vision, clock):
    """Сессия 04: нажатие «Авто» потерялось. С проверкой бот жмёт ещё раз и бой начинается."""
    result, taps = run_button(vision, clock, lambda since, n: n < 2, tap_delay=0.3)
    assert result is True
    assert len(taps) == 2


def test_retry_message_shows_tap_duration_and_reaction(vision, clock, capsys):
    """Диагностика для следующей сессии: сколько выполнялось нажатие и через сколько после повтора кнопка пропала."""
    run_button(vision, clock, lambda since, n: n < 2, tap_delay=1.1)
    out = capsys.readouterr().out
    assert "нажатие выполнялось 1.1 с" in out
    assert "после повтора кнопка пропала через" in out


def test_tap_watch_duration(clock):
    watch = TapWatch(FakeProc(clock, 1.1), clock=clock.monotonic)
    assert watch.duration() is None
    clock.now += 1.2
    assert watch.duration() == pytest.approx(1.2)


# ---------------------------------------------------------------------------
# combat.py: одно нажатие «Атаковать»
# ---------------------------------------------------------------------------
@pytest.fixture
def combat(clock, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("combat", "rules_engine", "analyzer"):
        sys.modules.pop(name, None)
    module = importlib.import_module("combat")
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module.engine, "is_room_forbidden", lambda *a, **k: False)
    monkeypatch.setattr(module, "scan_enemy_team", lambda *a, **k: ["sigurd"])
    yield module
    for name in ("combat", "rules_engine", "analyzer"):
        sys.modules.pop(name, None)


class FakeScreen:
    """Подделка mss: кадр с одной шаблонной «кнопкой», пока visible(t) истинно."""

    def __init__(self, clock, template, visible):
        self.clock, self.template, self.visible = clock, template, visible

    def grab(self, rect):
        frame = np.zeros((200, 300, 4), dtype=np.uint8)
        if self.visible(self.clock.now):
            h, w = self.template.shape[:2]
            frame[60:60 + h, 100:100 + w, :3] = self.template
        return frame


def run_attack(combat, clock, visible_after_first_tap, tap_delay=0.3):
    rng = np.random.default_rng(5)
    template = rng.integers(30, 255, (20, 40, 3), dtype=np.uint8)
    state = {"first": None}
    taps = []

    def visible(now):
        if state["first"] is None:
            return True
        return visible_after_first_tap(now - state["first"], len(taps))

    def fake_click(x, y, **kwargs):
        if state["first"] is None:
            state["first"] = clock.now
        taps.append(clock.now - state["first"])
        clock.sleep(0.15)
        return FakeProc(clock, tap_delay)

    combat.imread_cyrillic = lambda name: template
    combat.click_human = fake_click
    combat.get_match_loc = lambda *a, **k: None
    room, enemies = combat.find_smart_door({"top": 0, "left": 0, "width": 300, "height": 200}, FakeScreen(clock, template, visible), {})
    return room, enemies, taps


def test_attack_pressed_once(combat, clock):
    """Раньше бот жал «Атаковать» каждые ~0,3 с, пока кнопка не исчезнет."""
    room, enemies, taps = run_attack(combat, clock, lambda since, n: since < 0.8)
    assert room is not None and enemies == ["sigurd"]
    assert len(taps) == 1


def test_attack_lost_tap_repeated_once(combat, clock):
    room, enemies, taps = run_attack(combat, clock, lambda since, n: n < 2)
    assert room is not None
    assert len(taps) == 2
    assert taps[1] - taps[0] >= click_logic.RETRY_AFTER_S


def test_hallway_timeout_on_result_window_goes_to_wait_for_ok(navigation, clock, monkeypatch):
    """Сессия 06, 18:01:55: бой закончился позже, чем бот его ждал, и окно «ПОБЕДА» стояло на экране,
    а бот в коридоре бесконечно искал дверь. Теперь он переходит к обработке результата."""
    monkeypatch.setattr(navigation, "get_match_info", lambda *a, **k: None)
    monkeypatch.setattr(navigation, "get_match_loc",
                        lambda name, *a, **k: (500, 500) if name == "btn_ok.png" else None)
    assert navigation.smart_navigate_hallway({}, None) == "WAIT_FOR_OK"
