# Тесты задачи 10: вместо фиксированных пауз — «экран замер», и одна пауза реакции перед нажатием.
# Игры и телефона нет: часы подделываем (время идёт только в sleep), экран — последовательности снимков.
# Окно результата проверяем на настоящих скриншотах пользователя (logs/session_01-02/screens/54.png и 111.png).
import importlib
import os
import random
import sys
import types

import pytest

sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import click_logic  # noqa: E402
import result_scan as rs  # noqa: E402
from click_logic import TapPacer, spots_still, wait_until_still  # noqa: E402
from test_click_logic import FakeProc, FakeTime, look_on_frame  # noqa: E402

PACK = ["araji", "hyperion", "rigel", "iyari", "lumira"]
SCREENS = os.path.join(os.path.dirname(__file__), "..", "logs", "session_01-02", "screens")
GAME_RECT = {"top": 0, "left": 0, "width": 1590, "height": 704}


@pytest.fixture
def clock():
    return FakeTime()


class FixedRng:
    """Вместо random: uniform всегда отдаёт заданное число."""

    def __init__(self, value):
        self.value = value

    def uniform(self, a, b):
        return self.value


# ---------------------------------------------------------------------------
# Пауза реакции и не больше 2 нажатий в секунду (вопрос 13)
# ---------------------------------------------------------------------------
def test_reaction_counts_from_button_appearing(clock):
    """Кнопка только что появилась — ждём 0,3–0,8 с. Бот после её появления думал дольше — не ждём совсем."""
    pacer = TapPacer(clock=clock.monotonic)
    for _ in range(50):
        assert 0.3 <= pacer.wait_before(seen_at=clock.now) <= 0.8
    assert pacer.wait_before(seen_at=clock.now - 2.5) == 0  # «ОК» видна 2,5 с: бот читал ХП


def test_reaction_partly_passed(clock):
    pacer = TapPacer(clock=clock.monotonic, rng=FixedRng(0.8))
    assert pacer.wait_before(seen_at=clock.now - 0.5) == pytest.approx(0.3)
    assert pacer.wait_before(seen_at=None) == pytest.approx(0.8)  # None — кнопку только что нашли


def test_not_more_than_two_taps_per_second(clock):
    """Серия нажатий (сборка состава): между нажатиями не меньше 0,5 с, даже если кнопки видны давно."""
    pacer = TapPacer(clock=clock.monotonic, rng=random.Random(1))
    seen = clock.now - 10
    taps = []
    for _ in range(6):
        clock.sleep(pacer.wait_before(seen))
        taps.append(clock.now)
        pacer.tapped()
        clock.sleep(0.05)  # бот что-то делает между нажатиями
    gaps = [b - a for a, b in zip(taps, taps[1:])]
    assert min(gaps) >= click_logic.MIN_TAP_INTERVAL_S - 1e-9
    assert taps[0] == pytest.approx(seen + 10)  # первое нажатие без ожидания: кнопка видна давно


# ---------------------------------------------------------------------------
# «Экран замер» на последовательности снимков
# ---------------------------------------------------------------------------
def frames(clock, values, read_s=0.0):
    """read() отдаёт снимки по очереди (последний повторяется); каждый снимок делается read_s секунд."""
    seq = list(values)
    times = []

    def read():
        times.append(clock.now)
        clock.sleep(read_s)
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return read, times


def test_still_screen_needs_two_same_shots(clock):
    """Полоска ХП «доезжает»: 70 → 60 → 56 → 56. Берём 56, когда два снимка подряд одинаковые."""
    read, times = frames(clock, [70, 60, 56, 56, 56])
    value, still, shots = wait_until_still(read, lambda a, b: a == b, clock=clock.monotonic, sleep=clock.sleep)
    assert (value, still, shots) == (56, True, 4)
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert min(gaps) >= click_logic.STILL_INTERVAL_S - 1e-9


