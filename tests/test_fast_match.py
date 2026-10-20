# Тесты задачи 11: быстрый поиск картинок находит то же самое, что и раньше, и в 2+ раза быстрее.
# Скриншоты пользователя: окна результата (tests/data/screens: result_54, result_111, s06_01),
# экраны выбора команды (pered_boem.png, сессия 04, сессия 09), коридор (сессия 04).
# «Раньше» — обычный cv2.matchTemplate по всему снимку, как бот искал до задачи 11.
import os
import sys
import time
import types

import pytest

sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import vision  # noqa: E402

SCREENS = os.path.join(os.path.dirname(__file__), "data", "screens")
RESULT_PACK = ["araji", "hyperion", "rigel", "iyari", "lumira"]


def shot(path):
    return cv2.imread(os.path.join(SCREENS, path))


def calibrated(img):
    """Игровая область скриншота окна scrcpy, как её находит бот (_calibrate_geometry), и масштаб картинок.
    Снимок дальше — уже игровая область, поэтому сдвиг 0."""
    vision.GEOMETRY_CACHE["is_calibrated"] = False
    vision._calibrate_geometry(cv2.cvtColor(img, cv2.COLOR_BGR2BGRA))
    g = vision.GEOMETRY_CACHE
    game = img[g["offset_y"]:g["offset_y"] + g["game_h"], g["offset_x"]:g["offset_x"] + g["game_w"]]
    g["offset_x"], g["offset_y"] = 0, 0
    vision.get_scaled_template.cache_clear()
    return game


@pytest.fixture
def geometry(monkeypatch):
    # _calibrate_geometry заменяет словарь целиком — после теста вернётся прежний
    monkeypatch.setattr(vision, "GEOMETRY_CACHE", dict(vision.GEOMETRY_CACHE))
    yield calibrated
    vision.get_scaled_template.cache_clear()


def result_game(name):
    """Окно игры 1590x704 из скриншотов сессии 01-02 (как в tests/test_result_scan.py)."""
    return shot(name)[78:78 + 704, 58:58 + 1590]


def use_result_geometry(monkeypatch):
    monkeypatch.setitem(vision.GEOMETRY_CACHE, "is_calibrated", True)
    for key, value in {"offset_x": 0, "offset_y": 0, "game_w": 1590, "game_h": 704, "scale": 704 / 720}.items():
        monkeypatch.setitem(vision.GEOMETRY_CACHE, key, value)
    vision.get_scaled_template.cache_clear()


def plain(game, name):
    """Как бот искал раньше: весь снимок. (совпадение, (x, y))."""
    template = vision.imread_cyrillic(name)
    _, max_val, _, max_loc = cv2.minMaxLoc(cv2.matchTemplate(game, template, cv2.TM_CCOEFF_NORMED))
    return max_val, max_loc


def assert_same_as_plain(game, name, threshold):
    """Новый поиск (часть экрана из AREAS + быстрый поиск) находит то же, что старый по всему снимку."""
    old_score, old_loc = plain(game, name)
    info = vision.find_on_frame((game, 0, 0), name, threshold)
    if old_score >= threshold:
        assert info is not None, (name, old_score)
        assert (info["x"], info["y"]) == tuple(old_loc), name
        assert abs(info["score"] - old_score) < 1e-4, name
    else:
        assert info is None, (name, old_score)
    return old_score >= threshold


# ---------------------------------------------------------------------------
# То же самое, что раньше
# ---------------------------------------------------------------------------
def test_fast_scores_equal_plain_on_whole_screen(monkeypatch):
    """match_scores: везде, где совпадение не ниже порога, — те же числа, что у cv2.matchTemplate."""
    use_result_geometry(monkeypatch)
    game = result_game("result_54.webp")
    for name, threshold in [("res_araji.png", 0.62), ("res_rigel.png", 0.62), ("res_moloch.png", 0.62),
                            ("btn_ok.png", 0.8), ("badge_x2.png", 0.75), ("araji.png", 0.88)]:
        template = vision.imread_cyrillic(name)
        old = cv2.matchTemplate(game, template, cv2.TM_CCOEFF_NORMED)
        new, _ = vision.match_scores(game, template, threshold)
        assert np.array_equal(old >= threshold, new >= threshold), name
        mask = old >= threshold
        if mask.any():
            assert np.max(np.abs(old[mask] - new[mask])) < 1e-4, name


