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
    assert unwanted == ["amon", "rigel"]  # слева направо (задача 11)
    assert missing == ["sigurd", "nova"]  # порядок сборки как в игре
    assert set(missing) == {"sigurd", "nova"}
    assert tm.team_diff(["hyperion"], {"hyperion": 5}) == ([], [])


def test_mismatch_removes_unwanted_left_to_right_without_swipes(screen, monkeypatch):
    sct, rect = screen
    clicked = []
    monkeypatch.setattr(tm, "open_grid_if_needed", lambda *a: True)
    monkeypatch.setattr(tm, "precise_select_titan", lambda x, y, seen_at=None: clicked.append((x, y)))
    swipes = []
    monkeypatch.setattr(tm, "swipe_scrcpy", lambda *a, **k: swipes.append(k))
    monkeypatch.setattr(tm, "SLOTS_SETTLE_TIMEOUT", 0.0)
    monkeypatch.setattr(tm.time, "sleep", lambda s: None)
    # нужен только hyperion: четверых лишних убираем, а картинка не меняется — проверка в конце честно провалится
    ok = tm.verify_and_set_team(["hyperion"], None, rect, sct)
    assert not ok
    assert swipes == []  # свайпов вверх нет, вниз не нужны: никого не надо искать в сетке
    first_four = clicked[:4]
    assert [x for x, _ in first_four] == sorted(x for x, _ in first_four)


def test_slot_names_from_assets_dir_include_metida():
    names = tm.slot_titan_names()
    assert "metida" in names and set(tm.GAME_ORDER) <= set(names)
    assert names[:len(tm.GAME_ORDER)] == tm.GAME_ORDER
    assert not any(n.startswith(tm.NOT_TITAN_PREFIXES) for n in names)


def test_slot_names_from_assets_db(monkeypatch):
    """В собранном .exe картинки лежат в assets_db.py (ключи «имя.png» и «RU/имя.png»), а папки assets/ может не быть."""
    import vision
    monkeypatch.setattr(vision, "ASSETS", {"newtitan.png": "x", "RU/btn_ok.png": "x", "RU\\btn_ok.png": "x", "btn_auto.png": "x", "enemy_nova.png": "x"})
    monkeypatch.setattr(vision, "ASSETS_DIR", "/нет/такой/папки")
    names = tm.slot_titan_names()
    assert "newtitan" in names
    assert "btn_auto" not in names and "enemy_nova" not in names and "btn_ok" not in names
    assert "RU/btn_ok" not in names


def test_slot_names_include_target_pack_extras(monkeypatch):
    import vision
    monkeypatch.setattr(vision, "ASSETS", {})
    monkeypatch.setattr(vision, "ASSETS_DIR", "/нет/такой/папки")
    assert "secret_titan" in tm.slot_titan_names(["secret_titan"])


# ---------------------------------------------------------------------------
# Задача 11: слоты и сетка на скриншотах сессии 09 (logs/session_09/screens/, окно 1592x741, рамка 28 px)
# ---------------------------------------------------------------------------
SESSION09 = os.path.join(os.path.dirname(__file__), "..", "logs", "session_09", "screens")


def load09(name):
    img = cv2.imread(os.path.join(SESSION09, name))
    assert img is not None, name
    return img[28:]


class SequenceSct(FakeSct):
    """Снимки по очереди из списка картинок (последняя повторяется)."""

    def __init__(self, images):
        super().__init__(images[0])
        self.images = images

    def grab(self, rect):
        self.img = self.images[min(self.grabs, len(self.images) - 1)]
        return super().grab(rect)


@pytest.fixture
def game09(screen):
    """Геометрия та же, что у pered_boem.png (окно того же размера); картинки берите через load09."""
    _, rect = screen
    return rect


@pytest.mark.parametrize("name, expected", [
    ("araji_i_vulkan_v_slotah.png", ["araji", "vulcan"]),
    ("alecto_i_umbra_v_slotah.png", ["umbra", "alecto"]),
    ("alecto_v_slote.png", ["alecto"]),
    ("umbra_v_slote.png", ["umbra"]),
])
def test_session09_slots(game09, name, expected):
    sct = FakeSct(load09(name))
    _, slots = tm.read_slots(tm.slot_titan_names(), game09, sct)
    assert sorted(slots, key=slots.get) == expected


def test_slots_are_right_aligned(game09, screen):
    """Слоты в игре прижаты вправо: один титан стоит в самом правом слоте, двое — в двух правых
    (на pered_boem.png заняты все пять). Поэтому лишних надо убирать слева направо."""
    full_sct, _ = screen
    _, full = tm.read_slots(tm.slot_titan_names(), game09, full_sct)
    xs = sorted(full.values())
    _, one = tm.read_slots(tm.slot_titan_names(), game09, FakeSct(load09("alecto_v_slote.png")))
    _, two = tm.read_slots(tm.slot_titan_names(), game09, FakeSct(load09("araji_i_vulkan_v_slotah.png")))
    assert abs(one["alecto"] - xs[4]) <= 5
    assert abs(two["araji"] - xs[3]) <= 5 and abs(two["vulcan"] - xs[4]) <= 5


