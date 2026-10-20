# Тесты задачи 9в: ХП и энергия с экрана выбора команды.
# Скриншот пользователя logs/session_01-02/screens/pered_boem.png: окно scrcpy 1592x741, сверху рамка окна 28 px.
# В слотах слева направо: amon, hyperion, lumira, iyari, rigel — у всех полное ХП, энергия разная.
# В сетке выше есть и раненый: Араджи (первый ряд, справа) — ХП чуть больше половины.
import os
import sys
import types

import pytest

sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import analyzer as an  # noqa: E402
import team_manager as tm  # noqa: E402

SCREEN = os.path.join(os.path.dirname(__file__), "..", "logs", "session_01-02", "screens", "pered_boem.png")
SLOTS = ["amon", "hyperion", "lumira", "iyari", "rigel"]
# Энергия в слотах (длина жёлтой полоски на скриншоте: 39, 51, 31, 12, 18 пикселей из 65)
SLOT_ENERGY = {"amon": 59, "hyperion": 79, "lumira": 48, "iyari": 18, "rigel": 28}


class FakeSct:
    """Вместо mss: отдаёт заранее заданную картинку и считает снимки."""

    def __init__(self, img):
        self.img = img
        self.grabs = 0

    def grab(self, rect):
        self.grabs += 1
        return cv2.cvtColor(self.img, cv2.COLOR_BGR2BGRA)