@pytest.mark.parametrize("name, present", [
    ("result_54.webp", ["btn_ok.png", "badge_x2.png"]),
    ("result_111.webp", ["btn_ok.png"]),
])
def test_result_buttons_found_in_their_area(monkeypatch, name, present):
    use_result_geometry(monkeypatch)
    game = result_game(name)
    found = [n for n, thr in [("btn_ok.png", 0.8), ("badge_x2.png", 0.75), ("btn_retry.png", 0.75)]
             if assert_same_as_plain(game, n, thr)]
    assert set(present) <= set(found)


def test_result_window_session06_buttons(geometry):
    """Окно результата сессии 06 (01.png): «Ещё раз», «ОК» и значок «x2» — внизу, в своих частях экрана."""
    game = geometry(shot("s06_01.webp")[:745, :1597])
    for n, thr in [("btn_ok.png", 0.8), ("btn_retry.png", 0.75), ("badge_x2.png", 0.75)]:
        assert assert_same_as_plain(game, n, thr), n


@pytest.mark.parametrize("name", ["result_54.webp", "result_111.webp"])
def test_result_icons_in_band_same_as_whole_screen(monkeypatch, name):
    """Иконки на окне результата ищутся только в их полосе — места и совпадения те же, что по всему снимку."""
    import analyzer
    use_result_geometry(monkeypatch)
    game = result_game(name)
    found = {}
    rect = {"top": 0, "left": 0, "width": 1590, "height": 704}

    class Sct:
        def grab(self, r):
            return cv2.cvtColor(game, cv2.COLOR_BGR2BGRA)

    pack = RESULT_PACK + ["moloch", "sigurd"]  # этих двоих в бою не было
    status = analyzer.scan_team_health(rect, Sct(), pack, found=found)
    for titan in pack:
        template = analyzer._result_template(titan)
        _, old_score, _, old_loc = cv2.minMaxLoc(cv2.matchTemplate(game, template, cv2.TM_CCOEFF_NORMED))
        if old_score >= analyzer.RESULT_ICON_THRESHOLD:
            assert found[titan][:2] == tuple(old_loc), titan
            assert abs(status[titan]["score"] - old_score) < 1e-4
        else:
            assert status[titan]["status"] == "ОТСУТСТВУЕТ", titan
    assert all(found[t] for t in RESULT_PACK)


# Полные слоты (свет), огонь (Араджи и Вулкан), смешанная с прокрученной сеткой (Алекто и Умбра).
# Сравнение со старым поиском долгое (~8 с на экран), поэтому экранов три
# Скриншоты окна результата, которые вы прислали к задаче 11 (окно scrcpy 1592x741): пак из 5 и из 3 титанов.
# Числа — как их читал бот до задачи 11 (тот же код полосок; проверено запуском старого analyzer.py)
DATA = os.path.join(os.path.dirname(__file__), "data")
RESULT_WINDOWS = [
    ("result_window_5_titans.webp", {"araji": (100, 79), "hyperion": (100, 70), "rigel": (100, 69),
                                     "iyari": (100, 100), "lumira": (100, 100)}),
    ("result_window_3_titans.webp", {"araji": (67, 47), "ignis": (100, 14), "acheron": (86, 90)}),
]


@pytest.mark.parametrize("name, expected", RESULT_WINDOWS)
def test_result_window_reads_same_as_before(geometry, name, expected):
    """Иконки ищутся в своей полосе и быстрым поиском — места те же, что по всему снимку, ХП и энергия те же, что
    читал старый код (полоски читаются тем же кодом, его настройку задача 11 не трогала)."""
    import analyzer
    game = geometry(cv2.imread(os.path.join(DATA, name)))
    h, w = game.shape[:2]
    found = {}
    status = analyzer.scan_team_health({"top": 0, "left": 0, "width": w, "height": h}, GameSct(game), list(expected),
                                       found=found)
    for titan, (hp, energy) in expected.items():
        assert (status[titan]["hp"], status[titan]["energy"]) == (hp, energy), titan
        _, _, _, old_loc = cv2.minMaxLoc(cv2.matchTemplate(game, analyzer._result_template(titan), cv2.TM_CCOEFF_NORMED))
        assert found[titan][:2] == tuple(old_loc), titan
    assert vision.find_on_frame((game, 0, 0), "btn_ok.png", 0.8) is not None
    assert vision.find_on_frame((game, 0, 0), "badge_x2.png", 0.75) is not None


