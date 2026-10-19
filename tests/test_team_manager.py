# Тесты задачи 7: проверка состава одним снимком экрана.
# Распознавание проверяем на настоящем скриншоте пользователя (logs/session_01-02/screens/pered_boem.png):
# окно scrcpy 1592x741, сверху рамка окна 28 px, внизу в слотах стоят amon, hyperion, iyari, lumira, rigel.
import os
import sys
import types

import pytest

sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import team_manager as tm  # noqa: E402

SCREEN = os.path.join(os.path.dirname(__file__), "..", "logs", "session_01-02", "screens", "pered_boem.png")
IN_SLOTS = {"amon", "hyperion", "iyari", "lumira", "rigel"}
IN_GRID_ONLY = {"angus", "araji", "mairi", "moloch", "nova", "sigurd", "solaris", "tidus", "verdok"}


class FakeSct:
    """Вместо mss: отдаёт заранее заданную картинку и считает снимки."""

    def __init__(self, img):
        self.img = img
        self.grabs = 0

    def grab(self, rect):
        self.grabs += 1
        return cv2.cvtColor(self.img, cv2.COLOR_BGR2BGRA)


@pytest.fixture
def screen(monkeypatch):
    import vision
    img = cv2.imread(SCREEN)
    assert img is not None
    game = img[28:]
    h, w = game.shape[:2]
    monkeypatch.setitem(vision.GEOMETRY_CACHE, "is_calibrated", True)
    for key, value in {"offset_x": 0, "offset_y": 0, "game_w": w, "game_h": h, "scale": 1.0}.items():
        monkeypatch.setitem(vision.GEOMETRY_CACHE, key, value)
    vision.get_scaled_template.cache_clear()
    yield FakeSct(game), {"top": 0, "left": 0, "width": w, "height": h}
    vision.get_scaled_template.cache_clear()


def test_all_slots_found_on_one_snapshot(screen):
    sct, rect = screen
    found, slots = tm.read_slots(tm.GAME_ORDER, rect, sct)
    assert set(slots) == IN_SLOTS
    assert sct.grabs == 1  # один снимок на все 28 титанов
    # порядок слотов слева направо: amon, hyperion, lumira, iyari, rigel (по x на скриншоте)
    assert sorted(slots, key=slots.get) == ["amon", "hyperion", "lumira", "iyari", "rigel"]


def test_grid_titans_found_on_one_snapshot(screen):
    sct, rect = screen
    found = tm.match_many_on_frame(sorted(IN_GRID_ONLY), rect, sct, tm.TITAN_THRESHOLD, tm.GRID_AREA)
    assert set(found) == IN_GRID_ONLY
    assert sct.grabs == 1


def test_matching_pack_changes_nothing(screen, monkeypatch):
    sct, rect = screen
    clicks = []
    monkeypatch.setattr(tm, "click_human", lambda *a, **k: clicks.append(a))
    monkeypatch.setattr(tm, "swipe_scrcpy", lambda *a, **k: clicks.append("swipe"))
    assert tm.verify_and_set_team(sorted(IN_SLOTS), None, rect, sct)
    assert clicks == []
    assert sct.grabs == 1


def test_team_diff():
    slots = {"amon": 200, "hyperion": 300, "rigel": 600}
    unwanted, missing = tm.team_diff(["hyperion", "sigurd", "nova"], slots)
    assert unwanted == ["rigel", "amon"]  # справа налево
    assert missing == ["sigurd", "nova"]  # порядок сборки как в игре
    assert set(missing) == {"sigurd", "nova"}
    assert tm.team_diff(["hyperion"], {"hyperion": 5}) == ([], [])


def test_mismatch_removes_unwanted_right_to_left_without_swipes(screen, monkeypatch):
    sct, rect = screen
    clicked = []
    monkeypatch.setattr(tm, "open_grid_if_needed", lambda *a: True)
    monkeypatch.setattr(tm, "precise_select_titan", lambda x, y: clicked.append((x, y)))
    swipes = []
    monkeypatch.setattr(tm, "swipe_scrcpy", lambda *a, **k: swipes.append(k))
    monkeypatch.setattr(tm, "SLOTS_SETTLE_TIMEOUT", 0.0)
    monkeypatch.setattr(tm.time, "sleep", lambda s: None)
    # нужен только hyperion: четверых лишних убираем, а картинка не меняется — проверка в конце честно провалится
    ok = tm.verify_and_set_team(["hyperion"], None, rect, sct)
    assert not ok
    assert swipes == []  # свайпов вверх нет, вниз не нужны: никого не надо искать в сетке
    first_four = clicked[:4]
    assert [x for x, _ in first_four] == sorted((x for x, _ in first_four), reverse=True)