def test_alecto_in_grid_is_where_alecto_is_not_on_umbra(game09):
    """Сессии 08 и 09: бот «ставил Алекто», а в слот вставала Умбра — она в том же столбце сетки, на ряд ниже.
    На скриншоте Алекто находится на своём месте, лучше всех совпадает именно там, а Умбра — на своём."""
    import vision
    sct = FakeSct(load09("umbra_v_slote.png"))  # Умбра в слоте, Алекто в сетке без галочки
    frame = vision.game_frame(game09, sct)
    names = tm.slot_titan_names()
    in_grid = tm.best_per_spot(tm.match_many_on_frame(names, game09, sct, tm.TITAN_THRESHOLD, tm.GRID_AREA, frame=frame))
    alecto, umbra = in_grid["alecto"], in_grid["umbra"]
    assert abs(alecto["x"] - umbra["x"]) < 10                 # один столбец
    assert umbra["y"] - alecto["y"] > alecto["h"]             # Алекто на ряд выше Умбры
    assert tm.better_titan_here("alecto", alecto, frame, names) is None
    # Алекто в слоте — в сетке у неё галочка, и бот её там не находит (ставить её не нужно)
    assert "alecto" not in tm.match_many_on_frame(["alecto"], game09, FakeSct(load09("alecto_v_slote.png")),
                                                  tm.TITAN_THRESHOLD, tm.GRID_AREA)


def test_best_per_spot_keeps_better_match():
    a = {"x": 100, "y": 50, "w": 66, "h": 49, "score": 0.91}
    b = {"x": 104, "y": 52, "w": 66, "h": 49, "score": 0.95}   # та же точка, совпадение лучше
    c = {"x": 207, "y": 50, "w": 66, "h": 49, "score": 0.90}   # соседний слот
    assert tm.best_per_spot({"alecto": a, "umbra": b, "mor": c}) == {"umbra": b, "mor": c}


class RightAlignedSlots:
    """Модель слотов игры: титаны прижаты вправо; убрали одного — все, кто левее, сдвигаются на слот вправо."""
    XS = [200, 307, 413, 518, 627]

    def __init__(self, titans):
        self.titans = list(titans)  # слева направо

    def positions(self):
        start = len(self.XS) - len(self.titans)
        return {t: self.XS[start + i] for i, t in enumerate(self.titans)}

    def tap(self, x):
        hit = next(t for t, px in self.positions().items() if px == x)
        self.titans.remove(hit)
        return hit


def test_removal_left_to_right_hits_the_right_titans():
    """Сессии 07 и 09, огонь: надо убрать Вулкана и Молоха. Нажатия — по одному снимку, сделанному до них."""
    game = RightAlignedSlots(["acheron", "araji", "vulcan", "ignis", "moloch"])
    before = game.positions()
    unwanted, missing = tm.team_diff(["araji", "ignis", "acheron"], before)
    assert unwanted == ["vulcan", "moloch"] and missing == []
    assert [game.tap(before[t]) for t in unwanted] == ["vulcan", "moloch"]
    assert set(game.titans) == {"acheron", "araji", "ignis"}


def test_old_right_to_left_order_removed_araji():
    """Как было: сначала Молох (справа), все левее сдвинулись — и второе нажатие попало в Араджи."""
    game = RightAlignedSlots(["acheron", "araji", "vulcan", "ignis", "moloch"])
    before = game.positions()
    assert [game.tap(before[t]) for t in ["moloch", "vulcan"]] == ["moloch", "araji"]
    assert "vulcan" in game.titans and "araji" not in game.titans


def test_settled_needs_two_same_shots(game09, monkeypatch):
    """Сессия 09: на снимке посреди анимации «видно» нужный состав, а на следующем — уже другой.
    Раньше бот принимал первый снимок; теперь нужно два одинаковых подряд."""
    monkeypatch.setattr(tm, "SLOTS_SETTLE_TIMEOUT", 0.8)
    sct = SequenceSct([load09("araji_i_vulkan_v_slotah.png"), load09("alecto_v_slote.png")])
    settled, slots = tm.wait_slots_settled(["araji", "vulcan"], tm.slot_titan_names(), game09, sct)
    assert not settled and set(slots) == {"alecto"}

    sct = SequenceSct([load09("alecto_v_slote.png"), load09("araji_i_vulkan_v_slotah.png")])
    settled, slots = tm.wait_slots_settled(["araji", "vulcan"], tm.slot_titan_names(), game09, sct)
    assert settled and set(slots) == {"araji", "vulcan"} and sct.grabs == 3


def test_settled_looks_only_after_tap_reached_phone(game09):
    """Первый снимок для проверки — только когда последнее нажатие дошло до телефона."""
    events = []

    class SlowTap:
        def __init__(self):
            self.polls = 0

        def poll(self):
            self.polls += 1
            events.append("poll")
            return 0 if self.polls >= 3 else None

    class Recording(FakeSct):
        def grab(self, rect):
            events.append("grab")
            return super().grab(rect)

    sct = Recording(load09("araji_i_vulkan_v_slotah.png"))
    settled, _ = tm.wait_slots_settled(["araji", "vulcan"], tm.slot_titan_names(), game09, sct, last_tap=SlowTap())
    assert settled
    assert events.index("grab") > events.index("poll") and events[:3] == ["poll"] * 3


def test_swipe_waits_until_grid_stops(game09, monkeypatch):
    """После свайпа сетка едет по инерции (40 → 12 → 3 пикселя за снимок) — титанов ищем, только когда она встала."""
    base = load09("umbra_v_slote.png")

    def scrolled(d):
        img = base.copy()
        img[0:500] = base[d:500 + d]
        return img

    swipes = []
    monkeypatch.setattr(tm, "swipe_scrcpy", lambda rect, direction: swipes.append(direction))
    sct = SequenceSct([scrolled(40), scrolled(12), scrolled(3), base, base])
    seen_at, frame = tm.swipe_grid(game09, sct, "down")
    assert swipes == ["down"]
    assert sct.grabs == 5
    assert np.array_equal(frame[0], base)