TEAM_SCREENS = [
    "pered_boem.webp",
    "s09_araji_i_vulkan_v_slotah.webp",
    "s09_umbra_v_slote.webp",
]


@pytest.mark.parametrize("path", TEAM_SCREENS)
def test_team_screen_same_as_before(geometry, path):
    """Слоты и сетка: каждый титан находится там же и с тем же совпадением, что раньше (поиск по всей ширине),
    кнопки «Автобой» и «В бой!» — в своей части экрана."""
    import team_manager as tm
    game = geometry(shot(path))
    h = game.shape[0]
    names = tm.slot_titan_names()
    for area, old_top, old_bottom in [(tm.SLOTS_AREA, 0.75, 1.0), (tm.GRID_AREA, 0.0, 0.75)]:
        new = vision.match_many_on_frame(names, None, None, tm.TITAN_THRESHOLD, area, frame=(game, 0, 0))
        top = int(h * old_top)
        part = game[top:int(h * old_bottom)]
        old = {}
        for n in names:
            score, loc = plain(part, n + ".png")
            if score >= tm.TITAN_THRESHOLD:
                old[n] = (loc[0], loc[1] + top, score)
        assert set(new) == set(old), path
        for n, (x, y, score) in old.items():
            assert (new[n]["x"], new[n]["y"]) == (x, y) and abs(new[n]["score"] - score) < 1e-4, n
    for n in ("btn_auto.png", "btn_in_battle.png"):
        assert assert_same_as_plain(game, n, 0.8), n


@pytest.mark.parametrize("path", [
    "s04_sleva_napravo_ostanovka_dveri.jpg",
    "s04_spravo_nalevo_ostanovka_dveri.jpg",
    "s04_spravo_nalevo_dver_v_puti.jpg",
])
def test_hallway_flag_same_as_before(geometry, path):
    game = geometry(shot(path))
    assert assert_same_as_plain(game, "flag_enter.png", 0.8)
    assert_same_as_plain(game, "btn_attack.png", 0.68)
    assert_same_as_plain(game, "btn_activate.png", 0.8)


def test_area_box_follows_window_proportions():
    """Часть экрана считается от высоты: при другом соотношении сторон панель слева не обрезается."""
    area = vision.Area(0.75, 1.0, right=1.05)
    assert area.box((704, 1590)) == (0, 528, 739, 704)
    assert area.box((748, 1330)) == (0, 561, 785, 748)    # телефон 16:9 — ширина панели та же в долях высоты
    centered = vision.Area(0.1, 0.5, -0.5, 0.5, "center")
    assert centered.box((700, 1600)) == (450, 70, 1150, 350)
    assert vision.Area(0.5, 1.0, -1.0, None, "right").box((700, 1600)) == (900, 350, 1600, 700)
    assert vision.area_box((100, 200), (0.5, 1.0)) == (0, 50, 200, 100)


# ---------------------------------------------------------------------------
# Быстрее хотя бы в 2 раза (замер в облаке; один поток OpenCV — как на слабом ПК)
# ---------------------------------------------------------------------------
def best_time(fn, runs=3):
    best = None
    for _ in range(runs):
        started = time.perf_counter()
        fn()
        took = time.perf_counter() - started
        best = took if best is None else min(best, took)
    return best


@pytest.fixture
def one_thread():
    threads = cv2.getNumThreads()
    cv2.setNumThreads(1)
    yield
    cv2.setNumThreads(threads)


class GameSct:
    def __init__(self, game):
        self.frame = cv2.cvtColor(game, cv2.COLOR_BGR2BGRA)

    def grab(self, rect):
        return self.frame