def test_already_still_costs_one_extra_shot(clock):
    """Первый снимок уже есть (окно результата прочитано) и экран не меняется: нужен всего один снимок."""
    read, _ = frames(clock, [56])
    start = clock.now
    value, still, shots = wait_until_still(read, lambda a, b: a == b, first=(clock.now - 2.6, 56),
                                           clock=clock.monotonic, sleep=clock.sleep)
    assert (value, still, shots) == (56, True, 1)
    assert clock.now - start == pytest.approx(0)  # первый снимок сделан давно — не ждём


def test_slow_pc_does_not_wait_extra(clock):
    """Слабый ПК: снимок делается 0,5 с (дольше интервала) — между снимками бот не спит."""
    read, times = frames(clock, [70, 56, 56], read_s=0.5)
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        clock.sleep(s)

    value, still, _ = wait_until_still(read, lambda a, b: a == b, clock=clock.monotonic, sleep=sleep)
    assert (value, still) == (56, True)
    assert sleeps == []


def test_never_still_gives_up_with_last_shot(clock):
    read, _ = frames(clock, list(range(100, 0, -1)))
    start = clock.now
    value, still, _ = wait_until_still(read, lambda a, b: a == b, clock=clock.monotonic, sleep=clock.sleep)
    assert not still
    assert click_logic.STILL_TIMEOUT_S <= clock.now - start <= click_logic.STILL_TIMEOUT_S + 0.4
    assert value < 100


def test_spots_still():
    assert spots_still([(100, 50)], [(101, 49), (300, 50)], tol=3)  # кнопка на месте, рядом другая дверь
    assert not spots_still([(100, 50)], [(110, 50)], tol=3)          # окно ещё едет
    assert not spots_still([(100, 50)], [], tol=3)                    # кнопки пропали


# ---------------------------------------------------------------------------
# Окно результата: вместо паузы 1,5 с — полоски ХП замерли (настоящие скриншоты)
# ---------------------------------------------------------------------------
class SeqSct:
    """Вместо mss: снимки по очереди (последний повторяется)."""

    def __init__(self, images):
        self.images = list(images)
        self.grabs = 0

    def grab(self, rect):
        self.grabs += 1
        img = self.images.pop(0) if len(self.images) > 1 else self.images[0]
        return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)


@pytest.fixture
def analyzer(monkeypatch):
    import vision
    import analyzer as an
    monkeypatch.setitem(vision.GEOMETRY_CACHE, "is_calibrated", True)
    for key, value in {"offset_x": 0, "offset_y": 0, "game_w": 1590, "game_h": 704, "scale": 704 / 720}.items():
        monkeypatch.setitem(vision.GEOMETRY_CACHE, key, value)
    vision.get_scaled_template.cache_clear()
    yield an
    vision.get_scaled_template.cache_clear()


def game_area(name):
    img = cv2.imread(os.path.join(SCREENS, name))
    assert img is not None
    return img[78:78 + 704, 58:58 + 1590].copy()


def shifted(img, dx, dy):
    """Окно результата чуть сдвинуто (ещё выезжает)."""
    out = np.zeros_like(img)
    out[dy:, dx:] = img[:img.shape[0] - dy, :img.shape[1] - dx]
    return out


def bar_cut(img, found, titan, keep):
    """Полоска ХП титана «не доехала»: зелёная часть правее keep пикселей от начала полоски закрашена тёмным."""
    x, y, w, h = found[titan]
    out = img.copy()
    box = out[y + int(h * 1.6):y + int(h * 1.6) + int(h * 0.7), max(0, x - 30):x + w + 30]
    hsv = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([45, 100, 100]), np.array([75, 255, 255])) > 0
    cols = np.where(green.any(axis=0))[0]
    green[:, :cols[0] + keep] = False
    box[green] = (20, 20, 20)
    return out


@pytest.mark.parametrize("name", ["54.png", "111.png"])
def test_reread_gives_same_numbers_as_full_scan(analyzer, name):
    img = game_area(name)
    found = {}
    status = analyzer.scan_team_health(GAME_RECT, SeqSct([img]), PACK, found=found)
    assert sorted(found) == sorted(PACK)
    again = analyzer.reread_team_health(GAME_RECT, SeqSct([img]), found)
    assert rs.same_status(status, again, PACK)


