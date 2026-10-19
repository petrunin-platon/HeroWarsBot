# Тесты задачи 6: надёжное чтение окна результата.
# Распознавание проверяем на настоящих скриншотах пользователя (logs/session_01-02/screens/54.png и 111.png):
# из них вырезано окно игры 1590x704, как его видит бот («Чистая зона игры» в логе).
import os
import sys
import types
from datetime import datetime

import pytest

sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import result_scan as rs  # noqa: E402

PACK = ["araji", "hyperion", "rigel", "iyari", "lumira"]
SCREENS = os.path.join(os.path.dirname(__file__), "..", "logs", "session_01-02", "screens")


class FakeSct:
    """Вместо mss: отдаёт заранее заданную картинку."""

    def __init__(self, img):
        self.img = img

    def grab(self, rect):
        return cv2.cvtColor(self.img, cv2.COLOR_BGR2BGRA)


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


def scan_screen(analyzer, img):
    game = img[78:78 + 704, 58:58 + 1590]
    return analyzer.scan_team_health({"top": 0, "left": 0, "width": 1590, "height": 704}, FakeSct(game), PACK)


@pytest.mark.parametrize("name, expected", [
    ("54.png", [100, 100, 55, 100, 100]),
    ("111.png", [56, 59, 81, 38, 44]),
])
def test_real_screens_all_titans_found(analyzer, name, expected):
    img = cv2.imread(os.path.join(SCREENS, name))
    assert img is not None
    status = scan_screen(analyzer, img)
    # порядок в логе: araji, hyperion, rigel, iyari, lumira
    assert rs.missing_titans(PACK, status) == []
    assert not rs.is_unreadable(PACK, status)
    for titan, hp in zip(PACK, expected):
        assert abs(status[titan]["hp"] - hp) <= 5, (titan, status[titan])
        assert status[titan]["score"] >= 0.62


def test_blank_screen_means_rescan_then_sos(analyzer):
    blank = np.zeros((1080, 1920, 3), dtype=np.uint8)
    sleeps = []
    scans = []

    def scan():
        scans.append(1)
        return scan_screen(analyzer, blank)

    status, unreadable = rs.scan_with_retries(scan, PACK, sleep=sleeps.append, log=lambda *_: None)
    assert unreadable
    assert len(scans) == 1 + rs.MAX_RESCANS
    assert sleeps == [rs.RESCAN_PAUSE_S] * rs.MAX_RESCANS
    assert sorted(rs.missing_titans(PACK, status)) == sorted(PACK)
    assert "сходство" in rs.describe_missing(PACK, status)


# --- логика пересканирования на подделке сканера ---------------------------------------------------

def status_with_missing(*missing):
    return {t: ({"hp": 0, "energy": 0, "status": "ОТСУТСТВУЕТ", "score": 0.3} if t in missing
                else {"hp": 100, "energy": 50, "status": "ЖИВ", "score": 0.9}) for t in PACK}


def run(results):
    it = iter(results)
    sleeps = []
    status, unreadable = rs.scan_with_retries(lambda: next(it), PACK, sleep=sleeps.append, log=lambda *_: None)
    return status, unreadable, sleeps


def test_all_found_scans_once():
    _, unreadable, sleeps = run([status_with_missing()])
    assert not unreadable and sleeps == []


def test_one_missing_is_not_rescanned():
    # один титан не найден — это «не дрался», как и раньше
    _, unreadable, sleeps = run([status_with_missing("rigel")])
    assert not unreadable and sleeps == []


def test_two_missing_rescanned_until_found():
    status, unreadable, sleeps = run([status_with_missing("rigel", "iyari"), status_with_missing("rigel", "iyari"),
                                      status_with_missing()])
    assert not unreadable
    assert rs.missing_titans(PACK, status) == []
    assert sleeps == [rs.RESCAN_PAUSE_S, rs.RESCAN_PAUSE_S]


def test_still_unreadable_picks_best_scan():
    best = status_with_missing("rigel", "iyari")
    worst = status_with_missing(*PACK)
    status, unreadable, _ = run([worst, best, worst, worst])
    assert unreadable
    assert status is best


def test_missing_template_counts_as_missing():
    status = status_with_missing()
    del status["rigel"], status["iyari"]
    assert rs.is_unreadable(PACK, status)
    assert "шаблона нет" in rs.describe_missing(PACK, status)


def test_debug_shot_name():
    name = rs.debug_shot_name("sos", 12, "water", datetime(2026, 10, 19, 14, 3, 21))
    assert name == "sos_комната12_water_2026-10-19_14-03-21.png"


def test_debug_dir_created(tmp_path, monkeypatch):
    import data_paths
    monkeypatch.chdir(tmp_path)
    data_paths._CHECKED.clear()
    path = data_paths.debug_dir()
    assert path == "bot_data/debug" and os.path.isdir(tmp_path / "bot_data" / "debug")