def test_steps_at_least_twice_faster(monkeypatch, geometry, one_thread, capsys):
    import analyzer
    import team_manager as tm
    rows = []

    # 1. Окно результата: 5 иконок титанов + полоски (раньше — каждая иконка по всему снимку)
    use_result_geometry(monkeypatch)
    game = result_game("result_54.webp")
    rect = {"top": 0, "left": 0, "width": 1590, "height": 704}
    sct = GameSct(game)

    def result_before():
        frame = cv2.cvtColor(sct.grab(rect), cv2.COLOR_BGRA2BGR)
        analyzer._result_masks(frame)
        for titan in RESULT_PACK:
            cv2.minMaxLoc(cv2.matchTemplate(frame, analyzer._result_template(titan), cv2.TM_CCOEFF_NORMED))

    rows.append(("окно результата: ХП 5 титанов", best_time(result_before),
                 best_time(lambda: analyzer.scan_team_health(rect, sct, RESULT_PACK))))

    # 2. Окно результата: «ОК» и «x2» (раньше — два снимка и поиск по всему снимку)
    def ok_before():
        for name in ("btn_ok.png", "badge_x2.png"):
            frame = cv2.cvtColor(sct.grab(rect), cv2.COLOR_BGRA2BGR)
            cv2.minMaxLoc(cv2.matchTemplate(frame, vision.imread_cyrillic(name), cv2.TM_CCOEFF_NORMED))

    def ok_after():
        frame = vision.game_frame(rect, sct)
        vision.find_on_frame(frame, "btn_ok.png", 0.8)
        vision.find_on_frame(frame, "badge_x2.png", 0.75)

    rows.append(("окно результата: «ОК» и «x2»", best_time(ok_before), best_time(ok_after)))

    # 3. Слоты: кто стоит (все 29 титанов; раньше — нижняя четверть по всей ширине)
    team = geometry(shot(TEAM_SCREENS[0]))
    h, w = team.shape[:2]
    team_rect = {"top": 0, "left": 0, "width": w, "height": h}
    team_sct = GameSct(team)
    names = tm.slot_titan_names()

    def slots_before():
        frame = cv2.cvtColor(team_sct.grab(team_rect), cv2.COLOR_BGRA2BGR)
        part = frame[int(h * 0.75):]
        for n in names:
            cv2.minMaxLoc(cv2.matchTemplate(part, vision.imread_cyrillic(n + ".png"), cv2.TM_CCOEFF_NORMED))

    rows.append(("слоты: кто стоит (29 титанов)", best_time(slots_before),
                 best_time(lambda: tm.read_slots(names, team_rect, team_sct))))

    # 4. Коридор, один шаг: «Атаковать», флажок, «Активировать» (раньше — три снимка, каждый по всему окну)
    hall = geometry(shot("s04_sleva_napravo_ostanovka_dveri.jpg"))
    hh, hw = hall.shape[:2]
    hall_rect = {"top": 0, "left": 0, "width": hw, "height": hh}
    hall_sct = GameSct(hall)

    def hallway_before():
        for name in ("btn_attack.png", "flag_enter.png", "btn_activate.png"):
            frame = cv2.cvtColor(hall_sct.grab(hall_rect), cv2.COLOR_BGRA2BGR)
            cv2.minMaxLoc(cv2.matchTemplate(frame, vision.imread_cyrillic(name), cv2.TM_CCOEFF_NORMED))

    def hallway_after():
        frame = vision.game_frame(hall_rect, hall_sct)
        for name, thr in (("btn_attack.png", 0.68), ("flag_enter.png", 0.8), ("btn_activate.png", 0.8)):
            vision.find_on_frame(frame, name, thr)

    rows.append(("коридор: один шаг", best_time(hallway_before), best_time(hallway_after)))

    with capsys.disabled():
        print("\n[ЗАМЕР] Шаг | раньше | теперь | быстрее в")
        for step, before, after in rows:
            print(f"[ЗАМЕР] {step} | {before * 1000:.0f} мс | {after * 1000:.0f} мс | {before / after:.1f} раза")
    for step, before, after in rows:
        assert before >= 2 * after, (step, before, after)


@pytest.mark.parametrize("name, expected", RESULT_WINDOWS)
def test_result_debug_image_marks_what_bot_measured(geometry, name, expected):
    """Режим отладки: картинка с разметкой строится на том же снимке и не меняет цифры. Красная черта (конец заливки)
    стоит там, где бот посчитал: при 100% — на конце полной длины (белой рамки)."""
    import analyzer
    game = geometry(cv2.imread(os.path.join(DATA, name)))
    h, w = game.shape[:2]
    icons = {}
    status = analyzer.scan_team_health({"top": 0, "left": 0, "width": w, "height": h}, GameSct(game), list(expected),
                                       found=icons, quiet=True)
    img = analyzer.result_debug_image(game, icons, status, w / 939.0)
    assert img.shape == game.shape and not np.array_equal(img, game)
    masks = analyzer._result_masks(game)
    for titan, (hp, energy) in expected.items():
        marks = {}
        assert analyzer._result_bars(masks, *icons[titan], w / 939.0, marks) == (hp, energy)
        x, _, width = marks["hp"]
        assert int(width / marks["full"] * 100) == min(hp, 100) or hp == 100