def test_reread_follows_window_that_moved(analyzer):
    """Окно сдвинулось на несколько пикселей: иконки ищутся рядом с прежним местом и находятся."""
    img = game_area("111.png")
    found = {}
    status = analyzer.scan_team_health(GAME_RECT, SeqSct([img]), PACK, found=found)
    before = dict(found)
    again = analyzer.reread_team_health(GAME_RECT, SeqSct([shifted(img, 7, 5)]), found)
    assert rs.same_status(status, again, PACK)
    assert all(found[t] == (before[t][0] + 7, before[t][1] + 5) + before[t][2:] for t in PACK)


def test_result_window_bars_moving_then_still(analyzer, clock, capsys):
    """Последовательность снимков окна результата: полоска Ригеля сначала «не доехала» (ХП меньше),
    потом встала на 55%. Бот берёт 55%, остальных — как в первом чтении, и пишет об этом в лог."""
    img = game_area("54.png")
    found = {}
    analyzer.scan_team_health(GAME_RECT, SeqSct([img]), PACK, found=found)
    moving = bar_cut(img, found, "rigel", keep=20)
    sct = SeqSct([moving, img, img])

    first = analyzer.scan_team_health(GAME_RECT, sct, PACK, found=found)
    assert first["rigel"]["hp"] < 40  # снимок, где полоска ещё двигалась
    final = rs.wait_bars_still(first, PACK, lambda: analyzer.reread_team_health(GAME_RECT, sct, found), clock.now,
                               clock=clock.monotonic, sleep=clock.sleep)
    assert abs(final["rigel"]["hp"] - 55) <= 2
    assert final["araji"] is first["araji"]
    out = capsys.readouterr().out
    assert "RIGEL: ХП" in out and "полоски ещё двигались" in out
    assert "Полоски ХП замерли после 3 снимков" in out


def test_result_window_still_at_once_is_quick(analyzer, clock, capsys):
    """Обычный случай: окно уже не двигается. Один быстрый снимок вместо паузы 1,5 с."""
    img = game_area("111.png")
    found = {}
    sct = SeqSct([img])
    first = analyzer.scan_team_health(GAME_RECT, sct, PACK, found=found)
    scanned_at = clock.now
    clock.sleep(2.5)  # на слабом ПК чтение окна (5 титанов) идёт ~2,5 с
    final = rs.wait_bars_still(first, PACK, lambda: analyzer.reread_team_health(GAME_RECT, sct, found), scanned_at,
                               clock=clock.monotonic, sleep=clock.sleep)
    assert final == first
    assert sct.grabs == 2
    assert clock.now - scanned_at == pytest.approx(2.5)  # ни одной лишней паузы
    assert "второй снимок такой же" in capsys.readouterr().out


def test_result_window_read_after_animation(clock):
    """Задача 11 (ваш совет): окно появилось, когда видна «ОК»; читать титанов — через 1,2 с.
    Если бот увидел «ОК» давно (например, долго искал), не ждёт."""
    seen = clock.now
    assert rs.wait_window_settled(seen, clock=clock.monotonic, sleep=clock.sleep) == pytest.approx(1.2)
    assert clock.now == pytest.approx(seen + rs.RESULT_ANIMATION_S)
    assert rs.wait_window_settled(clock.now - 2.0, clock=clock.monotonic, sleep=clock.sleep) == 0
    assert clock.now == pytest.approx(seen + rs.RESULT_ANIMATION_S)