def screen_at(monkeypatch, scale):
    """Окно игры из скриншота, уменьшенное или увеличенное в scale раз (как окно scrcpy другого размера)."""
    import vision
    game = cv2.imread(SCREEN)[28:]
    if scale != 1.0:
        game = cv2.resize(game, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = game.shape[:2]
    monkeypatch.setitem(vision.GEOMETRY_CACHE, "is_calibrated", True)
    for key, value in {"offset_x": 0, "offset_y": 0, "game_w": w, "game_h": h, "scale": scale}.items():
        monkeypatch.setitem(vision.GEOMETRY_CACHE, key, value)
    vision.get_scaled_template.cache_clear()
    return game, FakeSct(game), {"top": 0, "left": 0, "width": w, "height": h}


@pytest.fixture
def screen(monkeypatch):
    import vision
    yield screen_at(monkeypatch, 1.0)
    vision.get_scaled_template.cache_clear()


def assert_slot_readings(bars):
    assert set(bars) == set(SLOTS)
    for titan in SLOTS:
        assert bars[titan]["hp"] == 100, (titan, bars[titan])
        assert abs(bars[titan]["energy"] - SLOT_ENERGY[titan]) <= 3, (titan, bars[titan])


def test_slots_and_bars_on_one_snapshot(screen):
    _, sct, rect = screen
    found, slots, bars = tm.scan_slots(tm.slot_titan_names(), rect, sct)
    assert sct.grabs == 1  # кто в слотах и их полоски — с одного снимка
    assert sorted(slots, key=slots.get) == SLOTS
    assert_slot_readings(bars)


def test_known_pack_is_found_faster_with_same_readings(screen):
    """Если бот знает, кто стоит в слотах (LAST_USED_TEAMS), он ищет только их — цифры те же."""
    _, sct, rect = screen
    found, _, bars = tm.scan_slots(["hyperion", "rigel", "iyari", "lumira", "amon"], rect, sct)
    assert set(found) == set(SLOTS) and sct.grabs == 1
    assert_slot_readings(bars)


@pytest.mark.parametrize("scale", [704 / 713, 1.2])
def test_bars_do_not_depend_on_window_size(monkeypatch, scale):
    """Длину полоски бот меряет сам: у вас игра 1590x704 (на скриншоте 1592x713), у других окно может быть больше."""
    import vision
    _, sct, rect = screen_at(monkeypatch, scale)
    try:
        _, _, bars = tm.scan_slots(tm.slot_titan_names(), rect, sct)
        assert_slot_readings(bars)
    finally:
        vision.get_scaled_template.cache_clear()


def test_wounded_titan_in_grid(screen):
    """Полоски под иконками в сетке такие же: у Араджи ХП ~55% (36 из 65 пикселей), энергия ~17%."""
    game, sct, rect = screen
    found = tm.match_many_on_frame(["araji", "angus", "rigel"], rect, sct, tm.TITAN_THRESHOLD, tm.GRID_AREA)
    top = int(game.shape[0] * tm.GRID_AREA[0])
    read = {t: an.read_bars_under_icon(game, (i["x"], i["y"] + top, i["w"], i["h"])) for t, i in found.items()}
    assert abs(read["araji"]["hp"] - 55) <= 3 and abs(read["araji"]["energy"] - 17) <= 3
    assert read["angus"]["energy"] >= 97      # полная энергия
    assert abs(read["rigel"]["energy"] - 27) <= 3


def test_blank_screen_reads_nothing():
    blank = np.zeros((300, 300, 3), dtype=np.uint8)
    assert an.read_bars_under_icon(blank, (100, 50, 66, 48)) == {"hp": None, "energy": None}


def test_bar_percent_rules():
    full, empty = [True] * 65, [False] * 65
    assert an._bar_percent(full, empty, 39) == 100
    half_fill = [True] * 30 + [False] * 35
    assert an._bar_percent(half_fill, [False] * 30 + [True] * 35, 39) == 46
    # пустая полоска (энергия 0): только чёрная часть
    assert an._bar_percent(empty, full, 39) == 0
    # сглаженный край заливки (1 пиксель ни того, ни другого) полоску не обрывает
    edge = [True] * 12 + [False] * 53
    dark = [False] * 13 + [True] * 52
    assert an._bar_percent(edge, dark, 39) == 18
    # короткий кусок — не полоска
    assert an._bar_percent([True] * 10 + [False] * 55, empty, 39) is None


def test_verify_uses_slots_seen_without_new_snapshot(screen, monkeypatch):
    """Слоты уже прочитаны до выбора пака — проверка состава не делает второй снимок."""
    _, sct, rect = screen
    found, _, _ = tm.scan_slots(tm.slot_titan_names(), rect, sct)
    clicks = []
    monkeypatch.setattr(tm, "click_human", lambda *a, **k: clicks.append(a))
    assert tm.verify_and_set_team(SLOTS, None, rect, sct, seen=found)
    assert clicks == [] and sct.grabs == 1


def test_bars_after_team_settled(screen):
    """После сборки ХП и энергия берутся с того снимка, где состав совпал."""
    _, sct, rect = screen
    bars = {}
    assert tm.wait_slots_settled(SLOTS, tm.slot_titan_names(), rect, sct, bars)
    assert_slot_readings(bars)


class SequenceSct(FakeSct):
    """Снимки по очереди из списка картинок (последняя повторяется)."""

    def __init__(self, images):
        super().__init__(images[0])
        self.images = images

    def grab(self, rect):
        self.img = self.images[min(self.grabs, len(self.images) - 1)]
        return super().grab(rect)


def test_bars_that_disagree_with_memory_are_read_again(screen):
    """Цифры не совпали с памятью — бот перечитывает полоски, пока два снимка подряд не совпадут
    (вдруг на первом снимке полоски ещё не дорисовались)."""
    game, _, rect = screen
    half = game.copy()
    half[650:700, 150:720] = (20, 15, 12)   # на первом снимке полосок ещё нет: тёмная пустая область
    sct = SequenceSct([half, game, game])
    found, _, bars = tm.scan_slots(SLOTS, rect, sct)
    assert all(b["hp"] is None for b in bars.values())
    sleeps = []
    tm.recheck_bars(SLOTS, bars, rect, sct, sleep=sleeps.append)
    assert_slot_readings(bars)
    assert sleeps == [tm.BARS_RECHECK_S] * 2 and sct.grabs == 3   # второй и третий снимки совпали — хватит
    # Перечитывать некого — снимков нет
    assert tm.recheck_bars([], bars, rect, sct, sleep=sleeps.append) is bars and sct.grabs == 3