def test_video_jitter_is_not_movement():
    """Видео scrcpy «дрожит»: край полоски сдвигается на 1–2 пикселя (до 3%). Это не движение полоски."""
    a = {"rigel": {"hp": 55, "energy": 15, "status": "ЖИВ"}}
    assert rs.same_status(a, {"rigel": {"hp": 57, "energy": 12, "status": "ЖИВ"}}, ["rigel"])
    assert not rs.same_status(a, {"rigel": {"hp": 60, "energy": 15, "status": "ЖИВ"}}, ["rigel"])
    assert not rs.same_status(a, {"rigel": {"hp": 0, "energy": 0, "status": "МЕРТВ"}}, ["rigel"])


def test_bars_wait_keeps_titans_that_were_not_found_again(clock):
    """Перечитывание не нашло иконку (перекрыта) — значение титана остаётся прежним, бой не становится «нечитаемым»."""
    first = {t: {"hp": 80, "energy": 50, "status": "ЖИВ", "score": 0.8} for t in PACK}
    final = rs.wait_bars_still(first, PACK, lambda: {}, clock.now, clock=clock.monotonic, sleep=clock.sleep,
                               log=lambda *_: None)
    assert final == first


# ---------------------------------------------------------------------------
# Окно выбора комнат: вместо пауз 0,2 + 0,2 с — кнопки «Атаковать» стоят на месте
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


class SlidingScreen:
    """Окно с кнопкой «Атаковать»: она едет слева (x = 40 → 100) slide_s секунд, потом стоит.
    После нажатия (tapped) кнопка пропадает через 0,5 с."""

    def __init__(self, clock, template, slide_s):
        self.clock, self.template, self.slide_s = clock, template, slide_s
        self.start = clock.now
        self.tapped = None
        self.grabs = []

    def x(self):
        since = self.clock.now - self.start
        return 100 if since >= self.slide_s else 40 + int(60 * since / self.slide_s)

    def grab(self, rect):
        self.grabs.append((self.clock.now, self.x()))
        frame = np.zeros((200, 300, 4), dtype=np.uint8)
        if self.tapped is None or self.clock.now - self.tapped < 0.5:
            h, w = self.template.shape[:2]
            frame[60:60 + h, self.x():self.x() + w, :3] = self.template
        return frame


def run_door(combat, clock, slide_s, opened=None):
    rng = np.random.default_rng(5)
    template = rng.integers(30, 255, (20, 40, 3), dtype=np.uint8)
    screen = SlidingScreen(clock, template, slide_s)
    taps = []

    def fake_click(x, y, seen_at=None, **kwargs):
        taps.append((x, y, seen_at))
        screen.tapped = clock.now
        screen.shots_before_tap = len(screen.grabs)
        return FakeProc(clock, 0.2)

    combat.imread_cyrillic = lambda name: template
    combat.click_human = fake_click
    room, _ = combat.find_smart_door({"top": 0, "left": 0, "width": 300, "height": 200}, screen, {},
                                     opened=opened(screen) if opened else None)
    return room, screen, taps


def test_room_window_sliding_waits_until_buttons_stop(combat, clock):
    room, screen, taps = run_door(combat, clock, slide_s=0.9)
    assert room is not None
    assert len(taps) == 1
    assert taps[0][0] == 100 + 20  # нажатие по кнопке, которая уже встала на место (центр 100 + 40 / 2)
    # разбор дверей — по снимку, где кнопка уже стояла, и не раньше, чем окно замерло
    stopped = [t for t, x in screen.grabs if x == 100]
    assert stopped and stopped[0] >= screen.start + 0.9


def test_room_window_seen_after_door_tap_needs_one_shot(combat, clock):
    """Навигация уже видела окно после нажатия на дверь: если кнопка на том же месте, хватает одного снимка
    (раньше: пауза 0,2 с, ещё снимок, ещё 0,2 с, и только потом разбор дверей)."""
    def opened(screen):
        return clock.now - 0.4, (100 + 20, 60 + 10)  # центр кнопки «Атаковать» в координатах окна

    room, screen, taps = run_door(combat, clock, slide_s=0.0, opened=opened)
    assert room is not None
    # один снимок — убедиться, что окно замерло; по нему же и первое нажатие «Атаковать» (задача 11)
    assert screen.shots_before_tap == 1
    assert taps[0][2] == pytest.approx(screen.start - 0.4)  # пауза реакции — от момента, когда окно увидели


def test_room_window_fading_in_is_waited_for(combat, clock):
    """Окно выбора комнат ещё проявляется: первые 0,5 с кнопки «Атаковать» не узнаются. Раньше бот сразу
    уходил в коридор («Двери не найдены»), теперь ждёт их (не дольше 2 с)."""
    rng = np.random.default_rng(5)
    template = rng.integers(30, 255, (20, 40, 3), dtype=np.uint8)
    start = clock.now

    class Fading(SlidingScreen):
        def grab(self, rect):
            frame = super().grab(rect)
            if self.clock.now - start < 0.5:
                frame[:] = 0
            return frame

    screen = Fading(clock, template, 0.0)
    combat.imread_cyrillic = lambda name: template
    combat.click_human = lambda x, y, **k: setattr(screen, "tapped", clock.now) or FakeProc(clock, 0.2)
    room, _ = combat.find_smart_door({"top": 0, "left": 0, "width": 300, "height": 200}, screen, {},
                                     opened=(start, (120, 70)))
    assert room is not None


def test_room_window_without_buttons_gives_up(combat, clock):
    rng = np.random.default_rng(5)
    template = rng.integers(30, 255, (20, 40, 3), dtype=np.uint8)
    combat.imread_cyrillic = lambda name: template

    class Empty:
        def grab(self, rect):
            return np.zeros((200, 300, 4), dtype=np.uint8)

    start = clock.now
    assert combat.find_smart_door({"top": 0, "left": 0, "width": 300, "height": 200}, Empty(), {}) == (None, [])
    assert click_logic.STILL_TIMEOUT_S <= clock.now - start <= click_logic.STILL_TIMEOUT_S + 0.4


# ---------------------------------------------------------------------------
# Коридор: пока флажок едет — смотрим только на флажок
# ---------------------------------------------------------------------------
@pytest.fixture
def navigation(clock, monkeypatch):
    vision = importlib.import_module("vision")
    monkeypatch.setattr(vision, "time", clock)
    module = importlib.import_module("navigation")
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module, "click_point_from_info", lambda name, info, rect: (info["x"], info["y"]))
    monkeypatch.setattr(module, "game_frame", lambda *a, **k: None)
    monkeypatch.setattr(module, "find_on_frame", look_on_frame(module))
    return module


def test_hallway_looks_only_at_moving_flag_and_passes_room_window(navigation, clock, monkeypatch):
    start = clock.now
    looked = []
    taps = []

    def fake_info(name, rect, sct, threshold):
        clock.sleep(0.3)  # снимок и поиск на слабом ПК
        since = clock.now - start
        x = 600 - int(since * 100) if since < 0.8 else 520
        return {"x": x, "y": 200, "w": 60, "h": 40, "score": 0.9, "ox": 0, "oy": 0}

    def fake_loc(name, *a, **k):
        looked.append(name)
        clock.sleep(0.3)
        return None

    monkeypatch.setattr(navigation, "get_match_loc", fake_loc)
    monkeypatch.setattr(navigation, "get_match_info", fake_info)
    monkeypatch.setattr(navigation, "click_human", lambda x, y, seen_at=None, **k: taps.append(seen_at) or "proc")
    monkeypatch.setattr(navigation, "wait_after_tap", lambda *a, **k: (clock.now, (130, 70)))

    assert navigation.smart_navigate_hallway({}, None) == "ROOM_SELECTION"
    assert looked == ["btn_attack.png"]  # «Атаковать» — только до того, как увидели флажок
    assert taps == [pytest.approx(start + 0.6)]  # пауза реакции — от первого снимка с флажком
    assert navigation.take_room_window() == (clock.now, (130, 70))
    assert navigation.take_room_window() is None  # подсказка берётся один раз


# ---------------------------------------------------------------------------
# find_and_click_bulletproof: пауза реакции от появления кнопки
# ---------------------------------------------------------------------------
@pytest.fixture
def vision(clock, monkeypatch):
    module = importlib.import_module("vision")
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module, "click_point_from_info", lambda name, info, rect: (50, 50))
    return module


def run_ok(vision, clock, monkeypatch, seen_at=None):
    taps = []
    info = {"x": 100, "y": 100, "w": 40, "h": 20, "score": 0.95, "ox": 0, "oy": 0}

    def fake_info(*a, **k):
        clock.sleep(0.2)
        return None if taps else info

    def fake_click(x, y, seen_at=None, **k):
        taps.append(seen_at)
        return FakeProc(clock, 0.2)

    monkeypatch.setattr(vision, "get_match_info", fake_info)
    monkeypatch.setattr(vision, "click_human", fake_click)
    start = clock.now
    assert vision.find_and_click_bulletproof("btn_ok.png", {}, None, 0.8, seen_at=seen_at)
    return taps, start


def test_bulletproof_reaction_from_first_shot(vision, clock, monkeypatch):
    taps, start = run_ok(vision, clock, monkeypatch)
    assert taps == [pytest.approx(start)]  # кнопку нашли на первом снимке (он начат в start)


def test_bulletproof_uses_earlier_sighting(vision, clock, monkeypatch):
    """«ОК» бот увидел до чтения ХП: пауза реакции считается от того момента."""
    taps, start = run_ok(vision, clock, monkeypatch, seen_at=clock.now - 3.0)
    assert taps == [pytest.approx(start - 3.0)]


def test_click_human_waits_reaction_then_taps(vision, clock, monkeypatch):
    """Настоящий click_human: ждёт паузу реакции перед нажатием, после нажатия не спит, пишет паузу в замеры."""
    session_log = vision.session_log  # другие тесты могут перезагрузить модуль: берём тот, что видит vision
    started = []
    waits = []
    monkeypatch.setattr(vision, "LAST_WINDOW_RECT", {"top": 0, "left": 0, "width": 1000, "height": 500})
    monkeypatch.setitem(vision.GEOMETRY_CACHE, "is_calibrated", True)
    for key, value in {"offset_x": 0, "offset_y": 0, "game_w": 1000, "game_h": 500}.items():
        monkeypatch.setitem(vision.GEOMETRY_CACHE, key, value)
    monkeypatch.setattr(vision, "get_device_resolution", lambda: (2000, 1000))
    monkeypatch.setattr(vision.subprocess, "Popen", lambda *a, **k: started.append(clock.now) or FakeProc(clock, 0.3))
    monkeypatch.setattr(session_log, "track_tap", lambda *a, **k: None)
    monkeypatch.setattr(session_log, "track_reaction", waits.append)
    monkeypatch.setattr(vision, "TAP_PACER", TapPacer(clock=clock.monotonic, rng=FixedRng(0.6)))

    seen = clock.now
    vision.click_human(100, 100, seen_at=seen)
    assert started == [pytest.approx(seen + 0.6)]
    assert clock.now == pytest.approx(seen + 0.6)  # после нажатия бот не спит
    vision.click_human(120, 100, seen_at=seen - 5)  # кнопка видна давно, но второе нажатие — не раньше 0,5 с
    assert started[1] - started[0] == pytest.approx(click_logic.MIN_TAP_INTERVAL_S)
    assert waits == [pytest.approx(0.6), pytest.approx(0.5)]


# ---------------------------------------------------------------------------
# [ИТОГ]: сколько добавила пауза реакции
# ---------------------------------------------------------------------------
def test_summary_shows_reaction_pause():
    import session_log
    log = session_log.SessionLog()
    for w in (0.0, 0.0, 0.4, 0.2):
        log.track_reaction(w)
    lines = "\n".join(log.summary_lines(0, 0))
    assert "Пауза реакции перед нажатием: ждал 2 раз из 4 | всего 0.6 с, в среднем 0.15 с на нажатие" in lines
